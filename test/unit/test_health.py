"""Unit tests for spiderfoot.health."""
from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock

from spiderfoot.observability.health import (
    ComponentHealth,
    HealthAggregator,
    HealthStatus,
)


class TestHealthStatus(unittest.TestCase):
    def test_values(self):
        self.assertEqual(HealthStatus.UP.value, "up")
        self.assertEqual(HealthStatus.DOWN.value, "down")
        self.assertEqual(HealthStatus.DEGRADED.value, "degraded")
        self.assertEqual(HealthStatus.UNKNOWN.value, "unknown")


class TestComponentHealth(unittest.TestCase):
    def test_to_dict(self):
        ch = ComponentHealth("db", HealthStatus.UP, latency_ms=1.5)
        d = ch.to_dict()
        self.assertEqual(d["status"], "up")
        self.assertEqual(d["latency_ms"], 1.5)
        self.assertNotIn("message", d)

    def test_to_dict_with_message(self):
        ch = ComponentHealth("db", HealthStatus.DOWN,
                             message="connection refused")
        d = ch.to_dict()
        self.assertEqual(d["message"], "connection refused")

    def test_to_dict_with_details(self):
        ch = ComponentHealth("db", HealthStatus.UP,
                             details={"version": "15.0"})
        d = ch.to_dict()
        self.assertEqual(d["details"]["version"], "15.0")


class TestHealthAggregator(unittest.TestCase):

    def setUp(self):
        HealthAggregator.reset()
        self.health = HealthAggregator.get_instance()

    def tearDown(self):
        HealthAggregator.reset()

    def test_singleton(self):
        h1 = HealthAggregator.get_instance()
        h2 = HealthAggregator.get_instance()
        self.assertIs(h1, h2)

    def test_liveness(self):
        result = self.health.liveness()
        self.assertEqual(result["status"], "up")
        self.assertIn("uptime_seconds", result)

    def test_startup_not_ready(self):
        result = self.health.startup()
        self.assertEqual(result["status"], "down")
        self.assertFalse(result["startup_complete"])

    def test_startup_ready(self):
        self.health.mark_ready()
        result = self.health.startup()
        self.assertEqual(result["status"], "up")
        self.assertTrue(result["startup_complete"])

    def test_register_simple_check(self):
        self.health.register("test", lambda: HealthStatus.UP)
        result = self.health.check_all()
        self.assertEqual(result["status"], "up")
        self.assertIn("test", result["components"])
        self.assertEqual(result["components"]["test"]["status"], "up")

    def test_check_all_with_down_component(self):
        self.health.register("good", lambda: HealthStatus.UP)
        self.health.register("bad", lambda: HealthStatus.DOWN)
        result = self.health.check_all()
        self.assertEqual(result["status"], "down")

    def test_check_all_with_degraded_component(self):
        self.health.register("ok", lambda: HealthStatus.UP)
        self.health.register("slow", lambda: HealthStatus.DEGRADED)
        result = self.health.check_all()
        self.assertEqual(result["status"], "degraded")

    def test_check_with_exception(self):
        def failing_check():
            raise RuntimeError("connection refused")

        self.health.register("broken", failing_check)
        result = self.health.check_all()
        self.assertEqual(result["status"], "down")
        self.assertIn("connection refused",
                       result["components"]["broken"]["message"])

    def test_register_detailed_check(self):
        def detailed():
            return ComponentHealth("db", HealthStatus.UP,
                                   details={"connections": 5})

        self.health.register_detailed("db", detailed)
        result = self.health.check_all()
        self.assertEqual(result["components"]["db"]["status"], "up")

    def test_unregister(self):
        self.health.register("temp", lambda: HealthStatus.UP)
        self.health.unregister("temp")
        result = self.health.check_all()
        self.assertNotIn("temp", result["components"])

    def test_check_component(self):
        self.health.register("comp1", lambda: HealthStatus.UP)
        result = self.health.check_component("comp1")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "up")

    def test_check_component_not_found(self):
        result = self.health.check_component("nonexistent")
        self.assertIsNone(result)

    def test_check_component_with_error(self):
        self.health.register("err", lambda: (_ for _ in ()).throw(
            RuntimeError("fail")))
        result = self.health.check_component("err")
        self.assertEqual(result["status"], "down")

    def test_readiness_delegates_to_check_all(self):
        self.health.register("svc", lambda: HealthStatus.UP)
        result = self.health.readiness()
        self.assertEqual(result["status"], "up")
        self.assertIn("svc", result["components"])

    def test_latency_measured(self):
        def slow_check():
            time.sleep(0.01)
            return HealthStatus.UP

        self.health.register("slow", slow_check)
        result = self.health.check_all()
        self.assertGreater(
            result["components"]["slow"]["latency_ms"], 0)

    def test_empty_check_all(self):
        result = self.health.check_all()
        self.assertEqual(result["status"], "up")
        self.assertEqual(result["components"], {})


if __name__ == "__main__":
    unittest.main()
