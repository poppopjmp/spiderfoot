"""Backward-compatibility shim for module_health.py.

This module re-exports from plugins/module_health.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_health import (
    HealthStatus,
    ModuleHealth,
    ModuleHealthMonitor,
    get_health_monitor,
)

__all__ = [
    "HealthStatus",
    "ModuleHealth",
    "ModuleHealthMonitor",
    "get_health_monitor",
]
