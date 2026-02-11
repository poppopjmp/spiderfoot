"""Backward-compatibility shim for scan_queue.py.

This module re-exports from scan/scan_queue.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_queue import (
    Priority,
    BackpressureAction,
    PressureLevel,
    QueueItem,
    QueueStats,
    ScanQueue,
)

__all__ = [
    "Priority",
    "BackpressureAction",
    "PressureLevel",
    "QueueItem",
    "QueueStats",
    "ScanQueue",
]
