"""
Request body size limiting middleware.

Protects the API from excessively large request payloads that could
exhaust memory or be used in denial-of-service attacks.

Configuration:
    SF_API_MAX_BODY_SIZE  — Maximum body size in bytes (default: 10MB)
    SF_API_MAX_UPLOAD_SIZE — Maximum file upload size (default: 50MB)

Usage::

    from spiderfoot.api.body_limit_middleware import install_body_limits
    install_body_limits(app)
"""
from __future__ import annotations

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger("spiderfoot.api.body_limit")

# Default limits
_DEFAULT_MAX_BODY = 10 * 1024 * 1024       # 10 MB
_DEFAULT_MAX_UPLOAD = 50 * 1024 * 1024     # 50 MB

# Paths that handle file uploads (higher limit)
_UPLOAD_PATHS = {
    "/workspaces/import",
    "/config/import",
}


def _parse_size(value: str, default: int) -> int:
    """Parse a size string like '10MB', '1GB', or plain bytes."""
    if not value:
        return default
    value = value.strip().upper()
    multipliers = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}
    for suffix, mult in multipliers.items():
        if value.endswith(suffix):
            try:
                return int(float(value[:-len(suffix)]) * mult)
            except ValueError:
                return default
    try:
        return int(value)
    except ValueError:
        return default


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with Content-Length exceeding configured limits."""

    def __init__(self, app, max_body: int = _DEFAULT_MAX_BODY, max_upload: int = _DEFAULT_MAX_UPLOAD):
        super().__init__(app)
        self._max_body = _parse_size(
            os.environ.get("SF_API_MAX_BODY_SIZE", ""), max_body
        )
        self._max_upload = _parse_size(
            os.environ.get("SF_API_MAX_UPLOAD_SIZE", ""), max_upload
        )
        log.info(
            "Body size limits: general=%s bytes, upload=%s bytes",
            self._max_body, self._max_upload,
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Only check methods that can have bodies
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length is None:
            # No Content-Length header — let it through (chunked encoding handled by server)
            return await call_next(request)

        try:
            size = int(content_length)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INVALID_CONTENT_LENGTH", "message": "Invalid Content-Length header"}},
            )

        # Determine limit based on path
        path = request.url.path
        is_upload = any(path.endswith(p) or p in path for p in _UPLOAD_PATHS)
        limit = self._max_upload if is_upload else self._max_body

        if size > limit:
            limit_mb = limit / (1024 * 1024)
            size_mb = size / (1024 * 1024)
            log.warning(
                "Request body too large: %.1f MB > %.1f MB limit (%s %s)",
                size_mb, limit_mb, request.method, path,
            )
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "PAYLOAD_TOO_LARGE",
                        "message": f"Request body size ({size_mb:.1f} MB) exceeds limit ({limit_mb:.1f} MB)",
                        "limit_bytes": limit,
                        "actual_bytes": size,
                    }
                },
            )

        return await call_next(request)


def install_body_limits(app, **kwargs) -> None:
    """Install the body size limiting middleware on a FastAPI/Starlette app."""
    app.add_middleware(BodySizeLimitMiddleware, **kwargs)
    log.info("Body size limiting middleware installed")
