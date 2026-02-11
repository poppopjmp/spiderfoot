"""SpiderFoot security subpackage.

This subpackage contains authentication, authorization, CSRF protection,
security middleware, and logging components.

Usage::

    from spiderfoot.security import AuthGuard, CSRFProtection
    from spiderfoot.security import SpiderFootSecurityMiddleware
"""

from __future__ import annotations

# Authentication
from .auth import (
    AuthConfig,
    AuthGuard,
    AuthMethod,
    AuthResult,
    Role,
)

# CSRF protection
from .csrf_protection import (
    CSRFProtection,
    CSRFTool,
    csrf_protect,
    csrf_token,
    init_csrf_protection,
)

# Security compatibility
from .security_compat import (
    RequestContext,
    get_request_context,
    json_error_response,
)

# Security integration
from .security_integration import SecurityIntegrator

# Security logging
from .security_logging import (
    ErrorHandler,
    SecurityEventType,
    SecurityLogger,
    SecurityMonitor,
    handle_error,
    log_security_event,
)

# Security middleware
from .security_middleware import (
    CherryPySecurityTool,
    FastAPISecurityMiddleware,
    SecurityConfigDefaults,
    SpiderFootSecurityMiddleware,
    create_security_config,
    get_security_status,
    install_cherrypy_security,
    install_fastapi_security,
    validate_security_config,
)

# Service authentication
from .service_auth import (
    ServiceTokenIssuer,
    ServiceTokenValidator,
    TokenValidationResult,
    generate_service_secret,
)

__all__ = [
    # Authentication
    "AuthConfig",
    "AuthGuard",
    "AuthMethod",
    "AuthResult",
    "Role",
    # CSRF protection
    "CSRFProtection",
    "CSRFTool",
    "csrf_protect",
    "csrf_token",
    "init_csrf_protection",
    # Security compatibility
    "RequestContext",
    "get_request_context",
    "json_error_response",
    # Security integration
    "SecurityIntegrator",
    # Security logging
    "ErrorHandler",
    "SecurityEventType",
    "SecurityLogger",
    "SecurityMonitor",
    "handle_error",
    "log_security_event",
    # Security middleware
    "CherryPySecurityTool",
    "FastAPISecurityMiddleware",
    "SecurityConfigDefaults",
    "SpiderFootSecurityMiddleware",
    "create_security_config",
    "get_security_status",
    "install_cherrypy_security",
    "install_fastapi_security",
    "validate_security_config",
    # Service authentication
    "ServiceTokenIssuer",
    "ServiceTokenValidator",
    "TokenValidationResult",
    "generate_service_secret",
]
