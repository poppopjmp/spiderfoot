#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         metrics
# Purpose:      Prometheus-compatible metrics endpoint for all SpiderFoot services.
#               Exposes counters, gauges, histograms without requiring the
#               prometheus_client library (zero-dependency implementation).
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Metrics

Provides Prometheus-compatible metrics exposition in text/plain format.
Works as a standalone HTTP endpoint or integrates into the service_runner
health server.

Usage::

    from spiderfoot.metrics import metrics, Counter, Gauge, Histogram

    SCANS_TOTAL = Counter("sf_scans_total", "Total scans started", ["status"])
    SCANS_TOTAL.labels(status="completed").inc()

    ACTIVE_SCANS = Gauge("sf_active_scans", "Currently active scans")
    ACTIVE_SCANS.set(3)

    REQUEST_DURATION = Histogram(
        "sf_request_duration_seconds", "Request duration",
        buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
    )
    with REQUEST_DURATION.time():
        do_work()
"""

import threading
import time
from typing import Dict, List, Optional, Tuple

from collections.abc import Sequence


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------

def _label_key(labels: dict[str, str]) -> str:
    """Create a canonical key from a label dict."""
    if not labels:
        return ""
    return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))


def _format_labels(labels: dict[str, str]) -> str:
    """Format labels for Prometheus exposition."""
    if not labels:
        return ""
    return "{" + _label_key(labels) + "}"


# ---------------------------------------------------------------------------
# Metric types
# ---------------------------------------------------------------------------

class _LabeledValue:
    """Thread-safe labeled numeric value."""

    def __init__(self):
        self._lock = threading.Lock()
        self._value = 0.0

    @property
    def value(self) -> float:
        return self._value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value


class Counter:
    """Prometheus-style counter (monotonically increasing)."""

    def __init__(self, name: str, help_text: str = "",
                 label_names: Optional[list[str]] = None):
        self.name = name
        self.help_text = help_text
        self.label_names = label_names or []
        self._lock = threading.Lock()
        self._values: dict[str, _LabeledValue] = {}
        # No-label variant
        if not self.label_names:
            self._values[""] = _LabeledValue()

    def labels(self, **kwargs) -> _LabeledValue:
        key = _label_key(kwargs)
        with self._lock:
            if key not in self._values:
                self._values[key] = _LabeledValue()
                self._values[key]._labels = kwargs
            return self._values[key]

    def inc(self, amount: float = 1.0) -> None:
        """Increment the no-label variant."""
        if "" in self._values:
            self._values[""].inc(amount)

    def expose(self) -> str:
        lines: list[str] = []
        if self.help_text:
            lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} counter")
        with self._lock:
            for key, val in sorted(self._values.items()):
                labels_str = ""
                if hasattr(val, "_labels"):
                    labels_str = _format_labels(val._labels)
                elif key:
                    labels_str = "{" + key + "}"
                lines.append(f"{self.name}{labels_str} {val.value}")
        return "\n".join(lines)


class Gauge:
    """Prometheus-style gauge (can increase and decrease)."""

    def __init__(self, name: str, help_text: str = "",
                 label_names: Optional[list[str]] = None):
        self.name = name
        self.help_text = help_text
        self.label_names = label_names or []
        self._lock = threading.Lock()
        self._values: dict[str, _LabeledValue] = {}
        if not self.label_names:
            self._values[""] = _LabeledValue()

    def labels(self, **kwargs) -> _LabeledValue:
        key = _label_key(kwargs)
        with self._lock:
            if key not in self._values:
                self._values[key] = _LabeledValue()
                self._values[key]._labels = kwargs
            return self._values[key]

    def set(self, value: float) -> None:
        if "" in self._values:
            self._values[""].set(value)

    def inc(self, amount: float = 1.0) -> None:
        if "" in self._values:
            self._values[""].inc(amount)

    def dec(self, amount: float = 1.0) -> None:
        if "" in self._values:
            self._values[""].dec(amount)

    def expose(self) -> str:
        lines: list[str] = []
        if self.help_text:
            lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} gauge")
        with self._lock:
            for key, val in sorted(self._values.items()):
                labels_str = ""
                if hasattr(val, "_labels"):
                    labels_str = _format_labels(val._labels)
                elif key:
                    labels_str = "{" + key + "}"
                lines.append(f"{self.name}{labels_str} {val.value}")
        return "\n".join(lines)


class Histogram:
    """Prometheus-style histogram with configurable buckets."""

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5,
                       1.0, 2.5, 5.0, 10.0)

    def __init__(self, name: str, help_text: str = "",
                 buckets: Optional[Sequence[float]] = None,
                 label_names: Optional[list[str]] = None):
        self.name = name
        self.help_text = help_text
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self.label_names = label_names or []
        self._lock = threading.Lock()
        # For simplicity, only unlabeled histograms supported in v1
        self._bucket_counts = {b: 0 for b in self.buckets}
        self._bucket_counts[float("inf")] = 0
        self._sum = 0.0
        self._count = 0

    def observe(self, value: float) -> None:
        """Record a value."""
        with self._lock:
            self._sum += value
            self._count += 1
            for b in self.buckets:
                if value <= b:
                    self._bucket_counts[b] += 1
            self._bucket_counts[float("inf")] += 1

    def time(self):
        """Context manager that times the wrapped block."""
        return _HistogramTimer(self)

    def expose(self) -> str:
        lines: list[str] = []
        if self.help_text:
            lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} histogram")
        with self._lock:
            cumulative = 0
            for b in self.buckets:
                cumulative += self._bucket_counts[b]
                le = f"+Inf" if b == float("inf") else str(b)
                lines.append(f'{self.name}_bucket{{le="{le}"}} {cumulative}')
            cumulative += self._bucket_counts.get(float("inf"), 0) - cumulative
            lines.append(f'{self.name}_bucket{{le="+Inf"}} {self._count}')
            lines.append(f"{self.name}_sum {self._sum}")
            lines.append(f"{self.name}_count {self._count}")
        return "\n".join(lines)


class _HistogramTimer:
    def __init__(self, histogram: Histogram):
        self._histogram = histogram
        self._start = None

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, *args):
        self._histogram.observe(time.monotonic() - self._start)


# ---------------------------------------------------------------------------
# Global metrics registry
# ---------------------------------------------------------------------------

class MetricsRegistry:
    """Global registry of all metrics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._metrics: dict[str, object] = {}

    def register(self, metric) -> None:
        """Register a metric (Counter, Gauge, or Histogram)."""
        with self._lock:
            self._metrics[metric.name] = metric

    def unregister(self, name: str) -> None:
        with self._lock:
            self._metrics.pop(name, None)

    def expose(self) -> str:
        """Render all metrics in Prometheus text format."""
        with self._lock:
            items = list(self._metrics.values())
        parts = []
        for m in items:
            parts.append(m.expose())
        return "\n\n".join(parts) + "\n"

    def clear(self) -> None:
        with self._lock:
            self._metrics.clear()


