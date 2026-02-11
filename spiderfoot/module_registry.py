"""Backward-compatibility shim for module_registry.py.

This module re-exports from plugins/module_registry.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_registry import (
    DiscoveryResult,
    ModuleDescriptor,
    ModuleRegistry,
    ModuleStatus,
)

__all__ = [
    "DiscoveryResult",
    "ModuleDescriptor",
    "ModuleRegistry",
    "ModuleStatus",
]
