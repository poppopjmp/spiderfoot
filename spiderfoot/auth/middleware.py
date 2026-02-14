# -*- coding: utf-8 -*-
"""
FastAPI authentication middleware for SpiderFoot.

Intercepts every request, validates JWT tokens from the Authorization header,
and sets ``request.state.user`` with a ``UserContext`` for downstream RBAC checks.

Public paths (health, docs, login, SSO callbacks) bypass auth.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from spiderfoot.auth.models import AuthConfig
from spiderfoot.rbac import Role, UserContext, parse_role

log = logging.getLogger("spiderfoot.auth.middleware")

# Paths that never require authentication
PUBLIC_PATHS = frozenset({
    "/health",
    "/healthz",
    "/ready",
    "/api/health",
    "/api/healthz",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/status",
    "/api/auth/sso/providers",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/status",
    "/api/v1/auth/sso/providers",
})

# Path prefixes that are public
PUBLIC_PREFIXES = (
    "/api/auth/sso/callback/",
    "/api/auth/sso/saml/acs/",
    "/api/auth/sso/oauth2/login/",
    "/api/v1/auth/sso/callback/",
    "/api/v1/auth/sso/saml/acs/",
    "/api/v1/auth/sso/oauth2/login/",
    "/static/",
    "/spiderfoot-icon",
    "/favicon",
    "/assets/",
)


def _is_public_path(path: str) -> bool:
    """Check if a path is public (no auth required)."""
    if path in PUBLIC_PATHS:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that validates JWT tokens and sets request.state.user."""

    def __init__(self, app, auth_config: AuthConfig | None = None):
        super().__init__(app)
        self.config = auth_config or AuthConfig()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Skip auth for public paths
        if _is_public_path(path):
            request.state.user = None
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

        # Also check query param (for backward compat)
        if not token:
            token = request.query_params.get("api_key", "")

        if token:
            try:
                from spiderfoot.auth.service import get_auth_service
                auth_svc = get_auth_service()
                user_ctx = auth_svc.token_to_user_context(token)
                request.state.user = user_ctx
            except Exception as e:
                log.debug("Token validation failed: %s", e)
                request.state.user = None

                if self.config.auth_required:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": {
                                "code": "UNAUTHORIZED",
                                "message": "Invalid or expired token",
                            }
                        },
                    )
        else:
            request.state.user = None

            if self.config.auth_required and not _is_public_path(path):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "UNAUTHORIZED",
                            "message": "Authentication required",
                        }
                    },
                )

        return await call_next(request)


def install_auth_middleware(app, config: AuthConfig | None = None) -> None:
    """Install the auth middleware on a FastAPI app."""
    cfg = config or AuthConfig()
    app.add_middleware(AuthMiddleware, auth_config=cfg)
    log.info(
        "Auth middleware installed (auth_required=%s, rbac_enforce=%s)",
        cfg.auth_required,
        cfg.rbac_enforce,
    )
