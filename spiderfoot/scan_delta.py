"""Backward-compatibility shim for scan_delta.py.

This module re-exports from scan/scan_delta.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_delta import (
    DeltaKind,
    Finding,
    Delta,
    TrendPoint,
    ScanDeltaAnalyzer,
    DeltaResult,
)

__all__ = [
    "DeltaKind",
    "Finding",
    "Delta",
    "TrendPoint",
    "ScanDeltaAnalyzer",
    "DeltaResult",
]
