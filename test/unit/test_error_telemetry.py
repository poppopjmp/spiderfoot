"""Tests for spiderfoot.error_telemetry."""
from __future__ import annotations

import unittest
import time

from spiderfoot.error_telemetry import (
    AlertEvent,
    AlertRule,
    AlertSeverity,
    ErrorClass,
    ErrorGroup,
    ErrorRecord,
    ErrorTelemetry,
    classify_error,
    compute_fingerprint,
)


class TestClassifyError(unittest.TestCase):
    def test_timeout(self):
        self.assertEqual(classify_error("TimeoutError", "read timed out"), ErrorClass.TIMEOUT)

    def test_rate_limited(self):
        self.assertEqual(classify_error("HTTPError", "429 Too Many Requests"), ErrorClass.RATE_LIMITED)

    def test_auth(self):
        self.assertEqual(classify_error("HTTPError", "401 Unauthorized"), ErrorClass.AUTH_FAILURE)

    def test_network(self):
        self.assertEqual(classify_error("ConnectionError", "refused"), ErrorClass.TRANSIENT_NETWORK)

    def test_resource(self):
        self.assertEqual(classify_error("MemoryError", "out of memory"), ErrorClass.RESOURCE_EXHAUSTION)

    def test_parse(self):
        self.assertEqual(classify_error("JSONDecodeError", "bad json"), ErrorClass.DATA_PARSE)

    def test_internal(self):
        self.assertEqual(classify_error("RuntimeError", "test"), ErrorClass.INTERNAL)

    def test_unknown_no_type(self):
        self.assertEqual(classify_error("", "something"), ErrorClass.UNKNOWN)


class TestFingerprint(unittest.TestCase):
    def test_deterministic(self):
        fp1 = compute_fingerprint("ValueError", "mod1", "file.py", 10)
        fp2 = compute_fingerprint("ValueError", "mod1", "file.py", 10)
        self.assertEqual(fp1, fp2)

    def test_different_inputs(self):
        fp1 = compute_fingerprint("ValueError", "mod1", "file.py", 10)
        fp2 = compute_fingerprint("TypeError", "mod1", "file.py", 10)
        self.assertNotEqual(fp1, fp2)

    def test_length(self):
        fp = compute_fingerprint("X", "Y", "Z", 0)
        self.assertEqual(len(fp), 16)


class TestErrorRecord(unittest.TestCase):
    def test_to_dict(self):
        r = ErrorRecord(
            fingerprint="abc123",
            exception_type="ValueError",
            message="bad",
            module_name="sfp_test",
            error_class=ErrorClass.DATA_PARSE,
        )
        d = r.to_dict()
        self.assertEqual(d["fingerprint"], "abc123")
        self.assertEqual(d["error_class"], "data_parse")


