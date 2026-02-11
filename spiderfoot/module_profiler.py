"""Backward-compatibility shim for module_profiler.py.

This module re-exports from plugins/module_profiler.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_profiler import (
    MethodProfile,
    ModuleProfile,
    ModuleProfiler,
    get_module_profiler,
)

__all__ = [
    "MethodProfile",
    "ModuleProfile",
    "ModuleProfiler",
    "get_module_profiler",
]
