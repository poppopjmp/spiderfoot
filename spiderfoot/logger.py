"""Backward-compatibility shim for logger.py.

This module re-exports from observability/logger.py for backward compatibility.
"""

from __future__ import annotations

from .observability.logger import (
    SpiderFootSqliteLogHandler,
    logListenerSetup,
    logWorkerSetup,
    stop_listener,
)

__all__ = [
    "SpiderFootSqliteLogHandler",
    "logListenerSetup",
    "logWorkerSetup",
    "stop_listener",
]
