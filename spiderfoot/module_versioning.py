"""Backward-compatibility shim for module_versioning.py.

This module re-exports from plugins/module_versioning.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_versioning import (
    ChangelogEntry,
    ModuleVersionInfo,
    ModuleVersionRegistry,
    SemanticVersion,
    VersionBump,
    VersionConstraint,
)

__all__ = [
    "ChangelogEntry",
    "ModuleVersionInfo",
    "ModuleVersionRegistry",
    "SemanticVersion",
    "VersionBump",
    "VersionConstraint",
]
