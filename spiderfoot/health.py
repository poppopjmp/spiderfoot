#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         health
# Purpose:      Unified health check system for SpiderFoot services.
#               Aggregates health from all registered components with
#               configurable probes (liveness, readiness, startup).
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Health Check System

Provides Kubernetes-compatible health probes for all services:

    - ``/health/live``  — Liveness: is the process alive?
    - ``/health/ready`` — Readiness: can the service accept traffic?
    - ``/health/startup`` — Startup: has the service finished initializing?

Components register health checks via the ``HealthAggregator``.

Usage::

    from spiderfoot.health import HealthAggregator, HealthStatus

    health = HealthAggregator.get_instance()
    health.register("database", lambda: HealthStatus.UP)
    health.register("redis", check_redis)

    status = health.check_all()
    # {"status": "up", "components": {"database": "up", "redis": "up"}}
"""

import logging
import threading
import time
from enum import Enum
from typing import Callable, Dict, Optional

log = logging.getLogger("spiderfoot.health")


class HealthStatus(Enum):
    """Component health status."""
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ComponentHealth:
    """Health state of a single component."""

    def __init__(self, name: str, status: HealthStatus,
                 message: str = "", details: Optional[dict] = None,
                 latency_ms: float = 0.0):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.latency_ms = latency_ms
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        d = {
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
        }
        if self.message:
            d["message"] = self.message
        if self.details:
            d["details"] = self.details
        return d


class HealthAggregator:
    """Aggregates health checks from all registered components.

    Supports three probe types matching Kubernetes conventions:

    - **liveness**: Is the process still running? (always UP unless crashed)
    - **readiness**: Can the service handle requests? (checks dependencies)
    - **startup**: Has initial setup completed? (one-time check)
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._checks: Dict[str, Callable[[], HealthStatus]] = {}
        self._detailed_checks: Dict[
            str, Callable[[], ComponentHealth]
        ] = {}
        self._startup_complete = False
        self._start_time = time.time()
        self._check_timeout = 5.0  # seconds per check

    @classmethod
    def get_instance(cls) -> "HealthAggregator":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str,
                 check: Callable[[], HealthStatus]) -> None:
        """Register a simple health check.

        Args:
            name: Component name (e.g., "database", "redis").
            check: Callable returning HealthStatus.
        """
        self._checks[name] = check
        log.debug("Registered health check: %s", name)

    def register_detailed(self, name: str,
                          check: Callable[[], ComponentHealth]) -> None:
        """Register a detailed health check returning ComponentHealth."""
        self._detailed_checks[name] = check
        log.debug("Registered detailed health check: %s", name)

    def unregister(self, name: str) -> None:
        """Remove a health check."""
        self._checks.pop(name, None)
        self._detailed_checks.pop(name, None)

    # ------------------------------------------------------------------
    # Probes
    # ------------------------------------------------------------------

    def liveness(self) -> dict:
        """Liveness probe — is the process alive?

        Returns UP unless the process is fundamentally broken.
        """
        return {
            "status": HealthStatus.UP.value,
            "uptime_seconds": round(time.time() - self._start_time, 1),
        }

    def readiness(self) -> dict:
        """Readiness probe — can the service accept traffic?

        Checks all registered components. Returns DOWN if any
        critical component is DOWN.
        """
        return self.check_all()

    def startup(self) -> dict:
        """Startup probe — has initialization completed?."""
        return {
            "status": (HealthStatus.UP if self._startup_complete
                       else HealthStatus.DOWN).value,
            "startup_complete": self._startup_complete,
        }

    def mark_ready(self) -> None:
        """Mark the service as startup-complete."""
        self._startup_complete = True
        log.info("Service marked as startup-complete")

    # ------------------------------------------------------------------
    # Full check
    # ------------------------------------------------------------------

    def check_all(self) -> dict:
        """Run all registered health checks.

        Returns:
            Dict with overall status and per-component results.
        """
        components: Dict[str, dict] = {}
        overall = HealthStatus.UP

        # Simple checks
        for name, check_fn in self._checks.items():
            t0 = time.monotonic()
            try:
                status = check_fn()
                latency = (time.monotonic() - t0) * 1000
                components[name] = ComponentHealth(
                    name, status, latency_ms=latency
                ).to_dict()
            except Exception as e:
                latency = (time.monotonic() - t0) * 1000
                components[name] = ComponentHealth(
                    name, HealthStatus.DOWN,
                    message=str(e), latency_ms=latency
                ).to_dict()
                overall = HealthStatus.DOWN

            if components[name]["status"] == HealthStatus.DOWN.value:
                overall = HealthStatus.DOWN
            elif (components[name]["status"] == HealthStatus.DEGRADED.value
                  and overall == HealthStatus.UP):
                overall = HealthStatus.DEGRADED

        # Detailed checks
        for name, check_fn in self._detailed_checks.items():
            t0 = time.monotonic()
            try:
                result = check_fn()
                result.latency_ms = (time.monotonic() - t0) * 1000
                components[name] = result.to_dict()
            except Exception as e:
                latency = (time.monotonic() - t0) * 1000
                components[name] = ComponentHealth(
                    name, HealthStatus.DOWN,
                    message=str(e), latency_ms=latency
                ).to_dict()
                overall = HealthStatus.DOWN

            if components[name]["status"] == HealthStatus.DOWN.value:
                overall = HealthStatus.DOWN
            elif (components[name]["status"] == HealthStatus.DEGRADED.value
                  and overall == HealthStatus.UP):
                overall = HealthStatus.DEGRADED

        return {
            "status": overall.value,
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "components": components,
        }

    def check_component(self, name: str) -> Optional[dict]:
        """Check a single component by name."""
        if name in self._checks:
            try:
                status = self._checks[name]()
                return ComponentHealth(name, status).to_dict()
            except Exception as e:
                return ComponentHealth(
                    name, HealthStatus.DOWN, message=str(e)
                ).to_dict()

        if name in self._detailed_checks:
            try:
                return self._detailed_checks[name]().to_dict()
            except Exception as e:
                return ComponentHealth(
                    name, HealthStatus.DOWN, message=str(e)
                ).to_dict()

        return None


