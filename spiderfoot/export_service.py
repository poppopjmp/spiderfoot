"""Backward-compatibility shim for export_service.py.

This module re-exports from reporting/export_service.py for backward compatibility.
"""

from __future__ import annotations

from .reporting.export_service import (
    ExportFormat,
    ExportConfig,
    ExportService,
)

__all__ = [
    "ExportFormat",
    "ExportConfig",
    "ExportService",
]
