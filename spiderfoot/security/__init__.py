"""
SpiderFoot Security — auth, CSRF, input validation, session, and secret management.

This sub-package groups security-related modules for cleaner imports.

Usage::

    from spiderfoot.security import auth, secret_manager
    from spiderfoot.security.auth import require_auth
"""

__all__ = [
    "auth",
    "api_security",
    "csrf_protection",
    "input_validation",
    "secret_manager",
    "secure_config",
    "security_compat",
    "security_logging",
    "security_middleware",
    "session_security",
    "web_security",
    "audit_log",
]
