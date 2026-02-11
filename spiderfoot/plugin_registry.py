"""Backward-compatibility shim for plugin_registry.py.

This module re-exports from plugins/plugin_registry.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.plugin_registry import (
    InstalledPlugin,
    PluginManifest,
    PluginRegistry,
    PluginStatus,
)

__all__ = [
    "InstalledPlugin",
    "PluginManifest",
    "PluginRegistry",
    "PluginStatus",
]
