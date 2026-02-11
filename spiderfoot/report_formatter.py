"""Backward-compatibility shim for report_formatter.py.

This module re-exports from reporting/report_formatter.py for backward compatibility.
"""

from __future__ import annotations

from .reporting.report_formatter import (
    Theme,
    FormatterConfig,
    ReportFormatter,
)

__all__ = [
    "Theme",
    "FormatterConfig",
    "ReportFormatter",
]
