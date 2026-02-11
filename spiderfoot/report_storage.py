"""Backward-compatibility shim for report_storage.py.

This module re-exports from reporting/report_storage.py for backward compatibility.
"""

from __future__ import annotations

from .reporting.report_storage import (
    StorageBackend,
    StoreConfig,
    LRUCache,
    SQLiteBackend,
    MemoryBackend,
    ReportStore,
)

__all__ = [
    "StorageBackend",
    "StoreConfig",
    "LRUCache",
    "SQLiteBackend",
    "MemoryBackend",
    "ReportStore",
]
