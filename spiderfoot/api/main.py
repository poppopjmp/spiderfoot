"""
Main FastAPI app instance for SpiderFoot API (modular)

Routes are mounted under both /api/v1/... (canonical) and /api/... (legacy,
backwards-compatible).  The ApiVersionMiddleware adds X-API-Version and
Deprecation headers so clients can migrate at their own pace.
"""
from fastapi import FastAPI
from .routers import scan, workspace, config, data, websocket, visualization, correlations, rag_correlation, reports, health, scan_progress, tasks, webhooks
from spiderfoot import __version__

# Security imports
from spiderfoot.security_middleware import install_fastapi_security
from spiderfoot.secure_config import SecureConfigManager

# Request tracing
from spiderfoot.request_tracing import install_tracing_middleware

# Rate limiting
from spiderfoot.api.rate_limit_middleware import install_rate_limiting

# Structured error responses
from spiderfoot.api.error_handlers import install_error_handlers

# API versioning
from spiderfoot.api.versioning import mount_versioned_routers, install_api_versioning

app = FastAPI(
    title="SpiderFoot API",
    description="Complete REST API for SpiderFoot OSINT automation platform",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Initialize security (will be done by main application, but provide fallback)
def initialize_security(config):
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

# Install rate limiting middleware (after tracing so 429s get request IDs)
install_rate_limiting(app)

# Install structured error handlers (after all middleware so errors get request IDs)
install_error_handlers(app)
