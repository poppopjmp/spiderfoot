"""Backward-compatibility shim for module_resolver.py.

This module re-exports from plugins/module_resolver.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_resolver import (
    Dependency,
    DepKind,
    ModuleDescriptor,
    ModuleResolver,
    ResolutionResult,
    ResolveStatus,
)

__all__ = [
    "Dependency",
    "DepKind",
    "ModuleDescriptor",
    "ModuleResolver",
    "ResolutionResult",
    "ResolveStatus",
]
