"""Backward-compatibility shim for module_deps.py.

This module re-exports from plugins/module_deps.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_deps import (
    DepEdge,
    DepStatus,
    ModuleDependencyResolver,
    ModuleNode,
    ResolutionResult,
)

__all__ = [
    "DepEdge",
    "DepStatus",
    "ModuleDependencyResolver",
    "ModuleNode",
    "ResolutionResult",
]
