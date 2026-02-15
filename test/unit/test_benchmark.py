"""Tests for spiderfoot.benchmark."""
from __future__ import annotations

import unittest

from spiderfoot.benchmark import (
    Benchmark,
    BenchmarkReport,
    BenchmarkResult,
    BenchmarkSuite,
    HashBenchmark,
    SerializationBenchmark,
    ThreadingBenchmark,
    WorkerPoolBenchmark,
    _timed_loop,
)


class TestBenchmarkResult(unittest.TestCase):
    """Tests for BenchmarkResult."""

    def test_ops_per_sec(self):
        r = BenchmarkResult("test", "op", 1000, 1.0)
        self.assertAlmostEqual(r.ops_per_sec, 1000.0)

    def test_ops_per_sec_zero_time(self):
        r = BenchmarkResult("test", "op", 100, 0.0)
        self.assertEqual(r.ops_per_sec, 0.0)

    def test_avg_latency_no_times(self):
        r = BenchmarkResult("test", "op", 100, 1.0)
        self.assertAlmostEqual(r.avg_latency_ms, 10.0)

    def test_avg_latency_with_times(self):
        r = BenchmarkResult("test", "op", 2, 0.002,
                           times=[0.001, 0.001])
        self.assertAlmostEqual(r.avg_latency_ms, 1.0)

    def test_percentiles(self):
        times = [i * 0.001 for i in range(100)]
        r = BenchmarkResult("test", "op", 100, sum(times), times=times)
        self.assertGreater(r.p50_ms, 0)
        self.assertGreater(r.p95_ms, r.p50_ms)
        self.assertGreaterEqual(r.p99_ms, r.p95_ms)

    def test_stdev(self):
        r = BenchmarkResult("test", "op", 3, 0.003,
                           times=[0.001, 0.001, 0.001])
        self.assertEqual(r.stdev_ms, 0.0)

    def test_stdev_single(self):
        r = BenchmarkResult("test", "op", 1, 0.001, times=[0.001])
        self.assertEqual(r.stdev_ms, 0.0)

    def test_to_dict(self):
        r = BenchmarkResult("test", "op", 100, 1.0)
        d = r.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertEqual(d["iterations"], 100)
        self.assertIn("ops_per_sec", d)

    def test_summary_line(self):
        r = BenchmarkResult("test", "op", 100, 1.0, errors=2)
        line = r.summary_line()
        self.assertIn("test/op", line)
        self.assertIn("2 errors", line)


class TestBenchmarkReport(unittest.TestCase):
    """Tests for BenchmarkReport."""

    def test_total_time(self):
        r = BenchmarkReport(started_at=100.0, completed_at=105.0)
        self.assertEqual(r.total_time, 5.0)

    def test_add(self):
        r = BenchmarkReport()
        r.add(BenchmarkResult("a", "op", 10, 0.1))
        self.assertEqual(len(r.results), 1)

    def test_summary(self):
        r = BenchmarkReport(started_at=0, completed_at=1)
        r.system_info = {"python": "3.11", "os": "Linux", "cpus": 4}
        r.add(BenchmarkResult("a", "op", 100, 0.5))
        s = r.summary()
        self.assertIn("SpiderFoot Benchmark Report", s)
        self.assertIn("a/op", s)

    def test_to_dict(self):
        r = BenchmarkReport(started_at=0, completed_at=1)
        r.add(BenchmarkResult("a", "op", 100, 0.5))
        d = r.to_dict()
        self.assertEqual(len(d["results"]), 1)


class TestTimedLoop(unittest.TestCase):
    """Tests for _timed_loop helper."""

    def test_basic(self):
        counter = [0]

        def inc():
            counter[0] += 1

        result = _timed_loop("inc", "test", inc, 100)
        self.assertEqual(counter[0], 100)
        self.assertEqual(result.iterations, 100)
        self.assertGreater(result.total_time, 0)
        self.assertEqual(len(result.times), 100)

    def test_error_counting(self):
        def fail():
            raise ValueError("boom")

        result = _timed_loop("fail", "test", fail, 10)
        self.assertEqual(result.errors, 10)
        self.assertEqual(result.iterations, 10)


class TestBuiltInBenchmarks(unittest.TestCase):
    """Tests that built-in benchmarks run without errors."""

    def test_serialization(self):
        b = SerializationBenchmark()
        results = b.run(100)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.errors == 0 for r in results))

    def test_hash(self):
        b = HashBenchmark()
        results = b.run(100)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.errors == 0 for r in results))

    def test_threading(self):
        b = ThreadingBenchmark()
        results = b.run(50)
        self.assertEqual(len(results), 2)

    def test_worker_pool(self):
        b = WorkerPoolBenchmark()
        results = b.run(50)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].errors, 0)


class TestBenchmarkSuite(unittest.TestCase):
    """Tests for BenchmarkSuite."""

    def test_run_all(self):
        suite = BenchmarkSuite()
        suite.add(SerializationBenchmark())
        suite.add(HashBenchmark())
        report = suite.run_all(100)
        self.assertGreater(len(report.results), 0)
        self.assertGreater(report.total_time, 0)
        self.assertIn("python", report.system_info)

    def test_failed_benchmark(self):
        class BrokenBenchmark(Benchmark):
            name = "Broken"

            def run(self, iterations=100):
                raise RuntimeError("kaboom")

        suite = BenchmarkSuite()
        suite.add(BrokenBenchmark())
        report = suite.run_all(100)
        self.assertEqual(len(report.results), 1)
        self.assertEqual(report.results[0].errors, 1)


if __name__ == "__main__":
    unittest.main()
