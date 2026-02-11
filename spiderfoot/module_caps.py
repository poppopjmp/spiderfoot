"""Backward-compatibility shim for module_caps.py.

This module re-exports from plugins/module_caps.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_caps import (
    Capability,
    CapabilityCategory,
    CapabilityRegistry,
    ModuleCapabilityDeclaration,
    Requirement,
    get_capability_registry,
)

__all__ = [
    "Capability",
    "CapabilityCategory",
    "CapabilityRegistry",
    "ModuleCapabilityDeclaration",
    "Requirement",
    "get_capability_registry",
]
