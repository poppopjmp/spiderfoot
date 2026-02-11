"""Backward-compatibility shim for module_metrics.py.

This module re-exports from plugins/module_metrics.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_metrics import (
    MetricsCollector,
    MetricType,
    MetricValue,
    ModuleMetrics,
    TimerContext,
)

__all__ = [
    "MetricsCollector",
    "MetricType",
    "MetricValue",
    "ModuleMetrics",
    "TimerContext",
]
