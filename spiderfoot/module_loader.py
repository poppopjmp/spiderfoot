"""Backward-compatibility shim for module_loader.py.

This module re-exports from plugins/module_loader.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_loader import (
    LoadResult,
    ModuleLoader,
    get_module_loader,
    init_module_loader,
    reset_module_loader,
)

__all__ = [
    "LoadResult",
    "ModuleLoader",
    "get_module_loader",
    "init_module_loader",
    "reset_module_loader",
]
