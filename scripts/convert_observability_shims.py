"""Convert root-level observability files to re-export shims."""

from __future__ import annotations

import os

# Mapping of file to what it exports
FILE_EXPORTS = {
    "audit_log.py": [
        "AuditCategory",
        "AuditSeverity",
        "AuditEvent",
        "AuditBackend",
        "MemoryAuditBackend",
        "FileAuditBackend",
        "AuditLogger",
        "get_audit_logger",
    ],
    "health.py": [
        "HealthStatus",
        "ComponentHealth",
        "HealthAggregator",
        "check_database",
        "check_event_bus",
        "check_cache",
        "register_default_checks",
    ],
    "logger.py": [
        "SpiderFootSqliteLogHandler",
        "logListenerSetup",
        "logWorkerSetup",
        "stop_listener",
    ],
    "metrics.py": [
        "Counter",
        "Gauge",
        "Histogram",
        "MetricsRegistry",
        "get_registry",
    ],
    "structured_logging.py": [
        "StructuredFormatter",
        "StructuredLogHandler",
        "EventLogEmitter",
        "setup_structured_logging",
    ],
}


def make_shim(filename: str, exports: list[str]) -> str:
    """Generate shim content for a file."""
    base = filename.replace(".py", "")
    lines = [
        f'"""Backward-compatibility shim for {filename}.',
        "",
        f"This module re-exports from observability/{filename} for backward compatibility.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        f"from .observability.{base} import (",
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
