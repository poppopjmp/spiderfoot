"""Tests for spiderfoot.module_metrics module."""

import time
import unittest

from spiderfoot.module_metrics import (
    MetricType,
    MetricValue,
    MetricsCollector,
    ModuleMetrics,
)


class TestMetricValue(unittest.TestCase):
    def test_counter(self):
        m = MetricValue(name="events", metric_type=MetricType.COUNTER)
        m.record(1)
        m.record(5)
        self.assertEqual(m.value, 6)
        self.assertEqual(m.count, 2)

    def test_gauge(self):
        m = MetricValue(name="size", metric_type=MetricType.GAUGE)
        m.record(100)
        m.record(50)
        self.assertEqual(m.value, 50)  # Last value

    def test_histogram(self):
        m = MetricValue(name="latency", metric_type=MetricType.HISTOGRAM)
        for v in [10, 20, 30, 40, 50]:
            m.record(v)
        self.assertEqual(m.mean, 30.0)
        self.assertEqual(m.median, 30.0)
        self.assertEqual(m.min_val, 10)
        self.assertEqual(m.max_val, 50)

    def test_p95_p99(self):
        m = MetricValue(name="lat", metric_type=MetricType.HISTOGRAM)
        for v in range(1, 101):
            m.record(v)
        self.assertGreaterEqual(m.p95, 95)
        self.assertGreaterEqual(m.p99, 99)

    def test_reset(self):
        m = MetricValue(name="x", metric_type=MetricType.COUNTER)
        m.record(10)
        m.reset()
        self.assertEqual(m.value, 0)
        self.assertEqual(m.count, 0)

    def test_to_dict_counter(self):
        m = MetricValue(name="x", metric_type=MetricType.COUNTER)
        m.record(5)
        d = m.to_dict()
        self.assertEqual(d["type"], "counter")
        self.assertEqual(d["value"], 5)

    def test_to_dict_histogram(self):
        m = MetricValue(name="x", metric_type=MetricType.HISTOGRAM)
        m.record(10)
        m.record(20)
        d = m.to_dict()
        self.assertIn("mean", d)
        self.assertIn("p95", d)

    def test_empty_histogram_stats(self):
        m = MetricValue(name="x", metric_type=MetricType.HISTOGRAM)
        self.assertEqual(m.mean, 0.0)
        self.assertEqual(m.median, 0.0)
        self.assertEqual(m.p95, 0.0)
        self.assertEqual(m.min_val, 0.0)
        self.assertEqual(m.max_val, 0.0)

    def test_single_value_percentiles(self):
        m = MetricValue(name="x", metric_type=MetricType.HISTOGRAM)
        m.record(42)
        self.assertEqual(m.p95, 42)
        self.assertEqual(m.p99, 42)


class TestModuleMetrics(unittest.TestCase):
    def test_increment(self):
        mm = ModuleMetrics("sfp_dns")
        mm.increment("events_produced")
        mm.increment("events_produced", 5)
        self.assertEqual(mm.get("events_produced").value, 6)

    def test_gauge(self):
        mm = ModuleMetrics("sfp_dns")
        mm.gauge("queue_size", 42)
        self.assertEqual(mm.get("queue_size").value, 42)

    def test_histogram(self):
        mm = ModuleMetrics("sfp_dns")
        mm.histogram("response_size", 1024)
        mm.histogram("response_size", 2048)
        self.assertEqual(mm.get("response_size").mean, 1536.0)

    def test_timer_context(self):
        mm = ModuleMetrics("sfp_dns")
        with mm.timer("query_time"):
            time.sleep(0.01)
        t = mm.get("query_time")
        self.assertGreater(t.value, 0)
        self.assertEqual(t.count, 1)

    def test_record_time(self):
        mm = ModuleMetrics("sfp_dns")
        mm.record_time("fetch_time", 1.5)
        self.assertEqual(mm.get("fetch_time").value, 1.5)

    def test_get_nonexistent(self):
        mm = ModuleMetrics("sfp_dns")
        self.assertIsNone(mm.get("nonexistent"))

    def test_get_all(self):
        mm = ModuleMetrics("sfp_dns")
        mm.increment("a")
        mm.gauge("b", 10)
        self.assertEqual(len(mm.get_all()), 2)

    def test_metric_names(self):
        mm = ModuleMetrics("sfp_dns")
        mm.increment("b")
        mm.increment("a")
        self.assertEqual(mm.metric_names, ["a", "b"])

    def test_reset(self):
        mm = ModuleMetrics("sfp_dns")
        mm.increment("events", 10)
        mm.reset()
        self.assertEqual(mm.get("events").value, 0)

    def test_to_dict(self):
        mm = ModuleMetrics("sfp_dns")
        mm.increment("events")
        d = mm.to_dict()
        self.assertEqual(d["module"], "sfp_dns")
        self.assertIn("events", d["metrics"])


class TestMetricsCollector(unittest.TestCase):
    def setUp(self):
        MetricsCollector.reset_instance()
        self.collector = MetricsCollector()

    def test_get_module(self):
        m = self.collector.get_module("sfp_dns")
        self.assertIsInstance(m, ModuleMetrics)
        # Same instance on second call
        self.assertIs(self.collector.get_module("sfp_dns"), m)

    def test_remove_module(self):
        self.collector.get_module("sfp_dns")
        self.assertTrue(self.collector.remove_module("sfp_dns"))
        self.assertFalse(self.collector.remove_module("nonexistent"))

    def test_module_names(self):
        self.collector.get_module("sfp_b")
        self.collector.get_module("sfp_a")
        self.assertEqual(self.collector.module_names, ["sfp_a", "sfp_b"])

    def test_module_count(self):
        self.collector.get_module("sfp_a")
        self.collector.get_module("sfp_b")
        self.assertEqual(self.collector.module_count, 2)

    def test_global_metrics(self):
        self.collector.global_metrics.increment("total_events")
        self.assertEqual(self.collector.global_metrics.get("total_events").value, 1)

    def test_snapshot(self):
        self.collector.get_module("sfp_dns").increment("events")
        snap = self.collector.snapshot()
        self.assertIn("timestamp", snap)
        self.assertIn("modules", snap)
        self.assertIn("sfp_dns", snap["modules"])

    def test_snapshot_history(self):
        self.collector.snapshot()
        self.collector.snapshot()
        self.assertEqual(len(self.collector.get_snapshots()), 2)

    def test_summary(self):
        self.collector.get_module("sfp_dns").increment("events_produced", 10)
        self.collector.get_module("sfp_dns").increment("errors", 2)
        s = self.collector.summary()
        self.assertEqual(s["total_events"], 10)
        self.assertEqual(s["total_errors"], 2)
        self.assertIn("sfp_dns", s["modules_with_errors"])

    def test_reset_all(self):
        self.collector.get_module("sfp_dns").increment("events", 100)
        self.collector.snapshot()
        self.collector.reset_all()
        self.assertEqual(self.collector.get_module("sfp_dns").get("events").value, 0)
        self.assertEqual(len(self.collector.get_snapshots()), 0)

    def test_singleton(self):
        a = MetricsCollector.get_instance()
        b = MetricsCollector.get_instance()
        self.assertIs(a, b)
        MetricsCollector.reset_instance()
        c = MetricsCollector.get_instance()
        self.assertIsNot(a, c)

    def test_to_dict(self):
        self.collector.get_module("sfp_dns")
        d = self.collector.to_dict()
        self.assertIn("modules", d)


if __name__ == "__main__":
    unittest.main()
