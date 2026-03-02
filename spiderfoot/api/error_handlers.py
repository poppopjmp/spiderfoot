"""
Structured API error response handlers.

Wraps all FastAPI HTTPExceptions and unhandled exceptions in a
consistent JSON envelope that includes the request ID from the
tracing middleware, a machine-readable error code, and a timestamp.

Response format:
    {
        "error": {
            "code": "SCAN_NOT_FOUND",
            "message": "Scan not found",
            "status": 404,
            "request_id": "abc123...",
            "timestamp": 1718901234.56,
            "details": null
        }
    }

Usage:
    from spiderfoot.api.error_handlers import install_error_handlers
    install_error_handlers(app)
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


# ── Error codes ──────────────────────────────────────────────────────

class ErrorCode:
    """Well-known error codes used across the API."""

    # Generic
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    UNAUTHORIZED = "UNAUTHORIZED"
    RATE_LIMITED = "RATE_LIMITED"
    CONFLICT = "CONFLICT"
    BAD_REQUEST = "BAD_REQUEST"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    BAD_GATEWAY = "BAD_GATEWAY"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    GATEWAY_TIMEOUT = "GATEWAY_TIMEOUT"

    # Domain-specific
    SCAN_NOT_FOUND = "SCAN_NOT_FOUND"
    SCAN_ALREADY_RUNNING = "SCAN_ALREADY_RUNNING"
    MODULE_NOT_FOUND = "MODULE_NOT_FOUND"
    CORRELATION_NOT_FOUND = "CORRELATION_NOT_FOUND"
    WORKSPACE_NOT_FOUND = "WORKSPACE_NOT_FOUND"
    INVALID_TARGET = "INVALID_TARGET"
    UPLOAD_TOO_LARGE = "UPLOAD_TOO_LARGE"
    UPLOAD_INVALID_TYPE = "UPLOAD_INVALID_TYPE"


# ── Error response schema ────────────────────────────────────────────

class ErrorDetail(BaseModel):
    """Structured error payload."""
    code: str
    message: str
    status: int
    request_id: str | None = None
    timestamp: float = 0.0
    details: Any | None = None


class ErrorResponse(BaseModel):
    """Envelope wrapping an ErrorDetail."""
    error: ErrorDetail


# ── HTTP status → error code mapping ─────────────────────────────────

_STATUS_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    501: "NOT_IMPLEMENTED",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def _error_code_for(status: int, detail: str = "") -> str:
    """Derive a machine-readable error code from the HTTP status and detail."""
    # Check if the detail itself contains a common domain hint
    detail_lower = detail.lower() if detail else ""
    if "scan" in detail_lower and status == 404:
        return "SCAN_NOT_FOUND"
    if "module" in detail_lower and status == 404:
        return "MODULE_NOT_FOUND"
    if "correlation" in detail_lower and status == 404:
        return "CORRELATION_NOT_FOUND"
    if "workspace" in detail_lower and status == 404:
        return "WORKSPACE_NOT_FOUND"
    return _STATUS_CODES.get(status, f"HTTP_{status}")


def _get_request_id(request: Request) -> str | None:
    """Extract the request-tracing ID from the request state or headers."""
    # Set by request_tracing middleware
    rid = getattr(request.state, "request_id", None)
    if rid:
        return str(rid)
    return request.headers.get("x-request-id")


def _build_error_response(
    status: int,
    message: str,
    request: Request,
    details: Any = None,
    code: str | None = None,
) -> JSONResponse:
    """Build a structured JSON error response."""
    error_code = code or _error_code_for(status, message)
    body = ErrorResponse(
        error=ErrorDetail(
            code=error_code,
            message=message,
            status=status,
            request_id=_get_request_id(request),
            timestamp=time.time(),
            details=details,
        )
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(),
    )


# ── Exception handlers ───────────────────────────────────────────────

async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle FastAPI/Starlette HTTPExceptions."""
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return _build_error_response(exc.status_code, detail, request)


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic request validation errors."""
    errors = []
    for err in exc.errors():
        loc = " → ".join(str(l) for l in err.get("loc", []))
        errors.append({"field": loc, "message": err.get("msg", ""), "type": err.get("type", "")})
    return _build_error_response(
        422,
        "Request validation failed",
        request,
        details=errors,
        code="VALIDATION_ERROR",
    )


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all for unhandled exceptions — returns 500 without leaking internals."""
    log.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return _build_error_response(
        500,
        "Internal server error",
        request,
    )


# ── Installer ────────────────────────────────────────────────────────

def install_error_handlers(app: FastAPI) -> None:
    """Register structured error handlers on the FastAPI application."""
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
    log.info("Structured API error handlers installed")


# Alias for backward compat with error_handling.py
register_error_handlers = install_error_handlers


# ── Convenience helpers ──────────────────────────────────────────────

def error_response(
    status: int,
    code: str,
    message: str,
    *,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build a standardised error JSONResponse without a Request object.

    Useful for raising errors in service layers that don't have
    access to the incoming ``Request``.
    """
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "status": status,
        }
    }
    if request_id:
        body["error"]["request_id"] = request_id
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)


def api_error(
    status: int,
    code: str,
    message: str,
) -> StarletteHTTPException:
    """Create an HTTPException with structured detail.

    The ``detail`` field carries the structured error info so the
    registered handler can render it in the standard envelope.
    """
    return StarletteHTTPException(
        status_code=status,
        detail={"code": code, "message": message},
    )

