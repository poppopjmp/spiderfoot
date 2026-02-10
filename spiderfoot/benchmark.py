#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         benchmark
# Purpose:      Performance benchmarking suite for SpiderFoot services.
#               Measures throughput, latency, and resource usage of core
#               subsystems.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Benchmark Suite

Benchmarks core subsystems (EventBus, Cache, HTTP, DNS, Worker Pool,
Rate Limiter, etc.) and produces a structured report::

    from spiderfoot.benchmark import BenchmarkSuite

    suite = BenchmarkSuite()
    suite.add(EventBusBenchmark())
    suite.add(CacheBenchmark())
    report = suite.run_all()
    print(report.summary())
"""

from __future__ import annotations

import gc
import logging
import os
import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

log = logging.getLogger("spiderfoot.benchmark")

__all__ = [
    "BenchmarkResult",
    "BenchmarkReport",
    "Benchmark",
    "BenchmarkSuite",
    "EventBusBenchmark",
    "CacheBenchmark",
    "RateLimiterBenchmark",
    "WorkerPoolBenchmark",
    "SerializationBenchmark",
    "run_benchmarks",
]


# ------------------------------------------------------------------
# Result / Report
# ------------------------------------------------------------------

@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    operation: str
    iterations: int
    total_time: float       # seconds
    times: list[float] = field(default_factory=list)  # per-iteration
    errors: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ops_per_sec(self) -> float:
        if self.total_time <= 0:
            return 0.0
        return self.iterations / self.total_time

    @property
    def avg_latency_ms(self) -> float:
        if not self.times:
            return self.total_time / max(self.iterations, 1) * 1000
        return statistics.mean(self.times) * 1000

    @property
    def p50_ms(self) -> float:
        if not self.times:
            return 0.0
        return statistics.median(self.times) * 1000

    @property
    def p95_ms(self) -> float:
        if len(self.times) < 2:
            return self.avg_latency_ms
        sorted_t = sorted(self.times)
        idx = int(len(sorted_t) * 0.95)
        return sorted_t[min(idx, len(sorted_t) - 1)] * 1000

    @property
    def p99_ms(self) -> float:
        if len(self.times) < 2:
            return self.avg_latency_ms
        sorted_t = sorted(self.times)
        idx = int(len(sorted_t) * 0.99)
        return sorted_t[min(idx, len(sorted_t) - 1)] * 1000

    @property
    def stdev_ms(self) -> float:
        if len(self.times) < 2:
            return 0.0
        return statistics.stdev(self.times) * 1000

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "operation": self.operation,
            "iterations": self.iterations,
            "total_time_s": round(self.total_time, 4),
            "ops_per_sec": round(self.ops_per_sec, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 4),
            "p50_ms": round(self.p50_ms, 4),
            "p95_ms": round(self.p95_ms, 4),
            "p99_ms": round(self.p99_ms, 4),
            "stdev_ms": round(self.stdev_ms, 4),
            "errors": self.errors,
            "metadata": self.metadata,
        }

    def summary_line(self) -> str:
        return (
            f"{self.name}/{self.operation}: "
            f"{self.ops_per_sec:,.0f} ops/s  "
            f"avg={self.avg_latency_ms:.3f}ms  "
            f"p95={self.p95_ms:.3f}ms  "
            f"p99={self.p99_ms:.3f}ms  "
            f"({self.iterations} iters, {self.errors} errors)"
        )


@dataclass
class BenchmarkReport:
    """Collection of benchmark results."""

    results: list[BenchmarkResult] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float = 0.0
    system_info: dict[str, Any] = field(default_factory=dict)

    @property
    def total_time(self) -> float:
        return self.completed_at - self.started_at

    def add(self, result: BenchmarkResult) -> None:
        self.results.append(result)

    def summary(self) -> str:
        lines = [
            "=" * 72,
            "SpiderFoot Benchmark Report",
            "=" * 72,
        ]
        if self.system_info:
            lines.append(f"Python: {self.system_info.get('python', 'N/A')}")
            lines.append(f"OS: {self.system_info.get('os', 'N/A')}")
            lines.append(f"CPUs: {self.system_info.get('cpus', 'N/A')}")
            lines.append("")

        for r in self.results:
            lines.append(r.summary_line())

        lines.append("")
        lines.append(f"Total time: {self.total_time:.2f}s")
        lines.append("=" * 72)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "system_info": self.system_info,
            "total_time_s": round(self.total_time, 2),
            "results": [r.to_dict() for r in self.results],
        }


# ------------------------------------------------------------------
# Base Benchmark
# ------------------------------------------------------------------

class Benchmark:
    """Base class for benchmarks."""

    name: str = "base"

    def setup(self) -> None:
        """Called once before the benchmark runs."""
        pass

    def teardown(self) -> None:
        """Called once after the benchmark finishes."""
        pass

    def run(self, iterations: int = 10000) -> list[BenchmarkResult]:
        """Execute the benchmark and return results."""
        raise NotImplementedError


# ------------------------------------------------------------------
# Timing helper
# ------------------------------------------------------------------

def _timed_loop(operation_name: str, bench_name: str,
                fn: Callable[[], Any], iterations: int,
                **metadata: Any) -> BenchmarkResult:
    """Run *fn* for *iterations* and collect timing data."""
    times = []
    errors = 0
    gc.disable()
    try:
        start = time.perf_counter()
        for _ in range(iterations):
            t0 = time.perf_counter()
            try:
                fn()
            except Exception:
                errors += 1
            t1 = time.perf_counter()
            times.append(t1 - t0)
        total = time.perf_counter() - start
    finally:
        gc.enable()

    return BenchmarkResult(
        name=bench_name,
        operation=operation_name,
        iterations=iterations,
        total_time=total,
        times=times,
        errors=errors,
        metadata=metadata,
    )


# ------------------------------------------------------------------
# Built-in benchmarks
# ------------------------------------------------------------------

class EventBusBenchmark(Benchmark):
    """Benchmark the in-memory EventBus publish/subscribe."""

    name = "EventBus"

    def __init__(self):
        self._bus = None

    def setup(self) -> None:
        try:
            from spiderfoot.eventbus.memory import InMemoryEventBus
            self._bus = InMemoryEventBus()
            self._received = 0

            def handler(envelope):
                self._received += 1

            self._bus.subscribe("bench.topic", handler)
        except ImportError:
            self._bus = None

    def teardown(self) -> None:
        if self._bus:
            try:
                self._bus.shutdown()
            except Exception as e:
                log.debug("EventBus shutdown failed during teardown: %s", e)

    def run(self, iterations: int = 10000) -> list[BenchmarkResult]:
        results = []
        if self._bus is None:
            return results

        def publish():
            self._bus.publish("bench.topic", {"data": "test"})

        results.append(
            _timed_loop("publish", self.name, publish, iterations)
        )
        return results


class CacheBenchmark(Benchmark):
    """Benchmark the in-memory cache."""

    name = "Cache"

    def __init__(self):
        self._cache = None

    def setup(self) -> None:
        try:
            from spiderfoot.cache_service import MemoryCache
            self._cache = MemoryCache(max_size=100000)
        except ImportError:
            self._cache = None

    def run(self, iterations: int = 10000) -> list[BenchmarkResult]:
        results = []
        if self._cache is None:
            return results

        # Write
        i_counter = [0]

        def cache_put():
            self._cache.put(f"key_{i_counter[0]}", f"value_{i_counter[0]}")
            i_counter[0] += 1

        results.append(
            _timed_loop("put", self.name, cache_put, iterations)
        )

        # Read (existing keys)
        i_counter[0] = 0

        def cache_get():
            self._cache.get(f"key_{i_counter[0]}")
            i_counter[0] += 1

        results.append(
            _timed_loop("get", self.name, cache_get, iterations)
        )

        # Read miss
        def cache_miss():
            self._cache.get("nonexistent_key")

        results.append(
            _timed_loop("get_miss", self.name, cache_miss, iterations)
        )

        return results


class RateLimiterBenchmark(Benchmark):
    """Benchmark the rate limiter."""

    name = "RateLimiter"

    def __init__(self):
        self._limiter = None

    def setup(self) -> None:
        try:
            from spiderfoot.rate_limiter import RateLimiterService, RateLimit
            self._limiter = RateLimiterService()
            self._limiter.set_limit(
                "bench",
                RateLimit(requests=1_000_000, window=60.0)
            )
        except ImportError:
            self._limiter = None

    def run(self, iterations: int = 10000) -> list[BenchmarkResult]:
        results = []
        if self._limiter is None:
            return results

        def allow_check():
            self._limiter.allow("bench")

        results.append(
            _timed_loop("allow", self.name, allow_check, iterations)
        )
        return results


class WorkerPoolBenchmark(Benchmark):
    """Benchmark task submission to the worker pool."""

    name = "WorkerPool"

    def run(self, iterations: int = 5000) -> list[BenchmarkResult]:
        import concurrent.futures
        results = []

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)

        def submit_task():
            f = pool.submit(lambda: None)
            f.result()  # wait for completion

        results.append(
            _timed_loop("submit_and_wait", self.name, submit_task, iterations)
        )
        pool.shutdown(wait=True)
        return results


class SerializationBenchmark(Benchmark):
    """Benchmark JSON serialization (event-like payloads)."""

    name = "Serialization"

    def __init__(self):
        self._payload = {
            "eventType": "IP_ADDRESS",
            "data": "192.168.1.1",
            "module": "sfp_dnsresolve",
            "confidence": 100,
            "visibility": 100,
            "risk": 0,
            "source": "ROOT",
            "generated": time.time(),
            "extra": {
                "asn": "AS12345",
                "country": "US",
                "isp": "Example ISP",
            },
        }

    def run(self, iterations: int = 10000) -> list[BenchmarkResult]:
        import json
        results = []
        payload = self._payload

        serialized = json.dumps(payload)

        def serialize():
            json.dumps(payload)

        results.append(
            _timed_loop("json_dumps", self.name, serialize, iterations)
        )

        def deserialize():
            json.loads(serialized)

        results.append(
            _timed_loop("json_loads", self.name, deserialize, iterations)
        )
        return results


class ThreadingBenchmark(Benchmark):
    """Benchmark thread creation and lock contention."""

    name = "Threading"

    def run(self, iterations: int = 2000) -> list[BenchmarkResult]:
        results = []

        # Lock acquire/release
        lock = threading.Lock()

        def lock_cycle():
            lock.acquire()
            lock.release()

        results.append(
            _timed_loop("lock_acquire_release", self.name, lock_cycle, iterations * 5)
        )

        # Thread creation + join
        def thread_create():
            t = threading.Thread(target=lambda: None)
            t.start()
            t.join()

        results.append(
            _timed_loop("thread_create_join", self.name, thread_create, iterations)
        )
        return results


class HashBenchmark(Benchmark):
    """Benchmark hashing (used for event fingerprinting)."""

    name = "Hashing"

    def run(self, iterations: int = 10000) -> list[BenchmarkResult]:
        import hashlib
        results = []

        data = b"192.168.1.1:IP_ADDRESS:sfp_dnsresolve:example.com"

        def sha256_hash():
            hashlib.sha256(data).hexdigest()

        results.append(
            _timed_loop("sha256", self.name, sha256_hash, iterations)
        )

        def md5_hash():
            hashlib.md5(data).hexdigest()

        results.append(
            _timed_loop("md5", self.name, md5_hash, iterations)
        )
        return results


# ------------------------------------------------------------------
# Suite
# ------------------------------------------------------------------

class BenchmarkSuite:
    """Manages and runs a collection of benchmarks."""

    def __init__(self):
        self._benchmarks: list[Benchmark] = []

    def add(self, benchmark: Benchmark) -> BenchmarkSuite:
        self._benchmarks.append(benchmark)
        return self

    def run_all(self, iterations: int = 10000) -> BenchmarkReport:
        """Run all registered benchmarks and produce a report."""
        report = BenchmarkReport(started_at=time.time())
        report.system_info = _system_info()

        for bench in self._benchmarks:
            log.info("Running benchmark: %s", bench.name)
            try:
                bench.setup()
                results = bench.run(iterations)
                for r in results:
                    report.add(r)
            except Exception as e:
                log.error("Benchmark %s failed: %s", bench.name, e)
                report.add(BenchmarkResult(
                    name=bench.name, operation="FAILED",
                    iterations=0, total_time=0, errors=1,
                    metadata={"error": str(e)},
                ))
            finally:
                try:
                    bench.teardown()
                except Exception as e:
                    log.debug("Benchmark '%s' teardown failed: %s", bench.name, e)

        report.completed_at = time.time()
        return report


def _system_info() -> dict:
    import platform
    import sys
    return {
        "python": sys.version,
        "os": platform.platform(),
        "cpus": os.cpu_count() or 1,
        "arch": platform.machine(),
    }


# ------------------------------------------------------------------
# Convenience
# ------------------------------------------------------------------

def run_benchmarks(iterations: int = 10000) -> BenchmarkReport:
    """Run the built-in benchmark suite."""
    suite = BenchmarkSuite()
    suite.add(SerializationBenchmark())
    suite.add(HashBenchmark())
    suite.add(ThreadingBenchmark())
    suite.add(CacheBenchmark())
    suite.add(RateLimiterBenchmark())
    suite.add(EventBusBenchmark())
    suite.add(WorkerPoolBenchmark())
    return suite.run_all(iterations)
