"""Unit tests for spiderfoot.correlation_service."""
from __future__ import annotations

import os
import queue
import time
import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.services.correlation_service import (
    CorrelationResult,
    CorrelationService,
    CorrelationServiceConfig,
    CorrelationTrigger,
    get_correlation_service,
)


class TestCorrelationServiceConfig(unittest.TestCase):
    """Tests for CorrelationServiceConfig."""

    def test_defaults(self):
        cfg = CorrelationServiceConfig()
        self.assertEqual(cfg.trigger, CorrelationTrigger.ON_SCAN_COMPLETE)
        self.assertEqual(cfg.rules_dir, "correlations")
        self.assertEqual(cfg.max_workers, 2)
        self.assertTrue(cfg.subscribe_events)
        self.assertEqual(cfg.excluded_rules, [])

    def test_from_config(self):
        opts = {
            "_correlation_trigger": "manual",
            "_correlation_rules_dir": "/tmp/rules",
            "_correlation_batch_window": "10",
            "_correlation_max_workers": "4",
            "_correlation_excluded_rules": "rule1, rule2",
            "_correlation_risk_filter": "HIGH, MEDIUM",
        }
        cfg = CorrelationServiceConfig.from_config(opts)
        self.assertEqual(cfg.trigger, CorrelationTrigger.MANUAL)
        self.assertEqual(cfg.rules_dir, "/tmp/rules")
        self.assertEqual(cfg.batch_window, 10.0)
        self.assertEqual(cfg.max_workers, 4)
        self.assertEqual(cfg.excluded_rules, ["rule1", "rule2"])
        self.assertEqual(cfg.risk_filter, ["HIGH", "MEDIUM"])

    def test_from_config_invalid_trigger(self):
        cfg = CorrelationServiceConfig.from_config(
            {"_correlation_trigger": "bogus"})
        self.assertEqual(cfg.trigger, CorrelationTrigger.ON_SCAN_COMPLETE)


class TestCorrelationResult(unittest.TestCase):
    """Tests for CorrelationResult dataclass."""

    def test_creation(self):
        r = CorrelationResult(
            rule_id="test_rule",
            rule_name="Test Rule",
            headline="Found something",
            risk="HIGH",
            scan_id="scan-1",
            event_count=3,
        )
        self.assertEqual(r.rule_id, "test_rule")
        self.assertEqual(r.event_count, 3)
        self.assertIsInstance(r.timestamp, float)


class TestCorrelationService(unittest.TestCase):
    """Tests for the CorrelationService class."""

    def test_init(self):
        cfg = CorrelationServiceConfig(rules_dir="/nonexistent")
        svc = CorrelationService(cfg)
        self.assertEqual(svc.rule_count, 0)
        self.assertFalse(svc._running)

    def test_from_config(self):
        svc = CorrelationService.from_config({
            "_correlation_trigger": "manual",
        })
        self.assertEqual(svc.config.trigger, CorrelationTrigger.MANUAL)

    def test_start_stop(self):
        cfg = CorrelationServiceConfig(
            rules_dir="/nonexistent",
            subscribe_events=False,
        )
        svc = CorrelationService(cfg)
        svc.start()
        self.assertTrue(svc._running)
        self.assertIsNotNone(svc._worker_thread)

        svc.stop()
        self.assertFalse(svc._running)

    def test_status(self):
        cfg = CorrelationServiceConfig(rules_dir="/nonexistent")
        svc = CorrelationService(cfg)
        s = svc.status()
        self.assertFalse(s["running"])
        self.assertEqual(s["rule_count"], 0)
        self.assertIn("trigger", s)

    def test_submit_scan(self):
        cfg = CorrelationServiceConfig(
            rules_dir="/nonexistent",
            subscribe_events=False,
        )
        svc = CorrelationService(cfg)
        svc.submit_scan("scan-123", ["rule1"])
        item = svc._queue.get_nowait()
        self.assertEqual(item, ("scan", "scan-123", ["rule1"]))

    def test_result_cache(self):
        cfg = CorrelationServiceConfig(rules_dir="/nonexistent")
        svc = CorrelationService(cfg)

        results = [CorrelationResult(
            rule_id="r1", rule_name="R1", headline="H1",
            risk="HIGH", scan_id="s1", event_count=1,
        )]
        svc._results_cache["s1"] = results

        cached = svc.get_results("s1")
        self.assertEqual(len(cached), 1)
        self.assertEqual(cached[0].rule_id, "r1")

        svc.clear_cache("s1")
        self.assertEqual(svc.get_results("s1"), [])

    def test_clear_all_cache(self):
        cfg = CorrelationServiceConfig(rules_dir="/nonexistent")
        svc = CorrelationService(cfg)
        svc._results_cache["s1"] = []
        svc._results_cache["s2"] = []
        svc.clear_cache()
        self.assertEqual(len(svc._results_cache), 0)

    def test_callback_registration(self):
        cfg = CorrelationServiceConfig(rules_dir="/nonexistent")
        svc = CorrelationService(cfg)

        received = []
        svc.on_result(lambda r: received.append(r))

        result = CorrelationResult(
            rule_id="r1", rule_name="R1", headline="H1",
            risk="HIGH", scan_id="s1", event_count=1,
        )
        svc._notify_callbacks(result)
        self.assertEqual(len(received), 1)

    def test_callback_error_resilience(self):
        cfg = CorrelationServiceConfig(rules_dir="/nonexistent")
        svc = CorrelationService(cfg)

        def bad_cb(r):
            raise RuntimeError("boom")

        received = []
        svc.on_result(bad_cb)
        svc.on_result(lambda r: received.append(r))

        result = CorrelationResult(
            rule_id="r1", rule_name="R1", headline="H1",
            risk="HIGH", scan_id="s1", event_count=1,
        )
        # Should not raise
        svc._notify_callbacks(result)
        self.assertEqual(len(received), 1)

    def test_on_scan_completed_event(self):
        cfg = CorrelationServiceConfig(
            rules_dir="/nonexistent",
            subscribe_events=False,
        )
        svc = CorrelationService(cfg)
        svc._running = True

        event = {"scan_id": "test-scan-1"}
        svc._on_scan_completed(event)

        item = svc._queue.get_nowait()
        self.assertEqual(item[1], "test-scan-1")

    def test_on_scan_completed_ignored_manual(self):
        cfg = CorrelationServiceConfig(
            rules_dir="/nonexistent",
            trigger=CorrelationTrigger.MANUAL,
        )
        svc = CorrelationService(cfg)

        svc._on_scan_completed({"scan_id": "test-scan"})
        self.assertTrue(svc._queue.empty())

    def test_rules_property(self):
        cfg = CorrelationServiceConfig(rules_dir="/nonexistent")
        svc = CorrelationService(cfg)
        svc._rules = [{"id": "r1"}, {"id": "r2"}]
        self.assertEqual(len(svc.rules), 2)
        # Verify it returns a copy
        svc.rules.append({"id": "r3"})
        self.assertEqual(len(svc._rules), 2)

    def test_to_dict(self):
        cfg = CorrelationServiceConfig(rules_dir="/nonexistent")
        svc = CorrelationService(cfg)
        d = svc.to_dict()
        self.assertIn("running", d)
        self.assertIn("rule_count", d)


class TestGetCorrelationService(unittest.TestCase):
    """Tests for the singleton accessor."""

    def test_returns_instance(self):
        import spiderfoot.correlation_service as mod
        mod._instance = None  # Reset singleton
        svc = get_correlation_service({})
        self.assertIsInstance(svc, CorrelationService)
        mod._instance = None  # Clean up


if __name__ == "__main__":
    unittest.main()