# ---------------------------------------------------------------------------
# Built-in health checks for SpiderFoot services
# ---------------------------------------------------------------------------

def check_database() -> HealthStatus:
    """Check database connectivity."""
    try:
        from spiderfoot.service_registry import ServiceRegistry
        registry = ServiceRegistry.get_instance()
        data_svc = registry.get_optional("data")
        if data_svc is None:
            return HealthStatus.UNKNOWN
        # A simple operation to verify connectivity
        if hasattr(data_svc, "dbh") and data_svc.dbh:
            return HealthStatus.UP
        return HealthStatus.DOWN
    except Exception:
        return HealthStatus.DOWN


def check_event_bus() -> HealthStatus:
    """Check event bus connectivity."""
    try:
        from spiderfoot.service_registry import ServiceRegistry
        registry = ServiceRegistry.get_instance()
        bus = registry.get_optional("event_bus")
        if bus is None:
            return HealthStatus.UNKNOWN
        return HealthStatus.UP
    except Exception:
        return HealthStatus.DOWN


def check_cache() -> HealthStatus:
    """Check cache service."""
    try:
        from spiderfoot.service_registry import ServiceRegistry
        registry = ServiceRegistry.get_instance()
        cache = registry.get_optional("cache")
        if cache is None:
            return HealthStatus.UNKNOWN
        return HealthStatus.UP
    except Exception:
        return HealthStatus.DOWN


def register_default_checks(health: Optional[HealthAggregator] = None) -> None:
    """Register built-in health checks for core services."""
    if health is None:
        health = HealthAggregator.get_instance()

    health.register("database", check_database)
    health.register("event_bus", check_event_bus)
    health.register("cache", check_cache)
    log.debug("Default health checks registered")
