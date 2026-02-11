"""Backward-compatibility shim for security_logging.py.

This module re-exports from security/security_logging.py for backward compatibility.
"""

from __future__ import annotations

from .security.security_logging import (
    SecurityEventType,
    SecurityLogger,
    ErrorHandler,
    SecurityMonitor,
    log_security_event,
    handle_error,
)

__all__ = [
    "SecurityEventType",
    "SecurityLogger",
    "ErrorHandler",
    "SecurityMonitor",
    "log_security_event",
    "handle_error",
]
