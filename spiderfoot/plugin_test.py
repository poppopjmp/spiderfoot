"""Backward-compatibility shim for plugin_test.py.

This module re-exports from plugins/plugin_test.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.plugin_test import (
    EventCapture,
    FakeSpiderFoot,
    FakeTarget,
    PluginTestHarness,
    make_event,
    make_root_event,
)

__all__ = [
    "EventCapture",
    "FakeSpiderFoot",
    "FakeTarget",
    "PluginTestHarness",
    "make_event",
    "make_root_event",
]
