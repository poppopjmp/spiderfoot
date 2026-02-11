"""Backward-compatibility shim for security_middleware.py.

This module re-exports from security/security_middleware.py for backward compatibility.
"""

from __future__ import annotations

from .security.security_middleware import (
    SecurityConfigDefaults,
    SpiderFootSecurityMiddleware,
    CherryPySecurityTool,
    FastAPISecurityMiddleware,
    create_security_config,
    validate_security_config,
    get_security_status,
    install_cherrypy_security,
    install_fastapi_security,
)

__all__ = [
    "SecurityConfigDefaults",
    "SpiderFootSecurityMiddleware",
    "CherryPySecurityTool",
    "FastAPISecurityMiddleware",
    "create_security_config",
    "validate_security_config",
    "get_security_status",
    "install_cherrypy_security",
    "install_fastapi_security",
]
