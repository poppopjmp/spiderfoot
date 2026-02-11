"""Backward-compatibility shim for module_output_validator.py.

This module re-exports from plugins/module_output_validator.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_output_validator import (
    ModuleOutputValidator,
    UndeclaredEventError,
    ValidationStats,
    get_output_validator,
)

__all__ = [
    "ModuleOutputValidator",
    "UndeclaredEventError",
    "ValidationStats",
    "get_output_validator",
]
