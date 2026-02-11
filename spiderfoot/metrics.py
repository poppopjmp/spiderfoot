"""Backward-compatibility shim for metrics.py.

This module re-exports from observability/metrics.py for backward compatibility.
"""

from __future__ import annotations

from .observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    get_registry,
)

__all__ = [
    "Counter",
    "Gauge",
    "Histogram",
    "MetricsRegistry",
    "get_registry",
]
