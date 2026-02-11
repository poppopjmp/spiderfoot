"""Backward-compatibility shim for auth.py.

This module re-exports from security/auth.py for backward compatibility.
"""

from __future__ import annotations

from .security.auth import (
    AuthMethod,
    Role,
    AuthConfig,
    AuthResult,
    AuthGuard,
)

__all__ = [
    "AuthMethod",
    "Role",
    "AuthConfig",
    "AuthResult",
    "AuthGuard",
]
