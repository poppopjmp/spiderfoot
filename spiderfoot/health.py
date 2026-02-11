"""Backward-compatibility shim for health.py.

This module re-exports from observability/health.py for backward compatibility.
"""

from __future__ import annotations

from .observability.health import (
    HealthStatus,
    ComponentHealth,
    HealthAggregator,
    check_database,
    check_event_bus,
    check_cache,
    register_default_checks,
)

__all__ = [
    "HealthStatus",
    "ComponentHealth",
    "HealthAggregator",
    "check_database",
    "check_event_bus",
    "check_cache",
    "register_default_checks",
]
