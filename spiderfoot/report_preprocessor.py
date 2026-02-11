"""Backward-compatibility shim for report_preprocessor.py.

This module re-exports from reporting/report_preprocessor.py for backward compatibility.
"""

from __future__ import annotations

from .reporting.report_preprocessor import (
    RiskLevel,
    ReportSectionType,
    NormalizedEvent,
    ReportSection,
    ReportContext,
    PreprocessorConfig,
    PreprocessorStats,
    ReportPreprocessor,
)

__all__ = [
    "RiskLevel",
    "ReportSectionType",
    "NormalizedEvent",
    "ReportSection",
    "ReportContext",
    "PreprocessorConfig",
    "PreprocessorStats",
    "ReportPreprocessor",
]
