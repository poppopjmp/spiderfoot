"""Backward-compatibility shim for scan_hooks.py.

This module re-exports from scan/scan_hooks.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_hooks import (
    ScanEvent,
    ScanLifecycleEvent,
    ScanLifecycleHooks,
    get_scan_hooks,
)

__all__ = [
    "ScanEvent",
    "ScanLifecycleEvent",
    "ScanLifecycleHooks",
    "get_scan_hooks",
]
