"""Backward-compatibility shim for modern_plugin.py.

This module re-exports from plugins/modern_plugin.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.modern_plugin import (
    SpiderFootModernPlugin,
)

__all__ = [
    "SpiderFootModernPlugin",
]
