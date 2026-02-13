"""SpiderFoot reporting subpackage.

This subpackage contains report generation, formatting, storage,
export, and visualization components.

Usage::

    from spiderfoot.reporting import ReportGenerator, ReportFormatter
    from spiderfoot.reporting import ExportService, VisualizationService
"""

from __future__ import annotations

# Export service
from .export_service import ExportConfig, ExportFormat, ExportService

# Report formatter
from .report_formatter import FormatterConfig, ReportFormatter, Theme

# Report generator
from .report_generator import (
    GeneratedReport,
    GeneratedSection,
    ReportFormat,
    ReportGenerator,
    ReportGeneratorConfig,
    ReportType,
)

# Report preprocessor
from .report_preprocessor import (
    NormalizedEvent,
    PreprocessorConfig,
    PreprocessorStats,
    ReportContext,
    ReportPreprocessor,
    ReportSection,
    ReportSectionType,
    RiskLevel,
)

# Report storage
from .report_storage import (
    LRUCache,
    MemoryBackend,
    ReportStore,
    SQLiteBackend,
    StoreConfig,
    StorageBackend,
)

# PDF renderer
from .pdf_renderer import PDFBranding, PDFConfig, PDFRenderer

# Visualization service
from .visualization_service import VisualizationService, VisualizationServiceError

__all__ = [
    # Export service
    "ExportConfig",
    "ExportFormat",
    "ExportService",
    # Report formatter
    "FormatterConfig",
    "ReportFormatter",
    "Theme",
    # Report generator
    "GeneratedReport",
    "GeneratedSection",
    "ReportFormat",
    "ReportGenerator",
    "ReportGeneratorConfig",
    "ReportType",
    # Report preprocessor
    "NormalizedEvent",
    "PreprocessorConfig",
    "PreprocessorStats",
    "ReportContext",
    "ReportPreprocessor",
    "ReportSection",
    "ReportSectionType",
    "RiskLevel",
    # Report storage
    "LRUCache",
    "MemoryBackend",
    "ReportStore",
    "SQLiteBackend",
    "StoreConfig",
    "StorageBackend",
    # PDF renderer
    "PDFBranding",
    "PDFConfig",
    "PDFRenderer",
    # Visualization service
    "VisualizationService",
    "VisualizationServiceError",
]
