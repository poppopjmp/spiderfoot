"""Convert root-level reporting files to re-export shims."""

from __future__ import annotations

import os

# Mapping of file to what it exports
FILE_EXPORTS = {
    "export_service.py": [
        "ExportFormat",
        "ExportConfig",
        "ExportService",
    ],
    "report_formatter.py": [
        "Theme",
        "FormatterConfig",
        "ReportFormatter",
    ],
    "report_generator.py": [
        "ReportFormat",
        "ReportType",
        "ReportGeneratorConfig",
        "GeneratedSection",
        "GeneratedReport",
        "ReportGenerator",
    ],
    "report_preprocessor.py": [
        "RiskLevel",
        "ReportSectionType",
        "NormalizedEvent",
        "ReportSection",
        "ReportContext",
        "PreprocessorConfig",
        "PreprocessorStats",
        "ReportPreprocessor",
    ],
    "report_storage.py": [
        "StorageBackend",
        "StoreConfig",
        "LRUCache",
        "SQLiteBackend",
        "MemoryBackend",
        "ReportStore",
    ],
    "visualization_service.py": [
        "VisualizationServiceError",
        "VisualizationService",
    ],
}


def make_shim(filename: str, exports: list[str]) -> str:
    """Generate shim content for a file."""
    base = filename.replace(".py", "")
    lines = [
        f'"""Backward-compatibility shim for {filename}.',
        "",
        f"This module re-exports from reporting/{filename} for backward compatibility.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        f"from .reporting.{base} import (",
    ]
    for exp in exports:
        lines.append(f"    {exp},")
    lines.append(")")
    lines.append("")
    lines.append("__all__ = [")
    for exp in exports:
        lines.append(f'    "{exp}",')
    lines.append("]")
    lines.append("")
    return "\n".join(lines)


# Convert all files
os.chdir("d:/github/spiderfoot/spiderfoot")
for filename, exports in FILE_EXPORTS.items():
    shim = make_shim(filename, exports)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(shim)
    print(f"Converted {filename} to shim ({len(exports)} exports)")

print(f"\nConverted {len(FILE_EXPORTS)} files to shims")
