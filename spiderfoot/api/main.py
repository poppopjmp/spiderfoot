"""
Main FastAPI app instance for SpiderFoot API (modular)
"""
from fastapi import FastAPI
from .routers import scan, workspace, config, data, websocket, visualization, correlations
from spiderfoot import __version__

# Security imports
from spiderfoot.security_middleware import install_fastapi_security
from spiderfoot.secure_config import SecureConfigManager

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

# Include routers
app.include_router(scan.router, prefix="/api", tags=["scans"])
app.include_router(workspace.router, prefix="/api", tags=["workspaces"])
app.include_router(data.router, prefix="/api", tags=["data"])
app.include_router(config.router, prefix="/api", tags=["configuration"])
app.include_router(visualization.router, prefix="/api", tags=["visualization"])
app.include_router(correlations.router, prefix="/api", tags=["correlations"])
app.include_router(websocket.router, prefix="/ws", tags=["websockets"])
