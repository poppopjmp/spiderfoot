"""Backward-compatibility shim for report_generator.py.

This module re-exports from reporting/report_generator.py for backward compatibility.
"""

from __future__ import annotations

from .reporting.report_generator import (
    ReportFormat,
    ReportType,
    ReportGeneratorConfig,
    GeneratedSection,
    GeneratedReport,
    ReportGenerator,
)

__all__ = [
    "ReportFormat",
    "ReportType",
    "ReportGeneratorConfig",
    "GeneratedSection",
    "GeneratedReport",
    "ReportGenerator",
]
