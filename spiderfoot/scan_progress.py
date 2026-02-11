"""Backward-compatibility shim for scan_progress.py.

This module re-exports from scan/scan_progress.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_progress import (
    ModuleStatus,
    ModuleProgress,
    ProgressSnapshot,
    ScanProgressTracker,
)

__all__ = [
    "ModuleStatus",
    "ModuleProgress",
    "ProgressSnapshot",
    "ScanProgressTracker",
]