# Singleton registry
_registry = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    return _registry


# ---------------------------------------------------------------------------
# Pre-defined SpiderFoot metrics
# ---------------------------------------------------------------------------

# Scan metrics
SCANS_TOTAL = Counter(
    "sf_scans_total",
    "Total number of scans by status",
    label_names=["status"],
)
_registry.register(SCANS_TOTAL)

ACTIVE_SCANS = Gauge(
    "sf_active_scans",
    "Number of currently active scans",
)
_registry.register(ACTIVE_SCANS)

SCAN_DURATION = Histogram(
    "sf_scan_duration_seconds",
    "Scan duration in seconds",
    buckets=[10, 30, 60, 120, 300, 600, 1800, 3600],
)
_registry.register(SCAN_DURATION)

# Event metrics
EVENTS_PRODUCED = Counter(
    "sf_events_produced_total",
    "Total events produced",
    label_names=["event_type"],
)
_registry.register(EVENTS_PRODUCED)

EVENTS_PROCESSED = Counter(
    "sf_events_processed_total",
    "Total events processed by modules",
    label_names=["module"],
)
_registry.register(EVENTS_PROCESSED)

# Module metrics
MODULE_ERRORS = Counter(
    "sf_module_errors_total",
    "Total module errors",
    label_names=["module", "error_type"],
)
_registry.register(MODULE_ERRORS)

MODULE_DURATION = Histogram(
    "sf_module_handle_duration_seconds",
    "Module handleEvent duration",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
)
_registry.register(MODULE_DURATION)

# HTTP metrics
HTTP_REQUESTS = Counter(
    "sf_http_requests_total",
    "Total HTTP requests made",
    label_names=["method", "status_code"],
)
_registry.register(HTTP_REQUESTS)

HTTP_DURATION = Histogram(
    "sf_http_request_duration_seconds",
    "HTTP request duration",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
_registry.register(HTTP_DURATION)

# DNS metrics
DNS_QUERIES = Counter(
    "sf_dns_queries_total",
    "Total DNS queries",
    label_names=["record_type", "status"],
)
_registry.register(DNS_QUERIES)

DNS_CACHE_HITS = Counter(
    "sf_dns_cache_hits_total",
    "DNS cache hits",
)
_registry.register(DNS_CACHE_HITS)

DNS_CACHE_MISSES = Counter(
    "sf_dns_cache_misses_total",
    "DNS cache misses",
)
_registry.register(DNS_CACHE_MISSES)

# Cache metrics
CACHE_OPERATIONS = Counter(
    "sf_cache_operations_total",
    "Cache operations",
    label_names=["operation", "status"],
)
_registry.register(CACHE_OPERATIONS)

# Worker pool metrics
WORKER_POOL_SIZE = Gauge(
    "sf_worker_pool_size",
    "Current worker pool size",
)
_registry.register(WORKER_POOL_SIZE)

WORKER_QUEUE_SIZE = Gauge(
    "sf_worker_queue_size",
    "Current worker input queue size",
)
_registry.register(WORKER_QUEUE_SIZE)

# Service uptime
SERVICE_UPTIME = Gauge(
    "sf_service_uptime_seconds",
    "Service uptime in seconds",
    label_names=["service"],
)
_registry.register(SERVICE_UPTIME)

# Data service metrics
DB_QUERIES = Counter(
    "sf_db_queries_total",
    "Total database queries",
    label_names=["operation"],
)
_registry.register(DB_QUERIES)

DB_QUERY_DURATION = Histogram(
    "sf_db_query_duration_seconds",
    "Database query duration",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)
_registry.register(DB_QUERY_DURATION)

# EventBus metrics
EVENTBUS_PUBLISHED = Counter(
    "sf_eventbus_published_total",
    "Total events published to event bus",
    label_names=["topic"],
)
_registry.register(EVENTBUS_PUBLISHED)

EVENTBUS_CONSUMED = Counter(
    "sf_eventbus_consumed_total",
    "Total events consumed from event bus",
    label_names=["topic"],
)
_registry.register(EVENTBUS_CONSUMED)
