"""
Response compression middleware for SpiderFoot API.

Adds transparent gzip compression to API responses that exceed a
configurable size threshold.  Respects the client's Accept-Encoding
header and skips already-compressed or streaming responses.

Configuration via environment variables:
    SF_API_COMPRESS_MIN_SIZE   — minimum response body size in bytes to
                                  compress (default: 1024)
    SF_API_COMPRESS_LEVEL      — gzip compression level 1-9 (default: 6)

Usage:
    from spiderfoot.api.compression_middleware import install_compression

    install_compression(app)
"""
from __future__ import annotations

import gzip
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from typing import Any, Callable

log = logging.getLogger("spiderfoot.api.compression")

# Defaults
_DEFAULT_MIN_SIZE = 1024   # bytes
_DEFAULT_LEVEL = 6         # gzip level (1=fast, 9=best)

# Content types eligible for compression
_COMPRESSIBLE_TYPES = {
    "application/json",
    "application/x-ndjson",
    "text/plain",
    "text/csv",
    "text/html",
    "application/xml",
    "application/stix+json",
    "application/sarif+json",
}


def _is_compressible(content_type: str) -> bool:
    """Check if the content type is eligible for compression."""
    if not content_type:
        return False
    # Strip parameters (charset, etc.)
    base_type = content_type.split(";")[0].strip().lower()
    return base_type in _COMPRESSIBLE_TYPES


class CompressionMiddleware(BaseHTTPMiddleware):
    """Middleware that gzip-compresses eligible responses.

    Only compresses when:
    - Client sends Accept-Encoding: gzip
    - Response body exceeds min_size bytes
    - Content type is compressible
    - Response is not already encoded
    - Response is not a streaming response
    """

    def __init__(self, app: Any, *, min_size: int = _DEFAULT_MIN_SIZE, level: int = _DEFAULT_LEVEL) -> None:
        """Initialize the CompressionMiddleware."""
        super().__init__(app)
        self.min_size = min_size
        self.level = max(1, min(9, level))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Compress response body with gzip if the client accepts it."""
        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return await call_next(request)

        response = await call_next(request)

        # Skip streaming responses (we can't easily buffer them)
        if isinstance(response, StreamingResponse):
            return response

        # Skip if already encoded
        if response.headers.get("content-encoding"):
            return response

        # Check content type
        content_type = response.headers.get("content-type", "")
        if not _is_compressible(content_type):
            return response

        # Read body
        body = b""
        if hasattr(response, "body"):
            body = response.body
        else:
            return response

        # Skip small responses
        if len(body) < self.min_size:
            return response

        # Compress
        compressed = gzip.compress(body, compresslevel=self.level)

        # Only use compressed version if it's actually smaller
        if len(compressed) >= len(body):
            return response

        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )


def install_compression(app: Any, *, min_size: int = None, level: int = None) -> None:
    """Install response compression middleware on the FastAPI app.

    Reads defaults from environment variables if not explicitly provided.
    """
    if min_size is None:
        min_size = int(os.environ.get("SF_API_COMPRESS_MIN_SIZE", _DEFAULT_MIN_SIZE))
    if level is None:
        level = int(os.environ.get("SF_API_COMPRESS_LEVEL", _DEFAULT_LEVEL))

    app.add_middleware(CompressionMiddleware, min_size=min_size, level=level)
    log.info("Response compression enabled (min_size=%d, level=%d)", min_size, level)
