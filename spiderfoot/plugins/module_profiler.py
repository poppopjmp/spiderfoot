"""Module performance profiler for SpiderFoot.

Provides detailed per-module, per-method profiling including:
- Per-method call counts, total/avg/min/max/p50/p95/p99 latency
- Event throughput tracking
- Memory usage snapshots (via tracemalloc when available)
- Profile snapshots and comparison over time
- Context manager and decorator for easy instrumentation

Usage::

    profiler = get_module_profiler()
    with profiler.trace("sfp_dns", "handleEvent"):
        # ... do work ...

    @profiler.profile("sfp_dns")
    def my_function():
        pass

    report = profiler.get_profile("sfp_dns")
"""

from __future__ import annotations

import functools
import logging
import math
import statistics
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

log = logging.getLogger("spiderfoot.module_profiler")


@dataclass
class MethodProfile:
    """Performance profile for a single method."""
    method_name: str
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    _samples: list[float] = field(default_factory=list)
    _max_samples: int = 10000

    def record(self, duration: float) -> None:
        """Record a method invocation duration."""
        self.call_count += 1
        self.total_time += duration
        if duration < self.min_time:
            self.min_time = duration
        if duration > self.max_time:
            self.max_time = duration

        # Keep bounded sample reservoir for percentile calculations
        if len(self._samples) < self._max_samples:
            self._samples.append(duration)
        else:
            # Reservoir sampling to maintain representative distribution
            import random
            idx = random.randint(0, self.call_count - 1)
            if idx < self._max_samples:
                self._samples[idx] = duration

    @property
    def avg_time(self) -> float:
        """Return the average method execution time."""
        if self.call_count == 0:
            return 0.0
        return self.total_time / self.call_count

    def percentile(self, p: float) -> float:
        """Calculate the p-th percentile (0-100) from samples."""
        if not self._samples:
            return 0.0
        sorted_s = sorted(self._samples)
        k = (p / 100.0) * (len(sorted_s) - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_s[int(k)]
        return sorted_s[f] * (c - k) + sorted_s[c] * (k - f)

    @property
    def p50(self) -> float:
        """Return the 50th percentile latency."""
        return self.percentile(50)

    @property
    def p95(self) -> float:
        """Return the 95th percentile latency."""
        return self.percentile(95)

    @property
    def p99(self) -> float:
        """Return the 99th percentile latency."""
        return self.percentile(99)

    @property
    def stddev(self) -> float:
        """Return the standard deviation of sample times."""
        if len(self._samples) < 2:
            return 0.0
        return statistics.stdev(self._samples)

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation."""
        return {
            "method": self.method_name,
            "calls": self.call_count,
            "total_ms": round(self.total_time * 1000, 3),
            "avg_ms": round(self.avg_time * 1000, 3),
            "min_ms": round(self.min_time * 1000, 3) if self.min_time != float("inf") else 0.0,
            "max_ms": round(self.max_time * 1000, 3),
            "p50_ms": round(self.p50 * 1000, 3),
            "p95_ms": round(self.p95 * 1000, 3),
            "p99_ms": round(self.p99 * 1000, 3),
            "stddev_ms": round(self.stddev * 1000, 3),
        }


@dataclass
class ModuleProfile:
    """Aggregated profile for a module."""
    module_name: str
    methods: dict[str, MethodProfile] = field(default_factory=dict)
    _snapshots: list[dict[str, Any]] = field(default_factory=list)
    start_time: float = field(default_factory=time.monotonic)
    memory_peak_kb: float = 0.0
    memory_current_kb: float = 0.0

    def get_method(self, method_name: str) -> MethodProfile:
        """Get or create a method profile."""
        if method_name not in self.methods:
            self.methods[method_name] = MethodProfile(method_name=method_name)
        return self.methods[method_name]

    @property
    def total_calls(self) -> int:
        """Return the total number of method calls across all methods."""
        return sum(m.call_count for m in self.methods.values())

    @property
    def total_time(self) -> float:
        """Return the total execution time across all methods."""
        return sum(m.total_time for m in self.methods.values())

    @property
    def hottest_method(self) -> str | None:
        """Return the method consuming the most total time."""
        if not self.methods:
            return None
        return max(self.methods.values(), key=lambda m: m.total_time).method_name

    @property
    def slowest_method(self) -> str | None:
        """Return the method with the highest average time."""
        methods_with_calls = [m for m in self.methods.values() if m.call_count > 0]
        if not methods_with_calls:
            return None
        return max(methods_with_calls, key=lambda m: m.avg_time).method_name

    def take_snapshot(self, label: str = "") -> dict[str, Any]:
        """Take a point-in-time snapshot of the profile."""
        snap = {
            "timestamp": time.time(),
            "label": label,
            "elapsed_s": round(time.monotonic() - self.start_time, 3),
            "total_calls": self.total_calls,
            "total_time_ms": round(self.total_time * 1000, 3),
            "methods": {
                name: mp.to_dict() for name, mp in self.methods.items()
            },
            "memory_peak_kb": self.memory_peak_kb,
            "memory_current_kb": self.memory_current_kb,
        }
        self._snapshots.append(snap)
        return snap

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation."""
        return {
            "module_name": self.module_name,
            "total_calls": self.total_calls,
            "total_time_ms": round(self.total_time * 1000, 3),
            "hottest_method": self.hottest_method,
            "slowest_method": self.slowest_method,
            "memory_peak_kb": self.memory_peak_kb,
            "memory_current_kb": self.memory_current_kb,
            "methods": {
                name: mp.to_dict() for name, mp in self.methods.items()
            },
            "snapshot_count": len(self._snapshots),
        }


class ModuleProfiler:
    """Thread-safe module performance profiler.

    Provides method-level profiling with percentile stats,
    memory tracking, and snapshot comparison.
    """

    def __init__(self) -> None:
        """Initialize the ModuleProfiler."""
        self._lock = threading.Lock()
        self._modules: dict[str, ModuleProfile] = {}
        self._enabled = True

    @property
    def enabled(self) -> bool:
        """Return whether profiling is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set whether profiling is enabled."""
        self._enabled = value

    def _get_or_create(self, module_name: str) -> ModuleProfile:
        """Get or create a module profile (caller must hold lock)."""
        if module_name not in self._modules:
            self._modules[module_name] = ModuleProfile(module_name=module_name)
        return self._modules[module_name]

    @contextmanager
    def trace(self, module_name: str, method_name: str) -> Iterator[None]:
        """Context manager to time a method execution.

        Usage::

            with profiler.trace("sfp_dns", "handleEvent"):
                process_event(event)
        """
        if not self._enabled:
            yield
            return

        start = time.monotonic()
        try:
            yield
        finally:
            duration = time.monotonic() - start
            with self._lock:
                profile = self._get_or_create(module_name)
                mp = profile.get_method(method_name)
                mp.record(duration)

    def record(self, module_name: str, method_name: str,
               duration: float) -> None:
        """Manually record a method invocation duration."""
        if not self._enabled:
            return
        with self._lock:
            profile = self._get_or_create(module_name)
            mp = profile.get_method(method_name)
            mp.record(duration)

    def profile(self, module_name: str, method_name: str = "") -> Callable:
        """Decorator to profile a function.

        Usage::

            @profiler.profile("sfp_dns")
            def fetch_records(domain):
                ...

            @profiler.profile("sfp_dns", "custom_name")
            def another_method():
                ...
        """
        def decorator(func: Callable) -> Callable:
            """Wrap a function with profiling."""
            name = method_name or func.__qualname__

            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                """Execute the function with profiling."""
                with self.trace(module_name, name):
                    return func(*args, **kwargs)

            return wrapper
        return decorator

    def update_memory(self, module_name: str, current_kb: float,
                      peak_kb: float = 0.0) -> None:
        """Update memory usage for a module."""
        with self._lock:
            profile = self._get_or_create(module_name)
            profile.memory_current_kb = current_kb
            if peak_kb > profile.memory_peak_kb:
                profile.memory_peak_kb = peak_kb

    def snapshot(self, module_name: str, label: str = "") -> dict[str, Any]:
        """Take a snapshot of a module's profile."""
        with self._lock:
            profile = self._get_or_create(module_name)
            return profile.take_snapshot(label)

    def get_profile(self, module_name: str) -> dict[str, Any] | None:
        """Get the profile for a specific module."""
        with self._lock:
            profile = self._modules.get(module_name)
            if profile:
                return profile.to_dict()
            return None

    def get_all_profiles(self) -> dict[str, dict[str, Any]]:
        """Get profiles for all modules."""
        with self._lock:
            return {
                name: profile.to_dict()
                for name, profile in self._modules.items()
            }

    def get_top_modules(self, by: str = "total_time",
                        limit: int = 10) -> list[dict[str, Any]]:
        """Get the top N modules by a metric.

        Args:
            by: Sort key - 'total_time', 'total_calls', 'memory_peak_kb'
            limit: Number of results
        """
        with self._lock:
            profiles = list(self._modules.values())

        sort_keys = {
            "total_time": lambda p: p.total_time,
            "total_calls": lambda p: p.total_calls,
            "memory_peak_kb": lambda p: p.memory_peak_kb,
        }

        key_fn = sort_keys.get(by, sort_keys["total_time"])
        profiles.sort(key=key_fn, reverse=True)

        return [p.to_dict() for p in profiles[:limit]]

    def get_slow_methods(self, threshold_ms: float = 1000.0,
                         limit: int = 20) -> list[dict[str, Any]]:
        """Find methods exceeding a latency threshold.

        Args:
            threshold_ms: Minimum average time in milliseconds
            limit: Maximum results
        """
        threshold_s = threshold_ms / 1000.0
        results = []

        with self._lock:
            for mod_name, profile in self._modules.items():
                for method in profile.methods.values():
                    if method.avg_time >= threshold_s and method.call_count > 0:
                        entry = method.to_dict()
                        entry["module"] = mod_name
                        results.append(entry)

        results.sort(key=lambda r: r["avg_ms"], reverse=True)
        return results[:limit]

    def compare_snapshots(self, module_name: str,
                          idx_a: int = -2,
                          idx_b: int = -1) -> dict[str, Any] | None:
        """Compare two snapshots for a module.

        By default compares the last two snapshots.

        Returns a dict with delta information for each method.
        """
        with self._lock:
            profile = self._modules.get(module_name)
            if not profile or len(profile._snapshots) < 2:
                return None

            try:
                snap_a = profile._snapshots[idx_a]
                snap_b = profile._snapshots[idx_b]
            except IndexError:
                return None

        delta_time = snap_b["elapsed_s"] - snap_a["elapsed_s"]
        delta_calls = snap_b["total_calls"] - snap_a["total_calls"]

        method_deltas = {}
        all_methods = set(snap_a.get("methods", {}).keys()) | set(snap_b.get("methods", {}).keys())

        for method in all_methods:
            a_data = snap_a.get("methods", {}).get(method, {})
            b_data = snap_b.get("methods", {}).get(method, {})
            method_deltas[method] = {
                "calls_delta": b_data.get("calls", 0) - a_data.get("calls", 0),
                "total_ms_delta": round(
                    b_data.get("total_ms", 0) - a_data.get("total_ms", 0), 3
                ),
                "avg_ms_before": a_data.get("avg_ms", 0),
                "avg_ms_after": b_data.get("avg_ms", 0),
            }

        return {
            "module": module_name,
            "time_delta_s": round(delta_time, 3),
            "calls_delta": delta_calls,
            "throughput_delta": round(
                delta_calls / delta_time if delta_time > 0 else 0, 3
            ),
            "methods": method_deltas,
        }

    def reset(self, module_name: str | None = None) -> None:
        """Reset profiling data.

        Args:
            module_name: If provided, reset only this module. Otherwise reset all.
        """
        with self._lock:
            if module_name:
                self._modules.pop(module_name, None)
            else:
                self._modules.clear()

    def get_summary(self) -> dict[str, Any]:
        """Get a compact summary across all modules."""
        with self._lock:
            total_calls = sum(p.total_calls for p in self._modules.values())
            total_time = sum(p.total_time for p in self._modules.values())
            total_methods = sum(len(p.methods) for p in self._modules.values())

            return {
                "modules_profiled": len(self._modules),
                "total_methods": total_methods,
                "total_calls": total_calls,
                "total_time_ms": round(total_time * 1000, 3),
                "enabled": self._enabled,
            }


# Singleton
_profiler: ModuleProfiler | None = None


def get_module_profiler() -> ModuleProfiler:
    """Get the singleton module profiler."""
    global _profiler
    if _profiler is None:
        _profiler = ModuleProfiler()
    return _profiler
