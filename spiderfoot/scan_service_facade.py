"""Backward-compatibility shim for scan_service_facade.py.

This module re-exports from scan/scan_service_facade.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_service_facade import (
    ScanServiceError,
    ScanService,
)

__all__ = [
    "ScanServiceError",
    "ScanService",
]
