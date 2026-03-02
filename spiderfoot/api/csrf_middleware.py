"""
CSRF protection middleware for FastAPI.

Protects state-changing endpoints (POST/PUT/PATCH/DELETE) against
Cross-Site Request Forgery by requiring a custom header that browsers
will not attach to cross-origin requests without explicit CORS permission.

Strategy: **custom-header check** — the simplest CSRF mitigation for
JSON/GraphQL APIs.  Any request with a state-changing method must include
either:
    X-Requested-With: <any-non-empty-value>   (commonly "XMLHttpRequest")
    X-SF-CSRF: 1                               (SpiderFoot-specific)

Additionally, WebSocket upgrade requests are validated against a
configurable set of allowed origins to prevent cross-site WebSocket
hijacking.

See OWASP: https://cheatsheetseries.owasp.org/cheatsheets/
    Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html#use-of-custom-request-headers
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Sequence
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_log = logging.getLogger("spiderfoot.api.csrf")

# HTTP methods that are considered "safe" (read-only) and exempt from CSRF
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# Accepted custom headers — presence of *any* of these satisfies the check
_CSRF_HEADERS = ("x-requested-with", "x-sf-csrf")


@dataclass
class CSRFConfig:
    """CSRF middleware configuration.

    Attributes:
        enabled: Master switch — disable in dev/test if needed.
        protected_paths: Path prefixes that require CSRF validation.
            Default: ``["/api/graphql"]``.
        exempt_paths: Exact paths exempt from CSRF even under protected prefixes.
        allowed_origins: Origins allowed for WebSocket upgrade requests.
            Derived from ``SF_CSRF_ALLOWED_ORIGINS`` env var (comma-separated).
    """

    enabled: bool = True
    protected_paths: list[str] = field(
        default_factory=lambda: ["/api/"],
    )
    exempt_paths: set[str] = field(
        default_factory=lambda: {
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/refresh",
            "/api/auth/sso/callback",
            "/api/health",
            "/api/version",
        },
    )
    allowed_origins: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> CSRFConfig:
        """Build config from environment variables."""
        enabled = os.environ.get("SF_CSRF_ENABLED", "true").lower() not in (
            "0", "false", "no",
        )
        origins_raw = os.environ.get("SF_CSRF_ALLOWED_ORIGINS", "")
        origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
        return cls(enabled=enabled, allowed_origins=origins)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Starlette middleware enforcing CSRF custom-header checks."""

    def __init__(self, app, config: CSRFConfig | None = None) -> None:
        super().__init__(app)
        self.config = config or CSRFConfig.from_env()
        if self.config.enabled:
            _log.info(
                "CSRF middleware active — protecting %s",
                self.config.protected_paths,
            )

    # ------------------------------------------------------------------

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        if not self.config.enabled:
            return await call_next(request)

        path = request.url.path

        # Only check paths under protected prefixes
        if not self._is_protected(path):
            return await call_next(request)

        # Exempt exact paths (e.g. /api/graphql/schema)
        if path in self.config.exempt_paths:
            return await call_next(request)

        # --- WebSocket upgrade: validate Origin ---
        if self._is_ws_upgrade(request):
            if not self._validate_ws_origin(request):
                _log.warning(
                    "CSRF: rejected WebSocket upgrade from origin=%s path=%s",
                    request.headers.get("origin", "<none>"),
                    path,
                )
                return JSONResponse(
                    {"error": "WebSocket CSRF origin rejected"},
                    status_code=403,
                )
            return await call_next(request)

        # --- Safe methods pass through ---
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        # --- State-changing methods: require custom header ---
        if not self._has_csrf_header(request):
            _log.warning(
                "CSRF: missing custom header on %s %s (client=%s)",
                request.method,
                path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                {
                    "error": {
                        "code": "CSRF_VALIDATION_FAILED",
                        "message": (
                            "State-changing requests to this endpoint require "
                            "a custom header: X-Requested-With or X-SF-CSRF."
                        ),
                    }
                },
                status_code=403,
            )

        return await call_next(request)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_protected(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.config.protected_paths)

    @staticmethod
    def _has_csrf_header(request: Request) -> bool:
        for h in _CSRF_HEADERS:
            val = request.headers.get(h)
            if val and val.strip():
                return True
        return False

    @staticmethod
    def _is_ws_upgrade(request: Request) -> bool:
        return request.headers.get("upgrade", "").lower() == "websocket"

    def _validate_ws_origin(self, request: Request) -> bool:
        origin = request.headers.get("origin")
        if not origin:
            # No origin header — allow (same-origin, non-browser client)
            return True

        # If no allowed_origins configured, derive from Host header
        if not self.config.allowed_origins:
            host = request.headers.get("host", "")
            origin_host = urlparse(origin).netloc
            return origin_host == host

        origin_lower = origin.lower().rstrip("/")
        return any(
            origin_lower == allowed.lower().rstrip("/")
            for allowed in self.config.allowed_origins
        )


def install_csrf_protection(app, config: CSRFConfig | None = None) -> None:
    """Install CSRF middleware on a FastAPI/Starlette application."""
    cfg = config or CSRFConfig.from_env()
    app.add_middleware(CSRFMiddleware, config=cfg)
    _log.info("CSRF protection installed")
