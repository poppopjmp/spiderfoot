"""
Tests for the Prometheus-compatible metrics module.
"""

import time
import unittest

from spiderfoot.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    get_registry,
    SCANS_TOTAL,
    ACTIVE_SCANS,
    SCAN_DURATION,
)


class TestCounter(unittest.TestCase):
    """Test Counter metric."""

    def test_inc_default(self):
        c = Counter("test_counter_1", "a test counter")
        c.inc()
        c.inc()
        self.assertIn("test_counter_1 2.0", c.expose())

    def test_labels(self):
        c = Counter("test_counter_2", "labeled", label_names=["status"])
        c.labels(status="ok").inc()
        c.labels(status="ok").inc()
        c.labels(status="error").inc()
        text = c.expose()
        self.assertIn('status="ok"', text)
        self.assertIn('status="error"', text)
        self.assertIn("2.0", text)

    def test_expose_format(self):
        c = Counter("test_counter_3", "help text")
        text = c.expose()
        self.assertIn("# HELP test_counter_3 help text", text)
        self.assertIn("# TYPE test_counter_3 counter", text)


class TestGauge(unittest.TestCase):
    """Test Gauge metric."""

    def test_set(self):
        g = Gauge("test_gauge_1", "a gauge")
        g.set(42.0)
        self.assertIn("42.0", g.expose())

    def test_inc_dec(self):
        g = Gauge("test_gauge_2", "")
        g.inc()
        g.inc()
        g.dec()
        self.assertIn("1.0", g.expose())

    def test_labeled_gauge(self):
        g = Gauge("test_gauge_3", "", label_names=["zone"])
        g.labels(zone="us").set(10)
        g.labels(zone="eu").set(20)
        text = g.expose()
        self.assertIn('zone="us"', text)
        self.assertIn('zone="eu"', text)


class TestHistogram(unittest.TestCase):
    """Test Histogram metric."""

    def test_observe(self):
        h = Histogram("test_hist_1", "a histogram", buckets=[1, 5, 10])
        h.observe(0.5)
        h.observe(3.0)
        h.observe(7.0)
        text = h.expose()
        self.assertIn("test_hist_1_count 3", text)
        self.assertIn("test_hist_1_sum", text)
        self.assertIn('le="1"', text)
        self.assertIn('le="5"', text)
        self.assertIn('le="10"', text)

    def test_timer(self):
        h = Histogram("test_hist_2", "", buckets=[0.01, 0.1, 1.0])
        with h.time():
            time.sleep(0.02)
        self.assertEqual(h._count, 1)
        self.assertGreater(h._sum, 0.01)


class TestMetricsRegistry(unittest.TestCase):
    """Test MetricsRegistry."""

    def test_register_and_expose(self):
        reg = MetricsRegistry()
        c = Counter("reg_test_1", "counter")
        g = Gauge("reg_test_2", "gauge")
        reg.register(c)
        reg.register(g)
        c.inc(5)
        g.set(99)
        text = reg.expose()
        self.assertIn("reg_test_1 5.0", text)
        self.assertIn("reg_test_2 99.0", text)

    def test_unregister(self):
        reg = MetricsRegistry()
        c = Counter("reg_test_3", "")
        reg.register(c)
        reg.unregister("reg_test_3")
        self.assertNotIn("reg_test_3", reg.expose())

    def test_clear(self):
        reg = MetricsRegistry()
        reg.register(Counter("reg_test_4", ""))
        reg.clear()
        self.assertEqual(reg.expose().strip(), "")


class TestGlobalRegistry(unittest.TestCase):
    """Test pre-defined global metrics."""

    def test_global_registry_has_sf_metrics(self):
        text = get_registry().expose()
        self.assertIn("sf_scans_total", text)
        self.assertIn("sf_active_scans", text)
        self.assertIn("sf_events_produced_total", text)
        self.assertIn("sf_http_requests_total", text)
        self.assertIn("sf_dns_queries_total", text)
        self.assertIn("sf_worker_pool_size", text)
        self.assertIn("sf_eventbus_published_total", text)

    def test_scans_total_labels(self):
        SCANS_TOTAL.labels(status="test_completed").inc()
        text = SCANS_TOTAL.expose()
        self.assertIn('status="test_completed"', text)


if __name__ == "__main__":
    unittest.main()
