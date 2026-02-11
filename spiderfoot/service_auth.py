"""Backward-compatibility shim for service_auth.py.

This module re-exports from security/service_auth.py for backward compatibility.
"""

from __future__ import annotations

from .security.service_auth import (
    TokenValidationResult,
    ServiceTokenIssuer,
    ServiceTokenValidator,
    generate_service_secret,
)

__all__ = [
    "TokenValidationResult",
    "ServiceTokenIssuer",
    "ServiceTokenValidator",
    "generate_service_secret",
]
