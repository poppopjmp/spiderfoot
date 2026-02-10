"""Module Metrics Collector for SpiderFoot.

Unified metrics collection for module performance, event throughput,
error rates, and resource usage. Supports histograms, counters, gauges,
and timing measurements with optional periodic snapshots.
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.module_metrics")


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricValue:
    """A single metric value with metadata."""
    name: str
    metric_type: MetricType
    value: float = 0.0
    count: int = 0
    _values: list[float] = field(default_factory=list, repr=False)

    def record(self, value: float) -> None:
        if self.metric_type == MetricType.COUNTER:
            self.value += value
            self.count += 1
        elif self.metric_type == MetricType.GAUGE:
            self.value = value
            self.count += 1
        elif self.metric_type in (MetricType.HISTOGRAM, MetricType.TIMER):
            self._values.append(value)
            self.value = value
            self.count += 1

    @property
    def mean(self) -> float:
        if not self._values:
            return self.value if self.metric_type in (MetricType.COUNTER, MetricType.GAUGE) else 0.0
        return statistics.mean(self._values)

    @property
    def median(self) -> float:
        if not self._values:
            return 0.0
        return statistics.median(self._values)

    @property
    def p95(self) -> float:
        if len(self._values) < 2:
            return self._values[0] if self._values else 0.0
        sorted_vals = sorted(self._values)
        idx = int(len(sorted_vals) * 0.95)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]

    @property
    def p99(self) -> float:
        if len(self._values) < 2:
            return self._values[0] if self._values else 0.0
        sorted_vals = sorted(self._values)
        idx = int(len(sorted_vals) * 0.99)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]

    @property
    def min_val(self) -> float:
        return min(self._values) if self._values else 0.0

    @property
    def max_val(self) -> float:
        return max(self._values) if self._values else 0.0

    def reset(self) -> None:
        self.value = 0.0
        self.count = 0
        self._values.clear()

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "type": self.metric_type.value,
            "value": self.value,
            "count": self.count,
        }
        if self.metric_type in (MetricType.HISTOGRAM, MetricType.TIMER) and self._values:
            d["mean"] = round(self.mean, 4)
            d["median"] = round(self.median, 4)
            d["p95"] = round(self.p95, 4)
            d["p99"] = round(self.p99, 4)
            d["min"] = round(self.min_val, 4)
            d["max"] = round(self.max_val, 4)
        return d


class TimerContext:
    """Context manager for timing operations."""

    def __init__(self, metric: MetricValue) -> None:
        self._metric = metric
        self._start: float = 0

    def __enter__(self) -> "TimerContext":
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        elapsed = time.monotonic() - self._start
        self._metric.record(elapsed)


class ModuleMetrics:
    """Metrics for a single module.

    Usage:
        metrics = ModuleMetrics("sfp_dns")
        metrics.increment("events_produced")
        metrics.gauge("queue_size", 42)

        with metrics.timer("query_time"):
            # perform DNS query
            pass

        print(metrics.get("events_produced").value)
    """

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self._metrics: dict[str, MetricValue] = {}
        self._lock = threading.Lock()
        self._created_at = time.time()

    def _get_or_create(self, name: str, metric_type: MetricType) -> MetricValue:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = MetricValue(name=name, metric_type=metric_type)
            return self._metrics[name]

    def increment(self, name: str, amount: float = 1.0) -> None:
        metric = self._get_or_create(name, MetricType.COUNTER)
        metric.record(amount)

    def gauge(self, name: str, value: float) -> None:
        metric = self._get_or_create(name, MetricType.GAUGE)
        metric.record(value)

    def histogram(self, name: str, value: float) -> None:
        metric = self._get_or_create(name, MetricType.HISTOGRAM)
        metric.record(value)

    def timer(self, name: str) -> TimerContext:
        metric = self._get_or_create(name, MetricType.TIMER)
        return TimerContext(metric)

    def record_time(self, name: str, seconds: float) -> None:
        metric = self._get_or_create(name, MetricType.TIMER)
        metric.record(seconds)

    def get(self, name: str) -> MetricValue | None:
        with self._lock:
            return self._metrics.get(name)

    def get_all(self) -> dict[str, MetricValue]:
        with self._lock:
            return dict(self._metrics)

    @property
    def metric_names(self) -> list[str]:
        with self._lock:
            return sorted(self._metrics.keys())

    def reset(self) -> None:
        with self._lock:
            for m in self._metrics.values():
                m.reset()

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "module": self.module_name,
                "created_at": self._created_at,
                "metrics": {name: m.to_dict() for name, m in self._metrics.items()},
            }


class MetricsCollector:
    """Global metrics collector managing per-module metrics.

    Usage:
        collector = MetricsCollector()
        collector.get_module("sfp_dns").increment("events")
        collector.get_module("sfp_ssl").gauge("connections", 5)

        snapshot = collector.snapshot()
    """

    _instance: "MetricsCollector" | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._modules: dict[str, ModuleMetrics] = {}
        self._global_metrics = ModuleMetrics("__global__")
        self._lock = threading.Lock()
        self._snapshots: list[dict] = []
        self._max_snapshots = 100

    def get_module(self, module_name: str) -> ModuleMetrics:
        with self._lock:
            if module_name not in self._modules:
                self._modules[module_name] = ModuleMetrics(module_name)
            return self._modules[module_name]

    def remove_module(self, module_name: str) -> bool:
        with self._lock:
            return self._modules.pop(module_name, None) is not None

    @property
    def global_metrics(self) -> ModuleMetrics:
        return self._global_metrics

    @property
    def module_names(self) -> list[str]:
        with self._lock:
            return sorted(self._modules.keys())

    @property
    def module_count(self) -> int:
        with self._lock:
            return len(self._modules)

    def snapshot(self) -> dict:
        """Take a snapshot of all metrics."""
        with self._lock:
            snap = {
                "timestamp": time.time(),
                "global": self._global_metrics.to_dict(),
                "modules": {name: m.to_dict() for name, m in self._modules.items()},
            }
            self._snapshots.append(snap)
            if len(self._snapshots) > self._max_snapshots:
                self._snapshots = self._snapshots[-self._max_snapshots:]
            return snap

    def get_snapshots(self) -> list[dict]:
        return list(self._snapshots)

    def summary(self) -> dict:
        """Get a summary across all modules."""
        with self._lock:
            total_events = 0
            total_errors = 0
            modules_with_errors = []

            for name, m in self._modules.items():
                ev = m.get("events_produced")
                if ev:
                    total_events += int(ev.value)
                err = m.get("errors")
                if err and err.value > 0:
                    total_errors += int(err.value)
                    modules_with_errors.append(name)

            return {
                "module_count": len(self._modules),
                "total_events": total_events,
                "total_errors": total_errors,
                "modules_with_errors": modules_with_errors,
            }

    def reset_all(self) -> None:
        with self._lock:
            for m in self._modules.values():
                m.reset()
            self._global_metrics.reset()
            self._snapshots.clear()

    def to_dict(self) -> dict:
        return self.snapshot()

    @classmethod
    def get_instance(cls) -> "MetricsCollector":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._instance_lock:
            cls._instance = None
