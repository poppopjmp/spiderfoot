"""Backward-compatibility shim for module_timeout.py.

This module re-exports from plugins/module_timeout.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_timeout import (
    ModuleTimeoutGuard,
    TimeoutRecord,
    get_timeout_guard,
)

__all__ = [
    "ModuleTimeoutGuard",
    "TimeoutRecord",
    "get_timeout_guard",
]
