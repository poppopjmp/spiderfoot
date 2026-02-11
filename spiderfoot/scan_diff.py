"""Backward-compatibility shim for scan_diff.py.

This module re-exports from scan/scan_diff.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_diff import (
    ChangeType,
    Finding,
    Change,
    ScanSnapshot,
    DiffResult,
    ScanDiff,
)

__all__ = [
    "ChangeType",
    "Finding",
    "Change",
    "ScanSnapshot",
    "DiffResult",
    "ScanDiff",
]
