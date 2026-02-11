"""Backward-compatibility shim for csrf_protection.py.

This module re-exports from security/csrf_protection.py for backward compatibility.
"""

from __future__ import annotations

from .security.csrf_protection import (
    CSRFProtection,
    CSRFTool,
    csrf_protect,
    csrf_token,
    init_csrf_protection,
)

__all__ = [
    "CSRFProtection",
    "CSRFTool",
    "csrf_protect",
    "csrf_token",
    "init_csrf_protection",
]
