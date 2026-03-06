"""DEPRECATED - merged into spiderfoot.api.error_handlers.

All public symbols are re-exported for backward compatibility.
New code should import from ``spiderfoot.api.error_handlers`` directly.
"""
from spiderfoot.api.error_handlers import (  # noqa: F401
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    api_error,
    error_response,
    install_error_handlers,
    register_error_handlers,
)

__all__ = [
    "ErrorCode",
    "ErrorDetail",
    "ErrorResponse",
    "api_error",
    "error_response",
    "install_error_handlers",
    "register_error_handlers",
]
