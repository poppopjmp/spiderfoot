# -*- coding: utf-8 -*-
"""Tests for spiderfoot.ops.benchmarks — Cycles 131-150 throughput benchmarking.

Covers:
    - BenchmarkResult / ScanBenchmark / MultiBenchmark  (Cycle 131)
    - PostgresTuningAdvisor / PgTuningRecommendation  (Cycles 132-140)
    - PerformanceRegressionRunner / Thresholds  (Cycles 141-150)
    - ThroughputSimulator / DBWriteBenchmark / EventPipelineBenchmark
"""

import time
from unittest.mock import patch

import pytest

from spiderfoot.ops.benchmarks import (
    BenchmarkResult,
    ScanBenchmark,
    MultiBenchmark,
    PgTuningRecommendation,
    PostgresTuningAdvisor,
    PerformanceThreshold,
    ThresholdResult,
    PerformanceRegressionRunner,
    ThroughputSimulator,
    DBWriteBenchmark,
    EventPipelineBenchmark,
    _percentile,
)


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 131 — BenchmarkResult / ScanBenchmark / MultiBenchmark
# ═══════════════════════════════════════════════════════════════════════════

class TestPercentile:
    """Tests for _percentile utility."""

    def test_empty_data(self):
        assert _percentile([], 50) == 0.0

    def test_single_value(self):
        assert _percentile([5.0], 50) == 5.0

    def test_p50_odd(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _percentile(data, 50) == 3.0

    def test_p95(self):
        data = list(range(1, 101))
        p95 = _percentile([float(x) for x in data], 95)
        assert 94 < p95 < 96

    def test_p99(self):
        data = [float(i) for i in range(100)]
        p99 = _percentile(data, 99)
        assert p99 > 90


class TestBenchmarkResult:
    """Tests for benchmark result dataclass."""

    def test_duration(self):
        r = BenchmarkResult(started_at=10.0, finished_at=15.0)
        assert r.duration_s == 5.0

    def test_events_per_second(self):
        r = BenchmarkResult(started_at=0.0, finished_at=2.0, events_produced=100)
        assert r.events_per_second == 50.0

    def test_events_per_second_zero_duration(self):
        r = BenchmarkResult(started_at=0.0, finished_at=0.0, events_produced=100)
        assert r.events_per_second == 0.0

    def test_db_writes_per_second(self):
        r = BenchmarkResult(started_at=0.0, finished_at=4.0, db_writes=200)
        assert r.db_writes_per_second == 50.0

    def test_latency_percentiles(self):
        samples = [0.01 * i for i in range(1, 101)]
        r = BenchmarkResult(samples=samples)
        assert r.p50_latency_ms > 0
        assert r.p95_latency_ms > r.p50_latency_ms
        assert r.p99_latency_ms > r.p95_latency_ms

    def test_latency_no_samples(self):
        r = BenchmarkResult()
        assert r.p50_latency_ms == 0.0
        assert r.p95_latency_ms == 0.0

    def test_to_dict(self):
        r = BenchmarkResult(
            name="test",
            started_at=0.0,
            finished_at=1.0,
            events_produced=50,
            db_writes=25,
        )
        d = r.to_dict()
        assert d["name"] == "test"
        assert d["events_per_second"] == 50.0
        assert d["db_writes_per_second"] == 25.0


class TestScanBenchmark:
    """Tests for scan benchmark runner."""

    def test_basic_flow(self):
        bench = ScanBenchmark("test")
        bench.start()
        assert bench.is_running

        for _ in range(10):
            bench.record_event(0.001)
        bench.record_db_writes(10)

        result = bench.finish()
        assert not bench.is_running
        assert result.events_produced == 10
        assert result.db_writes == 10
        assert result.duration_s > 0

    def test_record_error(self):
        bench = ScanBenchmark()
        bench.start()
        bench.record_error()
        bench.record_error()
        result = bench.finish()
        assert result.errors == 2

    def test_record_memory(self):
        bench = ScanBenchmark()
        bench.start()
        bench.record_memory(500.0)
        bench.record_memory(800.0)
        bench.record_memory(600.0)
        result = bench.finish()
        assert result.peak_memory_mb == 800.0


class TestMultiBenchmark:
    """Tests for multi-run benchmark aggregation."""

    def test_empty(self):
        multi = MultiBenchmark()
        report = multi.report()
        assert "error" in report

    def test_single_result(self):
        multi = MultiBenchmark()
        r = BenchmarkResult(
            name="r1",
            started_at=0.0,
            finished_at=1.0,
            events_produced=100,
            db_writes=50,
        )
        multi.add_result(r)
        report = multi.report()
        assert report["runs"] == 1
        assert report["total_events"] == 100

    def test_multiple_results(self):
        multi = MultiBenchmark()
        for i in range(3):
            r = BenchmarkResult(
                name=f"r{i}",
                started_at=0.0,
                finished_at=1.0,
                events_produced=100,
                db_writes=50,
            )
            multi.add_result(r)

        report = multi.report()
        assert report["runs"] == 3
        assert report["total_events"] == 300
        assert report["avg_events_per_second"] == 100.0


# ═══════════════════════════════════════════════════════════════════════════
# Cycles 132-140 — PostgresTuningAdvisor
# ═══════════════════════════════════════════════════════════════════════════

class TestPgTuningRecommendation:
    """Tests for tuning recommendation dataclass."""

    def test_to_dict(self):
        rec = PgTuningRecommendation(
            parameter="shared_buffers",
            recommended_value="4096MB",
            reason="25% of 16GB RAM",
            impact="high",
        )
        d = rec.to_dict()
        assert d["parameter"] == "shared_buffers"
        assert d["recommended_value"] == "4096MB"
        assert d["impact"] == "high"


class TestPostgresTuningAdvisor:
    """Tests for PostgreSQL tuning advisor."""

    def test_recommend_16gb(self):
        advisor = PostgresTuningAdvisor(total_ram_gb=16.0, max_connections=100, cpu_cores=8)
        recs = advisor.recommend()
        assert len(recs) >= 8
        params = {r.parameter for r in recs}
        assert "shared_buffers" in params
        assert "work_mem" in params
        assert "max_parallel_workers" in params

    def test_shared_buffers_calculation(self):
        advisor = PostgresTuningAdvisor(total_ram_gb=16.0, cpu_cores=4)
        recs = {r.parameter: r for r in advisor.recommend()}
        # 25% of 16GB = 4GB = 4096MB
        assert recs["shared_buffers"].recommended_value == "4096MB"

    def test_shared_buffers_capped_at_8gb(self):
        advisor = PostgresTuningAdvisor(total_ram_gb=64.0, cpu_cores=4)
        recs = {r.parameter: r for r in advisor.recommend()}
        # 25% of 64GB = 16GB, but capped at 8GB
        assert recs["shared_buffers"].recommended_value == "8192MB"

    def test_work_mem_calculation(self):
        advisor = PostgresTuningAdvisor(total_ram_gb=16.0, max_connections=100, cpu_cores=4)
        recs = {r.parameter: r for r in advisor.recommend()}
        # (16*1024*0.25)/100 = 40MB
        assert recs["work_mem"].recommended_value == "40MB"

    def test_parallel_workers(self):
        advisor = PostgresTuningAdvisor(total_ram_gb=16.0, cpu_cores=8)
        recs = {r.parameter: r for r in advisor.recommend()}
        assert recs["max_parallel_workers_per_gather"].recommended_value == "4"

    def test_ssd_random_page_cost(self):
        advisor = PostgresTuningAdvisor(total_ram_gb=8.0, ssd_storage=True, cpu_cores=4)
        recs = {r.parameter: r for r in advisor.recommend()}
        assert recs["random_page_cost"].recommended_value == "1.1"

    def test_no_ssd_no_random_page_cost(self):
        advisor = PostgresTuningAdvisor(total_ram_gb=8.0, ssd_storage=False, cpu_cores=4)
        recs = {r.parameter: r for r in advisor.recommend()}
        assert "random_page_cost" not in recs

    def test_summary(self):
        advisor = PostgresTuningAdvisor(total_ram_gb=16.0, cpu_cores=8)
        summary = advisor.summary()
        assert "system" in summary
        assert "recommendations" in summary
        assert summary["system"]["total_ram_gb"] == 16.0

    def test_generate_config(self):
        advisor = PostgresTuningAdvisor(total_ram_gb=8.0, cpu_cores=4)
        config = advisor.generate_config()
        assert "shared_buffers" in config
        assert "work_mem" in config
        assert "SpiderFoot" in config

    def test_small_ram(self):
        advisor = PostgresTuningAdvisor(total_ram_gb=2.0, max_connections=20, cpu_cores=2)
        recs = {r.parameter: r for r in advisor.recommend()}
        # Should still produce valid recommendations
        shared_mb = int(recs["shared_buffers"].recommended_value.rstrip("MB"))
        assert shared_mb >= 256  # Minimum

    def test_detect_cores(self):
        cores = PostgresTuningAdvisor._detect_cores()
        assert cores >= 1

    def test_detect_ram(self):
        ram = PostgresTuningAdvisor._detect_ram_gb()
        assert ram > 0


# ═══════════════════════════════════════════════════════════════════════════
# Cycles 141-150 — PerformanceRegressionRunner
# ═══════════════════════════════════════════════════════════════════════════

class TestPerformanceThreshold:
    """Tests for threshold definitions."""

    def test_gte_pass(self):
        t = PerformanceThreshold(metric="eps", operator=">=", value=100.0)
        assert t.check(150.0) is True

    def test_gte_fail(self):
        t = PerformanceThreshold(metric="eps", operator=">=", value=100.0)
        assert t.check(50.0) is False

    def test_lte_pass(self):
        t = PerformanceThreshold(metric="latency", operator="<=", value=50.0)
        assert t.check(30.0) is True

    def test_lte_fail(self):
        t = PerformanceThreshold(metric="latency", operator="<=", value=50.0)
        assert t.check(80.0) is False

    def test_gt(self):
        t = PerformanceThreshold(metric="x", operator=">", value=10.0)
        assert t.check(11.0) is True
        assert t.check(10.0) is False

    def test_lt(self):
        t = PerformanceThreshold(metric="x", operator="<", value=10.0)
        assert t.check(9.0) is True
        assert t.check(10.0) is False

    def test_invalid_operator(self):
        t = PerformanceThreshold(metric="x", operator="==", value=1.0)
        with pytest.raises(ValueError, match="Unknown operator"):
            t.check(1.0)

    def test_to_dict(self):
        t = PerformanceThreshold(metric="eps", operator=">=", value=100.0, description="test")
        d = t.to_dict()
        assert d["metric"] == "eps"
        assert d["value"] == 100.0


class TestPerformanceRegressionRunner:
    """Tests for CI-compatible performance regression runner."""

    def _make_passing_result(self) -> BenchmarkResult:
        return BenchmarkResult(
            name="test",
            started_at=0.0,
            finished_at=1.0,
            events_produced=200,  # 200 eps
            db_writes=100,
            errors=0,
            peak_memory_mb=500.0,
            samples=[0.001] * 200,  # 1ms latency
        )

    def _make_failing_result(self) -> BenchmarkResult:
        return BenchmarkResult(
            name="test",
            started_at=0.0,
            finished_at=1.0,
            events_produced=10,  # 10 eps — below 50 threshold
            db_writes=5,
            errors=5,  # above 0 threshold
            peak_memory_mb=3000.0,  # above 2048 threshold
            samples=[0.5] * 10,  # 500ms latency — above 100ms threshold
        )

    def test_check_passing(self):
        runner = PerformanceRegressionRunner()
        result = runner.check_result(self._make_passing_result())
        assert result["all_passed"] is True
        assert result["failed_count"] == 0

    def test_check_failing(self):
        runner = PerformanceRegressionRunner()
        result = runner.check_result(self._make_failing_result())
        assert result["all_passed"] is False
        assert result["failed_count"] > 0

    def test_custom_thresholds(self):
        runner = PerformanceRegressionRunner(use_defaults=False)
        runner.add_threshold(PerformanceThreshold(
            metric="events_per_second",
            operator=">=",
            value=500.0,
        ))
        result = runner.check_result(self._make_passing_result())
        assert result["all_passed"] is False  # 200 < 500

    def test_clear_thresholds(self):
        runner = PerformanceRegressionRunner()
        runner.clear_thresholds()
        assert len(runner.thresholds) == 0

    def test_run_single(self):
        runner = PerformanceRegressionRunner(use_defaults=False)
        runner.add_threshold(PerformanceThreshold(
            metric="events_produced",
            operator=">=",
            value=5.0,
        ))

        def bench_fn() -> BenchmarkResult:
            b = ScanBenchmark("test")
            b.start()
            for _ in range(10):
                b.record_event(0.001)
            return b.finish()

        result = runner.run(bench_fn)
        assert result["overall_passed"] is True
        assert result["runs"] == 1

    def test_run_multiple(self):
        runner = PerformanceRegressionRunner(use_defaults=False)
        runner.add_threshold(PerformanceThreshold(
            metric="events_produced",
            operator=">=",
            value=1.0,
        ))

        counter = {"n": 0}

        def bench_fn() -> BenchmarkResult:
            counter["n"] += 1
            b = ScanBenchmark(f"run-{counter['n']}")
            b.start()
            b.record_event(0.001)
            return b.finish()

        result = runner.run(bench_fn, runs=3)
        assert result["runs"] == 3

    def test_run_with_warmup(self):
        calls = {"total": 0}

        def bench_fn() -> BenchmarkResult:
            calls["total"] += 1
            b = ScanBenchmark()
            b.start()
            b.record_event(0.001)
            return b.finish()

        runner = PerformanceRegressionRunner(use_defaults=False)
        runner.run(bench_fn, warmup_runs=2, runs=1)
        assert calls["total"] == 3  # 2 warmup + 1 real

    def test_run_with_error(self):
        def failing_fn() -> BenchmarkResult:
            raise RuntimeError("boom")

        runner = PerformanceRegressionRunner(use_defaults=False)
        result = runner.run(failing_fn, runs=1)
        assert result["overall_passed"] is False

    def test_default_thresholds(self):
        runner = PerformanceRegressionRunner()
        defaults = runner.thresholds
        assert len(defaults) == 4
        metrics = {t.metric for t in defaults}
        assert "events_per_second" in metrics
        assert "errors" in metrics


# ═══════════════════════════════════════════════════════════════════════════
# ThroughputSimulator / DBWriteBenchmark / EventPipelineBenchmark
# ═══════════════════════════════════════════════════════════════════════════

class TestThroughputSimulator:
    """Tests for synthetic event throughput simulation."""

    def test_basic_simulation(self):
        sim = ThroughputSimulator(target_eps=100, duration_s=0.2)
        result = sim.run()
        assert result.events_produced > 0
        assert result.duration_s > 0
        assert result.db_writes > 0

    def test_error_rate(self):
        sim = ThroughputSimulator(target_eps=50, duration_s=0.2, error_rate=0.5)
        result = sim.run()
        assert result.errors > 0

    def test_custom_name(self):
        sim = ThroughputSimulator(target_eps=50, duration_s=0.1)
        result = sim.run(name="custom-test")
        assert result.name == "custom-test"

    def test_large_event_size(self):
        sim = ThroughputSimulator(target_eps=50, duration_s=0.1, event_size_bytes=4096)
        result = sim.run()
        assert result.events_produced > 0


class TestDBWriteBenchmark:
    """Tests for DB write throughput benchmarking."""

    def test_single_insert_no_fn(self):
        db_bench = DBWriteBenchmark()
        result = db_bench.single_insert_benchmark(100)
        assert result.db_writes == 100
        assert result.events_produced == 100
        assert result.errors == 0

    def test_single_insert_with_fn(self):
        calls = []

        def insert_fn(i: int) -> None:
            calls.append(i)

        db_bench = DBWriteBenchmark()
        result = db_bench.single_insert_benchmark(10, insert_fn=insert_fn)
        assert len(calls) == 10
        assert result.db_writes == 10

    def test_single_insert_with_errors(self):
        def failing_fn(i: int) -> None:
            if i % 3 == 0:
                raise ValueError("fail")

        db_bench = DBWriteBenchmark()
        result = db_bench.single_insert_benchmark(10, insert_fn=failing_fn)
        assert result.errors > 0

    def test_bulk_insert_no_fn(self):
        db_bench = DBWriteBenchmark()
        result = db_bench.bulk_insert_benchmark(100, batch_size=25)
        assert result.db_writes == 100
        assert result.events_produced == 4  # 4 batches

    def test_bulk_insert_with_fn(self):
        batches = []

        def bulk_fn(batch: list[int]) -> None:
            batches.append(list(batch))

        db_bench = DBWriteBenchmark()
        result = db_bench.bulk_insert_benchmark(10, batch_size=3, bulk_fn=bulk_fn)
        assert len(batches) == 4  # 3+3+3+1
        assert result.db_writes == 10

    def test_bulk_insert_remainder(self):
        db_bench = DBWriteBenchmark()
        result = db_bench.bulk_insert_benchmark(7, batch_size=5)
        assert result.db_writes == 7
        assert result.events_produced == 2  # 5 + 2


class TestEventPipelineBenchmark:
    """Tests for event processing pipeline benchmarking."""

    def test_basic_pipeline(self):
        pipeline = EventPipelineBenchmark()
        result = pipeline.run(event_count=100)
        assert result.events_produced > 0

    def test_pipeline_with_dedup(self):
        seen = set()

        def dedup_fn(data: str) -> bool:
            if data in seen:
                return True
            seen.add(data)
            return False

        pipeline = EventPipelineBenchmark()
        result = pipeline.run(
            event_count=100,
            dedup_fn=dedup_fn,
            duplicate_rate=0.3,
        )
        # Some events should be deduplicated
        assert result.events_produced <= 100

    def test_pipeline_with_dispatch(self):
        dispatched = []

        def dispatch_fn(event: dict) -> None:
            dispatched.append(event)

        pipeline = EventPipelineBenchmark()
        result = pipeline.run(
            event_count=50,
            dispatch_fn=dispatch_fn,
            duplicate_rate=0.0,
        )
        assert len(dispatched) == result.events_produced

    def test_pipeline_dispatch_error(self):
        def bad_dispatch(event: dict) -> None:
            raise RuntimeError("dispatch error")

        pipeline = EventPipelineBenchmark()
        result = pipeline.run(
            event_count=20,
            dispatch_fn=bad_dispatch,
            duplicate_rate=0.0,
        )
        assert result.errors > 0
