"""Backward-compatibility shim for structured_logging.py.

This module re-exports from observability/structured_logging.py for backward compatibility.
"""

from __future__ import annotations

from .observability.structured_logging import (
    StructuredFormatter,
    StructuredLogHandler,
    EventLogEmitter,
    setup_structured_logging,
)

__all__ = [
    "StructuredFormatter",
    "StructuredLogHandler",
    "EventLogEmitter",
    "setup_structured_logging",
]
