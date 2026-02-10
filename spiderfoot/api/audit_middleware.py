"""
API request audit logging middleware.

Records every API request with method, path, status code, duration,
client IP, and user identity (from auth headers) for compliance,
debugging, and usage analytics.

Logs are emitted at INFO level in structured JSON format via the
standard ``spiderfoot.api.audit`` log, allowing them to be routed
to Vector.dev / Elasticsearch / file via existing log infrastructure.

Usage:
    from spiderfoot.api.audit_middleware import install_audit_logging
    install_audit_logging(app)

Configuration:
    SF_API_AUDIT_ENABLED  — Enable/disable audit logging (default: true)
    SF_API_AUDIT_BODY     — Log request body for write methods (default: false)
    SF_API_AUDIT_EXCLUDE  — Comma-separated paths to exclude (default: /health,/metrics)
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger("spiderfoot.api.audit")

# Paths to exclude from audit logging (high-frequency probes)
_DEFAULT_EXCLUDES = {"/health", "/health/live", "/health/ready", "/health/startup", "/metrics"}


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that logs every API request for audit purposes.

    Each log entry includes:
    - method (GET, POST, etc.)
    - path
    - query string
    - status code
    - duration_ms
    - client IP
    - user agent
    - request ID (from tracing middleware)
    - user identity (from auth header, redacted)
    """

    def __init__(self, app: Any, exclude_paths: set[str] | None = None, log_body: bool = False) -> None:
        super().__init__(app)
        env_excludes = os.environ.get("SF_API_AUDIT_EXCLUDE", "")
        if env_excludes:
            self._exclude = {p.strip() for p in env_excludes.split(",")} | _DEFAULT_EXCLUDES
        else:
            self._exclude = exclude_paths or _DEFAULT_EXCLUDES
        self._log_body = log_body or os.environ.get("SF_API_AUDIT_BODY", "").lower() in ("1", "true")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip excluded paths
        path = request.url.path
        if path in self._exclude:
            return await call_next(request)

        start = time.monotonic()
        request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id", "")

        # Extract user identity (redacted)
        auth_header = request.headers.get("authorization", "")
        user_ident = self._extract_identity(auth_header)

        # Read body for write methods if enabled
        body_snippet = ""
        if self._log_body and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                body = await request.body()
                body_str = body.decode("utf-8", errors="replace")
                body_snippet = body_str[:500]  # Truncate large bodies
            except Exception:
                body_snippet = "<unreadable>"

        # Process request
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            status_code = 500
            raise
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            log_data = {
                "event": "api_request",
                "method": request.method,
                "path": path,
                "query": str(request.url.query) if request.url.query else "",
                "status": status_code,
                "duration_ms": duration_ms,
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent", "")[:200],
                "request_id": request_id,
                "user": user_ident,
            }
            if body_snippet:
                log_data["body_preview"] = body_snippet

            # Log at appropriate level
            if status_code >= 500:
                log.error("API request: %(method)s %(path)s → %(status)s (%(duration_ms)sms)", log_data, extra=log_data)
            elif status_code >= 400:
                log.warning("API request: %(method)s %(path)s → %(status)s (%(duration_ms)sms)", log_data, extra=log_data)
            else:
                log.info("API request: %(method)s %(path)s → %(status)s (%(duration_ms)sms)", log_data, extra=log_data)

    @staticmethod
    def _extract_identity(auth_header: str) -> str:
        """Extract a safe identity string from the Authorization header."""
        if not auth_header:
            return "anonymous"
        lower = auth_header.lower()
        if lower.startswith("bearer "):
            token = auth_header[7:]
            # For service tokens: show service name
            if ":" in token:
                parts = token.split(":")
                return f"service:{parts[0]}"
            # For API keys: show first 8 chars
            if len(token) > 8:
                return f"bearer:{token[:8]}..."
            return "bearer:***"
        if lower.startswith("basic "):
            return "basic:***"
        return "unknown"

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For behind a proxy."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        if request.client:
            return request.client.host
        return "unknown"


def install_audit_logging(app: Any, **kwargs) -> None:
    """Install the audit logging middleware on a FastAPI/Starlette app."""
    enabled = os.environ.get("SF_API_AUDIT_ENABLED", "true").lower()
    if enabled in ("0", "false", "no", "off"):
        log.info("API audit logging disabled via SF_API_AUDIT_ENABLED")
        return
    app.add_middleware(AuditLoggingMiddleware, **kwargs)
    log.info("API audit logging middleware installed")
