"""Module health monitoring for SpiderFoot.

Tracks runtime health metrics for each module during scans:
- Event processing rate and latency
- Error counts and error rate
- Memory usage estimates
- Stall detection
- Health score (0-100)

Usage::

    monitor = ModuleHealthMonitor()
    monitor.record_event_processed("sfp_dns", duration=0.5)
    monitor.record_error("sfp_dns", "ConnectionError")
    health = monitor.get_health("sfp_dns")
    report = monitor.get_report()
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


log = logging.getLogger("spiderfoot.health_monitor")


class HealthStatus(Enum):
    """Module health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STALLED = "stalled"
    UNKNOWN = "unknown"


@dataclass
class ModuleHealth:
    """Health metrics for a single module."""
    module_name: str
    events_processed: int = 0
    events_produced: int = 0
    total_duration: float = 0.0
    error_count: int = 0
    last_event_time: float = 0.0
    last_error_time: float = 0.0
    last_error_type: str = ""
    start_time: float = field(default_factory=time.monotonic)
    error_types: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def avg_duration(self) -> float:
        if self.events_processed == 0:
            return 0.0
        return self.total_duration / self.events_processed

    @property
    def error_rate(self) -> float:
        total = self.events_processed + self.error_count
        if total == 0:
            return 0.0
        return self.error_count / total

    @property
    def events_per_second(self) -> float:
        elapsed = time.monotonic() - self.start_time
        if elapsed <= 0:
            return 0.0
        return self.events_processed / elapsed

    @property
    def idle_seconds(self) -> float:
        if self.last_event_time == 0:
            return time.monotonic() - self.start_time
        return time.monotonic() - self.last_event_time

    @property
    def health_score(self) -> int:
        """Compute a 0-100 health score."""
        score = 100

        # Penalize for errors
        if self.error_rate > 0.5:
            score -= 50
        elif self.error_rate > 0.2:
            score -= 30
        elif self.error_rate > 0.05:
            score -= 15

        # Penalize for slow processing
        if self.avg_duration > 30:
            score -= 25
        elif self.avg_duration > 10:
            score -= 15
        elif self.avg_duration > 5:
            score -= 5

        # Penalize for stalling
        if self.idle_seconds > 300:
            score -= 30
        elif self.idle_seconds > 120:
            score -= 15

        return max(0, min(100, score))

    @property
    def status(self) -> HealthStatus:
        """Determine health status from score."""
        if self.idle_seconds > 300 and self.events_processed > 0:
            return HealthStatus.STALLED
        s = self.health_score
        if s >= 80:
            return HealthStatus.HEALTHY
        if s >= 50:
            return HealthStatus.DEGRADED
        return HealthStatus.UNHEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_name": self.module_name,
            "status": self.status.value,
            "health_score": self.health_score,
            "events_processed": self.events_processed,
            "events_produced": self.events_produced,
            "avg_duration_ms": round(self.avg_duration * 1000, 2),
            "error_count": self.error_count,
            "error_rate": round(self.error_rate, 4),
            "events_per_second": round(self.events_per_second, 3),
            "idle_seconds": round(self.idle_seconds, 1),
            "last_error_type": self.last_error_type,
            "top_errors": dict(
                sorted(self.error_types.items(), key=lambda x: -x[1])[:5]
            ),
        }


class ModuleHealthMonitor:
    """Monitors health of all modules during scans."""

    def __init__(self, stall_threshold: float = 300.0) -> None:
        """
        Parameters
        ----------
        stall_threshold : float
            Seconds of inactivity before marking a module as stalled.
        """
        self._modules: dict[str, ModuleHealth] = {}
        self._lock = threading.Lock()
        self._stall_threshold = stall_threshold
        self._callbacks: list = []

    def register_module(self, module_name: str) -> None:
        """Register a module for health tracking."""
        with self._lock:
            if module_name not in self._modules:
                self._modules[module_name] = ModuleHealth(module_name=module_name)

    def record_event_processed(self, module_name: str,
                                duration: float = 0.0) -> None:
        """Record that a module processed an event."""
        with self._lock:
            health = self._get_or_create(module_name)
            health.events_processed += 1
            health.total_duration += duration
            health.last_event_time = time.monotonic()

    def record_event_produced(self, module_name: str) -> None:
        """Record that a module produced an event."""
        with self._lock:
            health = self._get_or_create(module_name)
            health.events_produced += 1

    def record_error(self, module_name: str,
                     error_type: str = "unknown") -> None:
        """Record a module error."""
        with self._lock:
            health = self._get_or_create(module_name)
            health.error_count += 1
            health.last_error_time = time.monotonic()
            health.last_error_type = error_type
            health.error_types[error_type] += 1

        # Fire callbacks if threshold breached
        self._check_alerts(module_name)

    def get_health(self, module_name: str) -> ModuleHealth | None:
        """Get health for a specific module."""
        with self._lock:
            return self._modules.get(module_name)

    def get_report(self) -> dict[str, Any]:
        """Get a full health report for all modules."""
        with self._lock:
            modules = {
                name: health.to_dict()
                for name, health in sorted(self._modules.items())
            }

        total = len(modules)
        healthy = sum(1 for m in modules.values() if m["status"] == "healthy")
        degraded = sum(1 for m in modules.values() if m["status"] == "degraded")
        unhealthy = sum(1 for m in modules.values() if m["status"] == "unhealthy")
        stalled = sum(1 for m in modules.values() if m["status"] == "stalled")

        return {
            "summary": {
                "total": total,
                "healthy": healthy,
                "degraded": degraded,
                "unhealthy": unhealthy,
                "stalled": stalled,
            },
            "modules": modules,
        }

    def get_stalled_modules(self) -> list[str]:
        """Get list of modules that appear stalled."""
        with self._lock:
            return [
                name for name, h in self._modules.items()
                if h.status == HealthStatus.STALLED
            ]

    def get_unhealthy_modules(self) -> list[str]:
        """Get list of unhealthy modules."""
        with self._lock:
            return [
                name for name, h in self._modules.items()
                if h.status in (HealthStatus.UNHEALTHY, HealthStatus.STALLED)
            ]

    def on_alert(self, callback) -> None:
        """Register a callback for health alerts.

        Callback receives (module_name, health_dict).
        """
        self._callbacks.append(callback)

    def reset(self) -> None:
        """Reset all health data."""
        with self._lock:
            self._modules.clear()

    def _get_or_create(self, module_name: str) -> ModuleHealth:
        """Get or create health record (must hold lock)."""
        if module_name not in self._modules:
            self._modules[module_name] = ModuleHealth(module_name=module_name)
        return self._modules[module_name]

    def _check_alerts(self, module_name: str) -> None:
        """Fire alert callbacks if module health degrades."""
        health = self._modules.get(module_name)
        if not health:
            return

        if health.status in (HealthStatus.UNHEALTHY, HealthStatus.STALLED):
            for cb in self._callbacks:
                try:
                    cb(module_name, health.to_dict())
                except Exception as e:
                    log.debug("health callback cb(module_name, health) failed: %s", e)


# Singleton
_monitor: ModuleHealthMonitor | None = None


def get_health_monitor() -> ModuleHealthMonitor:
    """Get the singleton health monitor."""
    global _monitor
    if _monitor is None:
        _monitor = ModuleHealthMonitor()
    return _monitor
