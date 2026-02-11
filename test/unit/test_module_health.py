"""Tests for module health monitoring."""
from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock

from spiderfoot.plugins.module_health import (
    HealthStatus,
    ModuleHealth,
    ModuleHealthMonitor,
    get_health_monitor,
)


class TestModuleHealth(unittest.TestCase):
    """Test ModuleHealth data class."""

    def test_initial_state(self):
        h = ModuleHealth(module_name="sfp_test")
        self.assertEqual(h.events_processed, 0)
        self.assertEqual(h.error_count, 0)
        self.assertEqual(h.avg_duration, 0.0)
        self.assertEqual(h.error_rate, 0.0)

    def test_avg_duration(self):
        h = ModuleHealth(module_name="sfp_test")
        h.events_processed = 10
        h.total_duration = 5.0
        self.assertAlmostEqual(h.avg_duration, 0.5)

    def test_error_rate(self):
        h = ModuleHealth(module_name="sfp_test")
        h.events_processed = 8
        h.error_count = 2
        self.assertAlmostEqual(h.error_rate, 0.2)

    def test_health_score_healthy(self):
        h = ModuleHealth(module_name="sfp_test")
        h.events_processed = 100
        h.total_duration = 10.0  # 0.1s avg
        h.error_count = 1
        h.last_event_time = time.monotonic()
        self.assertGreaterEqual(h.health_score, 80)
        self.assertEqual(h.status, HealthStatus.HEALTHY)

    def test_health_score_high_errors(self):
        h = ModuleHealth(module_name="sfp_bad")
        h.events_processed = 5
        h.error_count = 10
        h.last_event_time = time.monotonic()
        self.assertLessEqual(h.health_score, 50)
        self.assertIn(h.status, (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED))

    def test_health_score_slow(self):
        h = ModuleHealth(module_name="sfp_slow")
        h.events_processed = 10
        h.total_duration = 350.0  # 35s avg
        h.last_event_time = time.monotonic()
        self.assertLess(h.health_score, 80)

    def test_stalled_detection(self):
        h = ModuleHealth(module_name="sfp_stalled")
        h.events_processed = 5
        h.start_time = time.monotonic() - 400
        h.last_event_time = time.monotonic() - 400
        self.assertEqual(h.status, HealthStatus.STALLED)

    def test_to_dict(self):
        h = ModuleHealth(module_name="sfp_test")
        h.events_processed = 10
        h.error_count = 1
        h.last_event_time = time.monotonic()
        d = h.to_dict()
        self.assertEqual(d["module_name"], "sfp_test")
        self.assertIn("status", d)
        self.assertIn("health_score", d)
        self.assertIn("events_per_second", d)
        self.assertIn("top_errors", d)

    def test_events_per_second(self):
        h = ModuleHealth(module_name="sfp_test")
        h.events_processed = 100
        h.start_time = time.monotonic() - 10  # 10 seconds ago
        eps = h.events_per_second
        self.assertGreater(eps, 5)  # roughly 10 eps


class TestModuleHealthMonitor(unittest.TestCase):
    """Test the monitor orchestrator."""

    def setUp(self):
        self.monitor = ModuleHealthMonitor()

    def test_register_module(self):
        self.monitor.register_module("sfp_test")
        h = self.monitor.get_health("sfp_test")
        self.assertIsNotNone(h)
        self.assertEqual(h.module_name, "sfp_test")

    def test_record_event_processed(self):
        self.monitor.record_event_processed("sfp_test", duration=0.5)
        h = self.monitor.get_health("sfp_test")
        self.assertEqual(h.events_processed, 1)
        self.assertAlmostEqual(h.total_duration, 0.5)

    def test_record_multiple_events(self):
        for i in range(10):
            self.monitor.record_event_processed("sfp_test", duration=0.1)
        h = self.monitor.get_health("sfp_test")
        self.assertEqual(h.events_processed, 10)

    def test_record_error(self):
        self.monitor.record_error("sfp_test", "TimeoutError")
        h = self.monitor.get_health("sfp_test")
        self.assertEqual(h.error_count, 1)
        self.assertEqual(h.last_error_type, "TimeoutError")
        self.assertEqual(h.error_types["TimeoutError"], 1)

    def test_record_event_produced(self):
        self.monitor.record_event_produced("sfp_test")
        h = self.monitor.get_health("sfp_test")
        self.assertEqual(h.events_produced, 1)

    def test_get_report(self):
        self.monitor.record_event_processed("sfp_a", duration=0.1)
        self.monitor.record_event_processed("sfp_b", duration=0.2)
        self.monitor.record_error("sfp_b", "Error")

        report = self.monitor.get_report()
        self.assertIn("summary", report)
        self.assertIn("modules", report)
        self.assertEqual(report["summary"]["total"], 2)
        self.assertIn("sfp_a", report["modules"])
        self.assertIn("sfp_b", report["modules"])

    def test_get_stalled_modules(self):
        self.monitor.register_module("sfp_stalled")
        h = self.monitor.get_health("sfp_stalled")
        h.events_processed = 5
        h.start_time = time.monotonic() - 400
        h.last_event_time = time.monotonic() - 400

        stalled = self.monitor.get_stalled_modules()
        self.assertIn("sfp_stalled", stalled)

    def test_get_unhealthy_modules(self):
        self.monitor.register_module("sfp_bad")
        h = self.monitor.get_health("sfp_bad")
        h.events_processed = 1
        h.error_count = 50
        h.total_duration = 500.0  # avg_duration = 500 -> -25 penalty
        h.last_event_time = time.monotonic()

        unhealthy = self.monitor.get_unhealthy_modules()
        self.assertIn("sfp_bad", unhealthy)

    def test_alert_callback(self):
        alerts = []
        self.monitor.on_alert(lambda name, data: alerts.append(name))

        # Make module unhealthy: high error rate + slow processing
        # to push score below 50
        self.monitor.record_event_processed("sfp_bad", 35.0)  # slow -> -25
        for _ in range(50):
            self.monitor.record_error("sfp_bad", "Error")  # error_rate >0.5 -> -50

        self.assertIn("sfp_bad", alerts)

    def test_reset(self):
        self.monitor.record_event_processed("sfp_test")
        self.monitor.reset()
        self.assertIsNone(self.monitor.get_health("sfp_test"))

    def test_auto_create_on_record(self):
        """Module should be auto-created when recording without register."""
        self.monitor.record_event_processed("sfp_auto")
        h = self.monitor.get_health("sfp_auto")
        self.assertIsNotNone(h)

    def test_thread_safety(self):
        """Test concurrent access."""
        import threading
        errors = []

        def worker(name):
            try:
                for _ in range(100):
                    self.monitor.record_event_processed(name, 0.01)
                    self.monitor.record_event_produced(name)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(f"sfp_{i}",))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        report = self.monitor.get_report()
        self.assertEqual(report["summary"]["total"], 10)


class TestSingleton(unittest.TestCase):
    def test_get_health_monitor(self):
        m = get_health_monitor()
        self.assertIsNotNone(m)
        self.assertIsInstance(m, ModuleHealthMonitor)
