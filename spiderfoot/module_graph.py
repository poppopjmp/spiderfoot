"""Backward-compatibility shim for module_graph.py.

This module re-exports from plugins/module_graph.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_graph import (
    ModuleGraph,
    ModuleInfo,
)

__all__ = [
    "ModuleGraph",
    "ModuleInfo",
]
