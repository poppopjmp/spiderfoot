"""
Main FastAPI app instance for SpiderFoot API (modular)

Routes are mounted under both /api/v1/... (canonical) and /api/... (legacy,
backwards-compatible).  The ApiVersionMiddleware adds X-API-Version and
Deprecation headers so clients can migrate at their own pace.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from .routers import (
    scan, workspace, config, data, websocket,
    visualization, correlations, rag_correlation, reports,
    health, scan_progress, tasks, webhooks, export,
)
from spiderfoot import __version__

# Security imports
from spiderfoot.security_middleware import install_fastapi_security

# Request tracing
from spiderfoot.request_tracing import install_tracing_middleware

# Rate limiting
from spiderfoot.api.rate_limit_middleware import install_rate_limiting

# Structured error responses
from spiderfoot.api.error_handlers import install_error_handlers

# API request audit logging
from spiderfoot.api.audit_middleware import install_audit_logging

# Request body size limits
from spiderfoot.api.body_limit_middleware import install_body_limits

# CORS
from spiderfoot.api.cors_config import install_cors

# Response compression
from spiderfoot.api.compression_middleware import install_compression

# API versioning
from spiderfoot.api.versioning import mount_versioned_routers, install_api_versioning

# Graceful shutdown
from spiderfoot.graceful_shutdown import get_shutdown_coordinator

_log = logging.getLogger("spiderfoot.api")


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """FastAPI lifespan: register background services for graceful shutdown."""
    mgr = get_shutdown_coordinator()
    _log.info("API startup — shutdown coordinator has %d registered services",
              len(mgr.registered_services()))
    yield
    # On shutdown, run all registered cleanup callbacks
    results = mgr.shutdown(reason="fastapi_lifespan")
    _log.info("API shutdown completed: %s", results)


app = FastAPI(
    title="SpiderFoot API",
    description=(
        "Complete REST API for SpiderFoot OSINT automation platform.\n\n"
        "## Authentication\n"
        "Endpoints accept an `api_key` query parameter or `Authorization: Bearer <key>` header.\n\n"
        "## Versioning\n"
        "Canonical routes live under `/api/v1/`. Legacy `/api/` paths continue to work "
        "but include `Deprecation` headers — migrate when ready.\n\n"
        "## Error Responses\n"
        "All errors return a structured `{\"error\": {...}}` envelope with a "
        "machine-readable `code`, the originating `request_id`, and a `timestamp`."
    ),
    version=__version__,
    lifespan=_lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=[
        {"name": "health", "description": "Liveness, readiness, and version probes"},
        {"name": "scans", "description": "Create, list, manage, and export scans"},
        {"name": "workspaces", "description": "Workspace CRUD and membership"},
        {"name": "data", "description": "Raw event data and search"},
        {"name": "configuration", "description": "Global and per-module config, API keys, credentials"},
        {"name": "visualization", "description": "Graph, heatmap, and summary endpoints"},
        {"name": "correlations", "description": "Correlation rule CRUD and execution"},
        {"name": "rag-correlation", "description": "RAG-based correlation engine"},
        {"name": "reports", "description": "Report generation and retrieval"},
        {"name": "scan-progress", "description": "SSE scan progress streaming"},
        {"name": "tasks", "description": "Background task management"},
        {"name": "webhooks", "description": "Outbound webhook configuration"},
        {"name": "websockets", "description": "Real-time event streaming via WebSocket"},
    ],
)

# Initialize security (will be done by main application, but provide fallback)
def initialize_security(config: dict) -> object | None:
    """Initialize security middleware for FastAPI."""
    try:
        return install_fastapi_security(app, config)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to initialize API security: {e}")
        return None

# ── Router configuration ──────────────────────────────────────────────
# Each tuple: (router, prefix, tags)
# Versioned routers are mounted under /api/v1/ AND legacy /api/
_VERSIONED_ROUTERS = [
    (scan.router,             "/api", ["scans"]),
    (workspace.router,        "/api", ["workspaces"]),
    (data.router,             "/api", ["data"]),
    (config.router,           "/api", ["configuration"]),
    (visualization.router,    "/api", ["visualization"]),
    (correlations.router,     "/api", ["correlations"]),
    (rag_correlation.router,  "/api", ["rag-correlation"]),
    (reports.router,          "/api", ["reports"]),
    (scan_progress.router,    "/api", ["scan-progress"]),
    (tasks.router,            "/api", ["tasks"]),
    (webhooks.router,         "/api", ["webhooks"]),
    (export.router,           "/api", ["scans"]),
    (websocket.router,        "/ws",  ["websockets"]),
]

# Mount versioned routers: /api/v1/... + legacy /api/...
mount_versioned_routers(app, _VERSIONED_ROUTERS, keep_legacy=True)

# Health/metrics are unversioned (Kubernetes probes expect stable paths)
app.include_router(health.router, tags=["health"])

# Install API versioning middleware (adds X-API-Version, Deprecation headers)
install_api_versioning(app)

# Install request tracing middleware (must be before security middleware
# so that every request gets a correlation ID regardless of auth outcome)
install_tracing_middleware(app)

# Install body size limits (before rate limiting to reject oversized payloads early)
install_body_limits(app)

# Install rate limiting middleware (after tracing so 429s get request IDs)
install_rate_limiting(app)

# Install structured error handlers (after all middleware so errors get request IDs)
install_error_handlers(app)

# Install audit logging middleware (outermost — captures final status after error handlers)
install_audit_logging(app)

# Install response compression (compress large JSON responses)
install_compression(app)

# Install CORS (must be last middleware added — runs first in ASGI onion)
install_cors(app)
