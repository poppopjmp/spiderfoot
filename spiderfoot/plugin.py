"""Backward-compatibility shim for plugin.py.

This module re-exports from plugins/plugin.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.plugin import (
    SpiderFootPlugin,
    SpiderFootPluginLogger,
)

__all__ = [
    "SpiderFootPlugin",
    "SpiderFootPluginLogger",
]
