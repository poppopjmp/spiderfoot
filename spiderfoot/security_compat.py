"""
Framework-agnostic request/response abstractions for security modules.

Provides a thin adapter layer so security middleware can work with
both Flask and FastAPI/Starlette without importing either directly.

Security modules should use these abstractions instead of importing
``flask.request``, ``flask.g``, ``flask.jsonify`` etc. directly.

Usage::

    from spiderfoot.security_compat import get_request_context

    ctx = get_request_context(request)  # works with Flask or Starlette
    client_ip = ctx.client_ip
    auth_header = ctx.get_header("Authorization")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict

log = logging.getLogger("spiderfoot.security_compat")


@dataclass
class RequestContext:
    """Framework-agnostic request context for security modules."""

    client_ip: str = "127.0.0.1"
    method: str = "GET"
    path: str = "/"
    headers: dict[str, str] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    _raw_request: Any = None

    def get_header(self, name: str, default: str = "") -> str:
        """Get a request header (case-insensitive)."""
        name_lower = name.lower()
        for k, v in self.headers.items():
            if k.lower() == name_lower:
                return v
        return default

    @property
    def authorization(self) -> str:
        """Get the Authorization header."""
        return self.get_header("Authorization")

    @property
    def content_type(self) -> str:
        """Get the Content-Type header."""
        return self.get_header("Content-Type")

    @property
    def user_agent(self) -> str:
        """Get the User-Agent header."""
        return self.get_header("User-Agent")


def get_request_context(request: Any) -> RequestContext:
    """Build a framework-agnostic RequestContext from a raw request.

    Supports:
    - Flask ``request`` object
    - Starlette/FastAPI ``Request`` object
    - Plain dict (for testing)

    Args:
        request: The raw framework request object.

    Returns:
        A ``RequestContext`` instance.
    """
    if request is None:
        return RequestContext()

    # Dict-based (testing)
    if isinstance(request, dict):
        return RequestContext(
            client_ip=request.get("client_ip", "127.0.0.1"),
            method=request.get("method", "GET"),
            path=request.get("path", "/"),
            headers=request.get("headers", {}),
            state=request.get("state", {}),
            _raw_request=request,
        )

    # Starlette/FastAPI Request
    if hasattr(request, "client") and hasattr(request, "scope"):
        headers = dict(request.headers) if hasattr(request, "headers") else {}
        client_ip = "127.0.0.1"
        if request.client:
            client_ip = request.client.host
        # Check X-Forwarded-For
        xff = headers.get("x-forwarded-for", "")
        if xff:
            client_ip = xff.split(",")[0].strip()
        return RequestContext(
            client_ip=client_ip,
            method=request.method,
            path=str(request.url.path) if hasattr(request.url, "path") else "/",
            headers=headers,
            state=dict(getattr(request, "state", {})) if hasattr(request.state, "__dict__") else {},
            _raw_request=request,
        )

    # Flask request (has .remote_addr, .environ)
    if hasattr(request, "remote_addr") and hasattr(request, "environ"):
        headers = {}
        if hasattr(request, "headers"):
            headers = dict(request.headers)
        return RequestContext(
            client_ip=getattr(request, "remote_addr", "127.0.0.1") or "127.0.0.1",
            method=getattr(request, "method", "GET"),
            path=getattr(request, "path", "/"),
            headers=headers,
            state={},
            _raw_request=request,
        )

    # Fallback
    return RequestContext(_raw_request=request)


def json_error_response(message: str, status_code: int = 400) -> dict[str, Any]:
    """Create a JSON error response dict.

    Returns a plain dict that can be used by both Flask (``jsonify()``)
    and FastAPI (return directly from endpoint).

    Args:
        message: Error message.
        status_code: HTTP status code.

    Returns:
        Dict with ``error`` and ``status_code`` keys.
    """
    return {
        "error": message,
        "status_code": status_code,
    }
