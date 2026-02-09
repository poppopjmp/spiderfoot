"""
SpiderFoot Observability — metrics, logging, tracing, and telemetry.

This sub-package groups observability-related modules for cleaner imports.
All symbols are re-exported from the original flat module locations for
backward compatibility.

Usage::

    from spiderfoot.observability import metrics, structured_logging
    from spiderfoot.observability.metrics import SCANS_TOTAL
"""

# Re-export from flat module locations (backward compat)
from spiderfoot.metrics import *  # noqa: F401,F403
from spiderfoot.structured_logging import *  # noqa: F401,F403

__all__ = [
    "metrics",
    "structured_logging",
    "request_tracing",
    "error_telemetry",
    "logging_config",
    "vector_sink",
    "vector_bootstrap",
    "health",
    "benchmark",
]
