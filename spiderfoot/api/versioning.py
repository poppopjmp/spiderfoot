"""
API versioning support for SpiderFoot.

Provides:
- Version-prefixed route mounting (/api/v1/...)
- Backwards-compatible /api/... redirects
- Version negotiation via Accept-Version header
- Deprecation warning headers for unversioned routes

Usage:
    from spiderfoot.api.versioning import mount_versioned_routers
    mount_versioned_routers(app, routers)
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

log = logging.getLogger("spiderfoot.api.versioning")

# Current and supported API versions
CURRENT_API_VERSION = "v1"
SUPPORTED_VERSIONS = ["v1"]

# Routes that should NOT be versioned (health probes, metrics, docs)
UNVERSIONED_PREFIXES = ("/health", "/metrics", "/api/docs", "/api/redoc",
                        "/api/openapi.json", "/ws")


class ApiVersionMiddleware(BaseHTTPMiddleware):
    """Middleware that:
    1. Adds X-API-Version response header to all versioned responses.
    2. Adds Deprecation warning header for requests using unversioned
       /api/* paths (excluding docs/health).
    3. Recognises Accept-Version header for future version negotiation.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add API version headers to responses."""
        path = request.url.path

        # Skip non-API routes
        is_api = path.startswith("/api") or path.startswith("/ws")
        if not is_api:
            return await call_next(request)

        # Skip unversioned special routes
        for prefix in UNVERSIONED_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        response = await call_next(request)

        # Always declare the version that served the request
        response.headers["X-API-Version"] = CURRENT_API_VERSION

        # If client used legacy /api/... path (no /v1/), add deprecation hint
        if path.startswith("/api/") and not path.startswith(f"/api/{CURRENT_API_VERSION}"):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = "2026-01-01"
            response.headers["Link"] = (
                f'</api/{CURRENT_API_VERSION}{path[4:]}>; rel="successor-version"'
            )

        # Log Accept-Version header if provided (for future negotiation)
        accept_version = request.headers.get("Accept-Version")
        if accept_version and accept_version not in SUPPORTED_VERSIONS:
            log.warning("Client requested unsupported API version: %s", accept_version)

        return response


def create_versioned_router() -> APIRouter:
    """Create the top-level v1 router that all domain routers attach to."""
    return APIRouter(prefix=f"/api/{CURRENT_API_VERSION}")


def mount_versioned_routers(
    app: FastAPI,
    router_configs: list[tuple[APIRouter, str, list[str]]],
    *,
    keep_legacy: bool = True,
) -> None:
    """Mount routers under both /api/v1/ and (optionally) legacy /api/.

    Args:
        app: FastAPI application instance.
        router_configs: List of (router, prefix, tags) tuples.
            prefix is the mount prefix (e.g. "/api" for REST routers).
        keep_legacy: If True, also mount under /api/ for backwards compat.
    """
    for router, prefix, tags in router_configs:
        # Determine versioned prefix
        if prefix == "/api":
            versioned_prefix = f"/api/{CURRENT_API_VERSION}"
        elif prefix == "/ws":
            versioned_prefix = f"/ws/{CURRENT_API_VERSION}"
        else:
            # No prefix or special prefix — mount as-is
            app.include_router(router, prefix=prefix, tags=tags)
            continue

        # Mount versioned route
        app.include_router(router, prefix=versioned_prefix, tags=tags)

        # Also mount legacy route for backwards compatibility
        if keep_legacy:
            app.include_router(router, prefix=prefix, tags=tags)

    log.info(
        "API versioning enabled: current=%s, supported=%s, legacy=%s",
        CURRENT_API_VERSION, SUPPORTED_VERSIONS, keep_legacy,
    )


def install_api_versioning(app: FastAPI) -> None:
    """Install the API version middleware on the app."""
    app.add_middleware(ApiVersionMiddleware)
    log.info("API version middleware installed")


def get_version_info() -> dict:
    """Return API version metadata for health/info endpoints."""
    return {
        "current": CURRENT_API_VERSION,
        "supported": SUPPORTED_VERSIONS,
        "deprecated": [],
    }
