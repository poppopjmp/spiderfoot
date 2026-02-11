"""Backward-compatibility shim for scan_metadata_service.py.

This module re-exports from scan/scan_metadata_service.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_metadata_service import (
    ScanMetadataService,
)

__all__ = [
    "ScanMetadataService",
]
