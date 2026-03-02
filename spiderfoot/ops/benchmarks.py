# -------------------------------------------------------------------------------
# Name:         spiderfoot/benchmarks.py
# Purpose:      Throughput benchmarking and tuning utilities (ROADMAP Cycles 131-150)
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2025-07-11
# Copyright:    (c) Agostino Panico 2025
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Throughput benchmarking & performance regression utilities for SpiderFoot v6.

Implements ROADMAP Cycles 131-150:

- **Cycle 131:** `ScanBenchmark` — measure events/second, memory, DB write
  throughput for a standard scan profile.
- **Cycles 132-140:** `PostgresTuningAdvisor` — recommend ``shared_buffers``,
  ``work_mem``, ``max_parallel_workers`` for scan workloads.
- **Cycles 141-150:** `PerformanceRegressionRunner` — CI-compatible benchmark
  runner with time budgets and threshold alerts.
"""

from __future__ import annotations

import logging
import os
import statistics
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("spiderfoot.ops.benchmarks")


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 131 — ScanBenchmark
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    events_produced: int = 0
    db_writes: int = 0
    errors: int = 0
    peak_memory_mb: float = 0.0
    samples: list[float] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return self.finished_at - self.started_at

    @property
    def events_per_second(self) -> float:
        if self.duration_s <= 0:
            return 0.0
        return self.events_produced / self.duration_s

    @property
    def db_writes_per_second(self) -> float:
        if self.duration_s <= 0:
            return 0.0
        return self.db_writes / self.duration_s

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "duration_s": round(self.duration_s, 3),
            "events_produced": self.events_produced,
            "events_per_second": round(self.events_per_second, 2),
            "db_writes": self.db_writes,
            "db_writes_per_second": round(self.db_writes_per_second, 2),
            "errors": self.errors,
            "peak_memory_mb": round(self.peak_memory_mb, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 3) if self.samples else None,
            "p95_latency_ms": round(self.p95_latency_ms, 3) if self.samples else None,
            "p99_latency_ms": round(self.p99_latency_ms, 3) if self.samples else None,
        }

    @property
    def p50_latency_ms(self) -> float:
        if not self.samples:
            return 0.0
        return _percentile(self.samples, 50) * 1000

    @property
    def p95_latency_ms(self) -> float:
        if not self.samples:
            return 0.0
        return _percentile(self.samples, 95) * 1000

    @property
    def p99_latency_ms(self) -> float:
        if not self.samples:
            return 0.0
        return _percentile(self.samples, 99) * 1000


def _percentile(data: list[float], pct: float) -> float:
    """Compute the given percentile of a sorted list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (pct / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    d0 = sorted_data[f] * (c - k)
    d1 = sorted_data[c] * (k - f)
    return d0 + d1


class ScanBenchmark:
    """Measure scan throughput metrics.

    Usage::

        bench = ScanBenchmark("quick-recon baseline")
        bench.start()

        for event in scan_events():
            t0 = time.monotonic()
            process(event)
            bench.record_event(time.monotonic() - t0)

        bench.record_db_writes(len(events))
        result = bench.finish()
        print(result.to_dict())
    """

    def __init__(self, name: str = "benchmark") -> None:
        self._result = BenchmarkResult(name=name)
        self._running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Mark the benchmark start time."""
        self._result.started_at = time.monotonic()
        self._running = True

    def record_event(self, latency_s: float = 0.0) -> None:
        """Record a single event produced.

        Args:
            latency_s: Time taken to produce this event (seconds).
        """
        with self._lock:
            self._result.events_produced += 1
            if latency_s > 0:
                self._result.samples.append(latency_s)

    def record_db_writes(self, count: int) -> None:
        """Record ``count`` successful DB writes."""
        with self._lock:
            self._result.db_writes += count

    def record_error(self) -> None:
        with self._lock:
            self._result.errors += 1

    def record_memory(self, rss_mb: float) -> None:
        with self._lock:
            if rss_mb > self._result.peak_memory_mb:
                self._result.peak_memory_mb = rss_mb

    def finish(self) -> BenchmarkResult:
        """Mark the benchmark end time and return results."""
        self._result.finished_at = time.monotonic()
        self._running = False
        return self._result

    @property
    def is_running(self) -> bool:
        return self._running


class MultiBenchmark:
    """Run multiple benchmarks and aggregate results.

    Usage::

        multi = MultiBenchmark()
        multi.add_result(result1)
        multi.add_result(result2)
        report = multi.report()
    """

    def __init__(self) -> None:
        self._results: list[BenchmarkResult] = []

    def add_result(self, result: BenchmarkResult) -> None:
        self._results.append(result)

    @property
    def results(self) -> list[BenchmarkResult]:
        return list(self._results)

    def report(self) -> dict[str, Any]:
        """Aggregate report across all benchmark runs."""
        if not self._results:
            return {"error": "No benchmark results"}

        durations = [r.duration_s for r in self._results]
        eps = [r.events_per_second for r in self._results]
        dps = [r.db_writes_per_second for r in self._results]

        return {
            "runs": len(self._results),
            "total_events": sum(r.events_produced for r in self._results),
            "total_db_writes": sum(r.db_writes for r in self._results),
            "total_errors": sum(r.errors for r in self._results),
            "avg_duration_s": round(statistics.mean(durations), 3),
            "avg_events_per_second": round(statistics.mean(eps), 2),
            "avg_db_writes_per_second": round(statistics.mean(dps), 2),
            "max_events_per_second": round(max(eps), 2),
            "peak_memory_mb": round(max(r.peak_memory_mb for r in self._results), 2),
            "results": [r.to_dict() for r in self._results],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Cycles 132-140 — PostgreSQL Tuning Advisor
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PgTuningRecommendation:
    """A single PostgreSQL tuning recommendation."""

    parameter: str
    current_value: str = ""
    recommended_value: str = ""
    reason: str = ""
    impact: str = "medium"  # low, medium, high

    def to_dict(self) -> dict[str, str]:
        return {
            "parameter": self.parameter,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "reason": self.reason,
            "impact": self.impact,
        }


class PostgresTuningAdvisor:
    """Generate PostgreSQL tuning recommendations for SpiderFoot scan workloads.

    Recommendations are based on the system's total RAM and the scan
    workload profile (write-heavy, many concurrent connections).

    Usage::

        advisor = PostgresTuningAdvisor(total_ram_gb=16, max_connections=100)
        recs = advisor.recommend()
        for r in recs:
            print(f"{r.parameter} = {r.recommended_value}  # {r.reason}")
    """

    # Standard SpiderFoot scan workload characteristics:
    # - Write-heavy (scan results, event storage)
    # - Read queries for deduplication checks
    # - Mixed read/write during scan, read-heavy during report generation
    # - Moderate connection count (workers * parallel modules)

    def __init__(
        self,
        total_ram_gb: float = 0.0,
        max_connections: int = 100,
        *,
        ssd_storage: bool = True,
        cpu_cores: int = 0,
    ) -> None:
        self.total_ram_gb = total_ram_gb or self._detect_ram_gb()
        self.max_connections = max_connections
        self.ssd_storage = ssd_storage
        self.cpu_cores = cpu_cores or self._detect_cores()

    @staticmethod
    def _detect_ram_gb() -> float:
        """Detect total system RAM in GB."""
        try:
            import psutil
            return psutil.virtual_memory().total / (1024 ** 3)
        except ImportError:
            pass

        # Linux fallback
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb / (1024 * 1024)
        except (FileNotFoundError, PermissionError):
            pass

        return 8.0  # Conservative default

    @staticmethod
    def _detect_cores() -> int:
        try:
            return os.cpu_count() or 4
        except Exception:
            return 4

    def recommend(self) -> list[PgTuningRecommendation]:
        """Generate tuning recommendations."""
        recs: list[PgTuningRecommendation] = []
        ram = self.total_ram_gb
        cores = self.cpu_cores

        # shared_buffers — 25% of total RAM, max 8GB
        shared_buffers_gb = min(ram * 0.25, 8.0)
        recs.append(PgTuningRecommendation(
            parameter="shared_buffers",
            recommended_value=f"{max(int(shared_buffers_gb * 1024), 256)}MB",
            reason=f"25% of {ram:.1f}GB total RAM (capped at 8GB)",
            impact="high",
        ))

        # effective_cache_size — 75% of total RAM
        ecs_gb = ram * 0.75
        recs.append(PgTuningRecommendation(
            parameter="effective_cache_size",
            recommended_value=f"{int(ecs_gb * 1024)}MB",
            reason=f"75% of {ram:.1f}GB total RAM — helps query planner",
            impact="medium",
        ))

        # work_mem — (RAM * 0.25) / max_connections
        work_mem_mb = max(int((ram * 1024 * 0.25) / self.max_connections), 4)
        recs.append(PgTuningRecommendation(
            parameter="work_mem",
            recommended_value=f"{work_mem_mb}MB",
            reason=f"(25% of RAM) / {self.max_connections} connections",
            impact="medium",
        ))

        # maintenance_work_mem — 5% of RAM, max 2GB
        maint_mb = min(int(ram * 1024 * 0.05), 2048)
        recs.append(PgTuningRecommendation(
            parameter="maintenance_work_mem",
            recommended_value=f"{max(maint_mb, 64)}MB",
            reason="5% of total RAM — speeds VACUUM, CREATE INDEX",
            impact="medium",
        ))

        # max_parallel_workers_per_gather
        parallel = max(min(cores // 2, 4), 1)
        recs.append(PgTuningRecommendation(
            parameter="max_parallel_workers_per_gather",
            recommended_value=str(parallel),
            reason=f"{cores} CPU cores → {parallel} parallel workers per query",
            impact="medium",
        ))

        # max_parallel_workers
        max_parallel = max(min(cores, 8), 2)
        recs.append(PgTuningRecommendation(
            parameter="max_parallel_workers",
            recommended_value=str(max_parallel),
            reason=f"Based on {cores} CPU cores",
            impact="medium",
        ))

        # wal_buffers — auto is usually good, but set explicitly for large systems
        wal_mb = max(min(int(shared_buffers_gb * 1024 / 32), 64), 8)
        recs.append(PgTuningRecommendation(
            parameter="wal_buffers",
            recommended_value=f"{wal_mb}MB",
            reason="1/32 of shared_buffers, capped at 64MB",
            impact="low",
        ))

        # random_page_cost — lower for SSD
        if self.ssd_storage:
            recs.append(PgTuningRecommendation(
                parameter="random_page_cost",
                recommended_value="1.1",
                reason="SSD storage detected — sequential and random IO roughly equal",
                impact="medium",
            ))

        # checkpoint_completion_target
        recs.append(PgTuningRecommendation(
            parameter="checkpoint_completion_target",
            recommended_value="0.9",
            reason="Spread checkpoint writes over 90% of the interval — reduces IO spikes",
            impact="low",
        ))

        # max_wal_size — larger for write-heavy scans
        recs.append(PgTuningRecommendation(
            parameter="max_wal_size",
            recommended_value="2GB",
            reason="SpiderFoot scans are write-heavy — larger WAL reduces checkpoint frequency",
            impact="medium",
        ))

        return recs

    def summary(self) -> dict[str, Any]:
        """Return recommendations as a dict suitable for JSON output."""
        recs = self.recommend()
        return {
            "system": {
                "total_ram_gb": round(self.total_ram_gb, 1),
                "cpu_cores": self.cpu_cores,
                "max_connections": self.max_connections,
                "ssd_storage": self.ssd_storage,
            },
            "recommendations": [r.to_dict() for r in recs],
        }

    def generate_config(self) -> str:
        """Generate a PostgreSQL configuration snippet.

        Returns a multi-line string suitable for appending to
        ``postgresql.conf`` or passing via ``-c`` arguments.
        """
        lines = [
            "# SpiderFoot scan-optimized PostgreSQL settings",
            f"# Generated for {self.total_ram_gb:.1f}GB RAM, {self.cpu_cores} cores, {self.max_connections} connections",
            "",
        ]
        for rec in self.recommend():
            lines.append(f"# {rec.reason}")
            lines.append(f"{rec.parameter} = '{rec.recommended_value}'")
            lines.append("")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Cycles 141-150 — Performance Regression Runner
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PerformanceThreshold:
    """Threshold definition for performance regression detection."""

    metric: str
    operator: str  # ">=", "<=", ">", "<"
    value: float
    description: str = ""

    def check(self, actual: float) -> bool:
        """Return True if the actual value passes the threshold."""
        ops = {
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
        }
        op_fn = ops.get(self.operator)
        if op_fn is None:
            raise ValueError(f"Unknown operator: {self.operator}")
        return op_fn(actual, self.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "operator": self.operator,
            "value": self.value,
            "description": self.description,
        }


@dataclass
class ThresholdResult:
    """Result of checking a single threshold."""

    threshold: PerformanceThreshold
    actual_value: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.threshold.metric,
            "threshold": f"{self.threshold.operator} {self.threshold.value}",
            "actual": round(self.actual_value, 4),
            "passed": self.passed,
            "description": self.threshold.description,
        }


class PerformanceRegressionRunner:
    """CI-compatible performance regression test runner.

    Runs a benchmark function, collects results, and compares against
    defined thresholds.  Returns exit code 0 (pass) or 1 (fail) for CI.

    Usage::

        runner = PerformanceRegressionRunner()
        runner.add_threshold(PerformanceThreshold(
            metric="events_per_second",
            operator=">=",
            value=100.0,
            description="Minimum 100 events/s for quick-recon profile",
        ))
        runner.add_threshold(PerformanceThreshold(
            metric="p95_latency_ms",
            operator="<=",
            value=50.0,
            description="P95 event latency must be under 50ms",
        ))

        result = runner.run(my_benchmark_fn)
        if not result["all_passed"]:
            sys.exit(1)
    """

    # Default thresholds for a standard SpiderFoot quick-recon scan
    DEFAULT_THRESHOLDS = [
        PerformanceThreshold(
            metric="events_per_second",
            operator=">=",
            value=50.0,
            description="Minimum event throughput for quick-recon",
        ),
        PerformanceThreshold(
            metric="p95_latency_ms",
            operator="<=",
            value=100.0,
            description="P95 event processing latency",
        ),
        PerformanceThreshold(
            metric="errors",
            operator="<=",
            value=0,
            description="No errors during benchmark",
        ),
        PerformanceThreshold(
            metric="peak_memory_mb",
            operator="<=",
            value=2048.0,
            description="Peak memory must not exceed 2GB",
        ),
    ]

    def __init__(self, use_defaults: bool = True) -> None:
        self._thresholds: list[PerformanceThreshold] = []
        if use_defaults:
            self._thresholds.extend(self.DEFAULT_THRESHOLDS)

    def add_threshold(self, threshold: PerformanceThreshold) -> None:
        self._thresholds.append(threshold)

    def clear_thresholds(self) -> None:
        self._thresholds.clear()

    @property
    def thresholds(self) -> list[PerformanceThreshold]:
        return list(self._thresholds)

    def check_result(self, benchmark_result: BenchmarkResult) -> dict[str, Any]:
        """Check a benchmark result against all thresholds.

        Args:
            benchmark_result: The completed benchmark to check.

        Returns:
            Dict with ``all_passed``, ``results``, and ``summary``.
        """
        results: list[ThresholdResult] = []
        result_dict = benchmark_result.to_dict()

        for threshold in self._thresholds:
            actual = result_dict.get(threshold.metric)
            if actual is None:
                # Try direct attribute access
                actual = getattr(benchmark_result, threshold.metric, None)
            if actual is None:
                results.append(ThresholdResult(
                    threshold=threshold,
                    actual_value=0.0,
                    passed=False,
                ))
                continue

            passed = threshold.check(float(actual))
            results.append(ThresholdResult(
                threshold=threshold,
                actual_value=float(actual),
                passed=passed,
            ))

        all_passed = all(r.passed for r in results)
        failed = [r for r in results if not r.passed]

        return {
            "all_passed": all_passed,
            "passed_count": sum(1 for r in results if r.passed),
            "failed_count": len(failed),
            "total_thresholds": len(results),
            "results": [r.to_dict() for r in results],
            "failures": [r.to_dict() for r in failed],
            "benchmark": benchmark_result.to_dict(),
        }

    def run(
        self,
        benchmark_fn: Callable[[], BenchmarkResult],
        *,
        warmup_runs: int = 0,
        runs: int = 1,
    ) -> dict[str, Any]:
        """Execute a benchmark function and check against thresholds.

        Args:
            benchmark_fn: Callable that returns a ``BenchmarkResult``.
            warmup_runs: Number of warmup executions to discard.
            runs: Number of actual benchmark runs.

        Returns:
            Aggregated check results.
        """
        # Warmup
        for _ in range(warmup_runs):
            try:
                benchmark_fn()
            except Exception:
                pass

        # Real runs
        all_results: list[dict[str, Any]] = []
        multi = MultiBenchmark()

        for i in range(runs):
            try:
                result = benchmark_fn()
                multi.add_result(result)
                check = self.check_result(result)
                check["run_number"] = i + 1
                all_results.append(check)
            except Exception as e:
                all_results.append({
                    "run_number": i + 1,
                    "all_passed": False,
                    "error": str(e),
                })

        overall_passed = all(r.get("all_passed", False) for r in all_results)

        return {
            "overall_passed": overall_passed,
            "runs": len(all_results),
            "run_results": all_results,
            "aggregate": multi.report() if multi.results else {},
        }


# ═══════════════════════════════════════════════════════════════════════════
# Throughput Simulator (for testing without real scans)
# ═══════════════════════════════════════════════════════════════════════════

class ThroughputSimulator:
    """Simulate event throughput for benchmarking without real scan infrastructure.

    Generates synthetic events at a target rate to validate the benchmark
    framework itself.

    Usage::

        sim = ThroughputSimulator(target_eps=500, duration_s=5.0)
        result = sim.run()
        print(result.events_per_second)
    """

    def __init__(
        self,
        target_eps: float = 100.0,
        duration_s: float = 1.0,
        *,
        error_rate: float = 0.0,
        event_size_bytes: int = 256,
    ) -> None:
        self.target_eps = target_eps
        self.duration_s = duration_s
        self.error_rate = error_rate
        self.event_size_bytes = event_size_bytes

    def run(self, name: str = "simulation") -> BenchmarkResult:
        """Run the throughput simulation."""
        import random

        bench = ScanBenchmark(name)
        bench.start()

        interval = 1.0 / self.target_eps if self.target_eps > 0 else 0.01
        deadline = time.monotonic() + self.duration_s
        event_count = 0

        while time.monotonic() < deadline:
            t0 = time.monotonic()

            # Simulate event processing
            if random.random() < self.error_rate:
                bench.record_error()
            else:
                # Simulate some work
                _ = "X" * self.event_size_bytes
                latency = time.monotonic() - t0
                bench.record_event(latency)
                event_count += 1

            # Pace to target rate
            elapsed = time.monotonic() - t0
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        bench.record_db_writes(event_count)

        # Record final memory
        try:
            from spiderfoot.ops.memory import CeleryMemoryGuard
            bench.record_memory(CeleryMemoryGuard._get_rss_mb())
        except Exception:
            pass

        return bench.finish()


class DBWriteBenchmark:
    """Benchmark database write throughput.

    Measures the time to insert N events using both single-row and
    bulk insert patterns (using mock or real DB connection).

    Usage::

        db_bench = DBWriteBenchmark(conn)
        result = db_bench.single_insert_benchmark(1000)
        result = db_bench.bulk_insert_benchmark(1000, batch_size=100)
    """

    def __init__(self, conn: Any = None) -> None:
        self.conn = conn

    def single_insert_benchmark(
        self,
        count: int = 1000,
        *,
        insert_fn: Callable[[int], None] | None = None,
    ) -> BenchmarkResult:
        """Benchmark single-row inserts.

        Args:
            count: Number of rows to insert.
            insert_fn: Optional callable that performs a single insert.
                       If None, uses a no-op (framework benchmark only).
        """
        bench = ScanBenchmark("single_insert")
        bench.start()

        for i in range(count):
            t0 = time.monotonic()
            if insert_fn:
                try:
                    insert_fn(i)
                    bench.record_db_writes(1)
                except Exception:
                    bench.record_error()
            else:
                bench.record_db_writes(1)
            bench.record_event(time.monotonic() - t0)

        return bench.finish()

    def bulk_insert_benchmark(
        self,
        count: int = 1000,
        batch_size: int = 100,
        *,
        bulk_fn: Callable[[list[int]], None] | None = None,
    ) -> BenchmarkResult:
        """Benchmark bulk inserts.

        Args:
            count: Total number of rows.
            batch_size: Rows per batch.
            bulk_fn: Optional callable that performs a bulk insert.
        """
        bench = ScanBenchmark("bulk_insert")
        bench.start()

        batch: list[int] = []
        for i in range(count):
            batch.append(i)
            if len(batch) >= batch_size:
                t0 = time.monotonic()
                if bulk_fn:
                    try:
                        bulk_fn(batch)
                        bench.record_db_writes(len(batch))
                    except Exception:
                        bench.record_error()
                else:
                    bench.record_db_writes(len(batch))
                bench.record_event(time.monotonic() - t0)
                batch = []

        # Flush remaining
        if batch:
            t0 = time.monotonic()
            if bulk_fn:
                try:
                    bulk_fn(batch)
                    bench.record_db_writes(len(batch))
                except Exception:
                    bench.record_error()
            else:
                bench.record_db_writes(len(batch))
            bench.record_event(time.monotonic() - t0)

        return bench.finish()


class EventPipelineBenchmark:
    """Benchmark the event processing pipeline.

    Measures throughput of producing events, passing them through
    deduplication, and dispatching to listeners.

    Usage::

        pipeline = EventPipelineBenchmark()
        result = pipeline.run(
            event_count=10000,
            dedup_fn=deduplicator.is_duplicate,
            dispatch_fn=bus.publish,
        )
    """

    def __init__(self) -> None:
        pass

    def run(
        self,
        event_count: int = 1000,
        *,
        dedup_fn: Callable[[str], bool] | None = None,
        dispatch_fn: Callable[[dict], None] | None = None,
        duplicate_rate: float = 0.1,
    ) -> BenchmarkResult:
        """Run the pipeline benchmark.

        Args:
            event_count: Number of events to generate.
            dedup_fn: Deduplication function (returns True if duplicate).
            dispatch_fn: Event dispatch function.
            duplicate_rate: Fraction of events that are duplicates (0.0-1.0).
        """
        import random
        import hashlib

        bench = ScanBenchmark("event_pipeline")
        bench.start()

        seen_hashes: list[str] = []
        dispatched = 0
        deduplicated = 0

        for i in range(event_count):
            t0 = time.monotonic()

            # Generate event with controlled duplicate rate
            if seen_hashes and random.random() < duplicate_rate:
                data = random.choice(seen_hashes)
            else:
                data = hashlib.md5(f"event_{i}_{random.random()}".encode()).hexdigest()
                seen_hashes.append(data)

            # Dedup check
            is_dup = False
            if dedup_fn:
                is_dup = dedup_fn(data)
            if is_dup:
                deduplicated += 1
                continue

            # Dispatch
            if dispatch_fn:
                try:
                    dispatch_fn({"type": "TEST", "data": data})
                except Exception:
                    bench.record_error()
                    continue

            dispatched += 1
            bench.record_event(time.monotonic() - t0)

        bench.record_db_writes(dispatched)
        result = bench.finish()
        result.name = f"event_pipeline (deduped={deduplicated})"
        return result
