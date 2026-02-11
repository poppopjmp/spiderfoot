"""Backward-compatibility shim for security_compat.py.

This module re-exports from security/security_compat.py for backward compatibility.
"""

from __future__ import annotations

from .security.security_compat import (
    RequestContext,
    get_request_context,
    json_error_response,
)

__all__ = [
    "RequestContext",
    "get_request_context",
    "json_error_response",
]