class TestErrorTelemetry(unittest.TestCase):
    def setUp(self):
        self.tel = ErrorTelemetry(ring_size=100, window_seconds=60.0)

    def test_capture_exception(self):
        try:
            raise ValueError("test error")
        except ValueError as e:
            rec = self.tel.capture(e, module_name="sfp_test", scan_id="s1")

        self.assertEqual(rec.exception_type, "ValueError")
        self.assertEqual(rec.module_name, "sfp_test")
        self.assertIn("ValueError", rec.traceback)
        self.assertNotEqual(rec.source_line, 0)

    def test_capture_no_exception(self):
        rec = self.tel.capture(message="something bad", module_name="sfp_mod")
        self.assertEqual(rec.exception_type, "")
        self.assertEqual(rec.message, "something bad")

    def test_capture_from_log(self):
        rec = self.tel.capture_from_log("api failed", module_name="sfp_api")
        self.assertEqual(rec.message, "api failed")

    def test_grouping(self):
        for _ in range(5):
            try:
                raise TypeError("grp test")
            except TypeError as e:
                self.tel.capture(e, module_name="sfp_x", scan_id="s1")

        groups = self.tel.top_errors(10)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].count, 5)

    def test_ring_buffer_limit(self):
        tel = ErrorTelemetry(ring_size=5)
        for i in range(10):
            tel.capture(message=f"err{i}")
        recent = tel.recent_errors(limit=100)
        self.assertEqual(len(recent), 5)

    def test_recent_filter_module(self):
        self.tel.capture(message="a", module_name="mod1")
        self.tel.capture(message="b", module_name="mod2")
        results = self.tel.recent_errors(module_name="mod1")
        self.assertEqual(len(results), 1)

    def test_recent_filter_scan(self):
        self.tel.capture(message="a", scan_id="s1")
        self.tel.capture(message="b", scan_id="s2")
        results = self.tel.recent_errors(scan_id="s1")
        self.assertEqual(len(results), 1)

    def test_recent_filter_class(self):
        self.tel.capture(
            message="timeout",
            error_class=ErrorClass.TIMEOUT,
        )
        self.tel.capture(
            message="parse",
            error_class=ErrorClass.DATA_PARSE,
        )
        results = self.tel.recent_errors(error_class=ErrorClass.TIMEOUT)
        self.assertEqual(len(results), 1)

    def test_error_rate(self):
        for _ in range(10):
            self.tel.capture(message="err", module_name="sfp_fast")
        rate = self.tel.error_rate()
        self.assertGreater(rate, 0)
        mod_rate = self.tel.error_rate("sfp_fast")
        self.assertGreater(mod_rate, 0)

    def test_error_rate_no_module(self):
        self.assertEqual(self.tel.error_rate("nonexistent"), 0.0)

    def test_error_count(self):
        self.tel.capture(message="a", module_name="m1")
        self.tel.capture(message="b", module_name="m1")
        self.assertEqual(self.tel.error_count("m1"), 2)
        self.assertEqual(self.tel.error_count("m2"), 0)

    def test_get_group(self):
        try:
            raise RuntimeError("x")
        except RuntimeError as e:
            rec = self.tel.capture(e, module_name="m")
        grp = self.tel.get_group(rec.fingerprint)
        self.assertIsNotNone(grp)
        self.assertEqual(grp.count, 1)

    def test_groups_for_module(self):
        self.tel.capture(message="a", module_name="m1")
        self.tel.capture(message="b", module_name="m2")
        groups = self.tel.groups_for_module("m1")
        self.assertTrue(all(g.module_name == "m1" for g in groups))

    def test_groups_for_scan(self):
        self.tel.capture(message="a", scan_id="s1")
        self.tel.capture(message="b", scan_id="s2")
        groups = self.tel.groups_for_scan("s1")
        self.assertEqual(len(groups), 1)

    def test_affected_modules(self):
        self.tel.capture(message="a", module_name="m1")
        self.tel.capture(message="b", module_name="m1")
        self.tel.capture(message="c", module_name="m2")
        affected = self.tel.affected_modules()
        self.assertEqual(affected["m1"], 2)
        self.assertEqual(affected["m2"], 1)

    def test_alert_fires(self):
        alerts = []
        rule = AlertRule(
            name="high_rate",
            severity=AlertSeverity.CRITICAL,
            threshold=1.0,  # 1 per minute — easily triggered
            callback=lambda evt: alerts.append(evt),
        )
        self.tel.add_alert(rule)
        self.tel.capture(message="trigger")
        self.assertGreater(len(alerts), 0)
        self.assertEqual(alerts[0].rule_name, "high_rate")

    def test_alert_module_filter(self):
        alerts = []
        rule = AlertRule(
            name="mod_alert",
            severity=AlertSeverity.WARNING,
            threshold=1.0,
            module_filter="sfp_target",
            callback=lambda evt: alerts.append(evt),
        )
        self.tel.add_alert(rule)
        self.tel.capture(message="err", module_name="sfp_other")
        self.assertEqual(len(alerts), 0)  # should not fire

    def test_remove_alert(self):
        rule = AlertRule(name="tmp", severity=AlertSeverity.WARNING, threshold=100)
        self.tel.add_alert(rule)
        self.assertTrue(self.tel.remove_alert("tmp"))
        self.assertFalse(self.tel.remove_alert("nonexistent"))

    def test_alert_history(self):
        rule = AlertRule(
            name="hist",
            severity=AlertSeverity.WARNING,
            threshold=0.1,
        )
        self.tel.add_alert(rule)
        self.tel.capture(message="err")
        history = self.tel.alert_history()
        self.assertGreater(len(history), 0)

    def test_clear(self):
        self.tel.capture(message="err", module_name="m")
        self.tel.clear()
        self.assertEqual(len(self.tel.recent_errors()), 0)
        self.assertEqual(len(self.tel.top_errors()), 0)

    def test_stats(self):
        self.tel.capture(message="a", module_name="m1")
        self.tel.capture(message="b", module_name="m2")
        s = self.tel.stats()
        self.assertEqual(s["total_records"], 2)
        self.assertGreater(s["global_rate_per_min"], 0)
        self.assertEqual(s["modules_affected"], 2)

    def test_auto_classification(self):
        try:
            raise ConnectionError("refused")
        except ConnectionError as e:
            rec = self.tel.capture(e)
        self.assertEqual(rec.error_class, ErrorClass.TRANSIENT_NETWORK)

    def test_explicit_classification(self):
        rec = self.tel.capture(
            message="custom",
            error_class=ErrorClass.AUTH_FAILURE,
        )
        self.assertEqual(rec.error_class, ErrorClass.AUTH_FAILURE)

    def test_affected_scans_tracking(self):
        try:
            raise ValueError("x")
        except ValueError as e:
            self.tel.capture(e, module_name="m", scan_id="s1")
            self.tel.capture(e, module_name="m", scan_id="s2")
        groups = self.tel.top_errors(1)
        self.assertIn("s1", groups[0].affected_scans)
        self.assertIn("s2", groups[0].affected_scans)


if __name__ == "__main__":
    unittest.main()
