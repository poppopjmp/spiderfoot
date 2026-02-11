"""Backward-compatibility shim for async_plugin.py.

This module re-exports from plugins/async_plugin.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.async_plugin import (
    AsyncResult,
    SpiderFootAsyncPlugin,
    get_event_loop,
    shutdown_event_loop,
)

__all__ = [
    "AsyncResult",
    "SpiderFootAsyncPlugin",
    "get_event_loop",
    "shutdown_event_loop",
]
