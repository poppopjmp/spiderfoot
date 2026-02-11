"""Backward-compatibility shim for security_integration.py.

This module re-exports from security/security_integration.py for backward compatibility.
"""

from __future__ import annotations

from .security.security_integration import (
    SecurityIntegrator,
)

__all__ = [
    "SecurityIntegrator",
]
