"""Backward-compatibility shim for scan_event_bridge.py.

This module re-exports from scan/scan_event_bridge.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_event_bridge import (
    ScanEventBridge,
    create_scan_bridge,
    get_scan_bridge,
    teardown_scan_bridge,
    list_active_bridges,
    reset_bridges,
)

__all__ = [
    "ScanEventBridge",
    "create_scan_bridge",
    "get_scan_bridge",
    "teardown_scan_bridge",
    "list_active_bridges",
    "reset_bridges",
]
