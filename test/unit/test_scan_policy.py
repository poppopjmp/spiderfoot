"""Tests for spiderfoot.scan_policy module."""
from __future__ import annotations

import unittest

from spiderfoot.scan_policy import (
    PolicyAction,
    PolicyCheckResult,
    PolicyEngine,
    PolicyViolation,
    ScanPolicy,
    ViolationSeverity,
)


class TestPolicyViolation(unittest.TestCase):
    def test_basic(self):
        v = PolicyViolation(policy_name="p", message="bad", severity=ViolationSeverity.ERROR)
        self.assertEqual(v.policy_name, "p")
        self.assertEqual(v.severity, ViolationSeverity.ERROR)
        self.assertEqual(v.action, PolicyAction.BLOCK)


class TestPolicyCheckResult(unittest.TestCase):
    def test_allowed(self):
        r = PolicyCheckResult(allowed=True)
        self.assertTrue(r.allowed)
        self.assertFalse(r.has_violations)
        self.assertFalse(r.blocked)

    def test_blocked(self):
        v = PolicyViolation(policy_name="p", message="x", action=PolicyAction.BLOCK)
        r = PolicyCheckResult(allowed=False, violations=[v])
        self.assertTrue(r.blocked)


class TestScanPolicy(unittest.TestCase):
    def test_chaining(self):
        p = ScanPolicy("test").set_max_events(100).set_max_depth(3).set_max_duration(3600)
        self.assertEqual(p.name, "test")

    def test_target_exclusion_pattern(self):
        p = ScanPolicy("test").exclude_targets(["*.gov", "*.mil"])
        r = p.check_target("whitehouse.gov")
        self.assertFalse(r.allowed)
        r2 = p.check_target("example.com")
        self.assertTrue(r2.allowed)

    def test_target_exclusion_cidr(self):
        p = ScanPolicy("test").exclude_targets(["10.0.0.0/8"])
        r = p.check_target("10.1.2.3")
        self.assertFalse(r.allowed)
        r2 = p.check_target("192.168.1.1")
        self.assertTrue(r2.allowed)

    def test_allowed_targets(self):
        p = ScanPolicy("test").allow_targets({"example.com", "test.com"})
        self.assertTrue(p.check_target("example.com").allowed)
        self.assertFalse(p.check_target("other.com").allowed)

    def test_module_denied(self):
        p = ScanPolicy("test").restrict_modules(denied={"sfp_malicious"})
        r = p.check_module("sfp_malicious")
        self.assertFalse(r.allowed)
        self.assertTrue(p.check_module("sfp_dns").allowed)

    def test_module_allowed_list(self):
        p = ScanPolicy("test").restrict_modules(allowed={"sfp_dns", "sfp_ssl"})
        self.assertTrue(p.check_module("sfp_dns").allowed)
        self.assertFalse(p.check_module("sfp_shodan").allowed)

    def test_event_type_denied(self):
        p = ScanPolicy("test").deny_event_types({"RAW_DATA"})
        self.assertFalse(p.check_event_type("RAW_DATA").allowed)
        self.assertTrue(p.check_event_type("IP_ADDRESS").allowed)

    def test_event_type_limit(self):
        p = ScanPolicy("test").set_max_events_per_type({"IP_ADDRESS": 100})
        self.assertTrue(p.check_event_type("IP_ADDRESS", current_count=50).allowed)
        self.assertFalse(p.check_event_type("IP_ADDRESS", current_count=100).allowed)

    def test_depth_limit(self):
        p = ScanPolicy("test").set_max_depth(3)
        self.assertTrue(p.check_depth(2).allowed)
        self.assertFalse(p.check_depth(5).allowed)

    def test_event_count_limit(self):
        p = ScanPolicy("test").set_max_events(1000)
        self.assertTrue(p.check_event_count(500).allowed)
        self.assertFalse(p.check_event_count(1000).allowed)

    def test_duration_limit(self):
        p = ScanPolicy("test").set_max_duration(3600)
        self.assertTrue(p.check_duration(1800).allowed)
        self.assertFalse(p.check_duration(7200).allowed)

    def test_disabled_policy_allows_all(self):
        p = ScanPolicy("test").set_max_depth(1)
        p.disable()
        self.assertTrue(p.check_depth(100).allowed)
        self.assertFalse(p.is_enabled)
        p.enable()
        self.assertFalse(p.check_depth(100).allowed)

    def test_violation_tracking(self):
        p = ScanPolicy("test").set_max_depth(1)
        p.check_depth(5)
        self.assertEqual(p.violation_count, 1)
        p.clear_violations()
        self.assertEqual(p.violation_count, 0)

    def test_to_dict(self):
        p = ScanPolicy("test").set_max_events(100).set_max_depth(3)
        d = p.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertEqual(d["max_events"], 100)
        self.assertEqual(d["max_depth"], 3)

    def test_from_dict(self):
        d = {
            "name": "loaded",
            "max_events": 500,
            "max_depth": 5,
            "denied_modules": ["sfp_test"],
            "denied_event_types": ["RAW_DATA"],
        }
        p = ScanPolicy.from_dict(d)
        self.assertEqual(p.name, "loaded")
        self.assertFalse(p.check_module("sfp_test").allowed)
        self.assertFalse(p.check_event_type("RAW_DATA").allowed)

    def test_from_dict_roundtrip(self):
        orig = ScanPolicy("rt").set_max_events(200).set_max_depth(4)
        orig.restrict_modules(denied={"sfp_x"})
        d = orig.to_dict()
        loaded = ScanPolicy.from_dict(d)
        self.assertEqual(loaded.name, "rt")
        self.assertFalse(loaded.check_module("sfp_x").allowed)

    def test_no_limit_allows(self):
        p = ScanPolicy("test")
        self.assertTrue(p.check_depth(999).allowed)
        self.assertTrue(p.check_event_count(999999).allowed)
        self.assertTrue(p.check_duration(999999).allowed)


class TestPolicyEngine(unittest.TestCase):
    def test_add_remove(self):
        engine = PolicyEngine()
        engine.add_policy(ScanPolicy("a"))
        self.assertEqual(engine.policy_count, 1)
        self.assertTrue(engine.remove_policy("a"))
        self.assertEqual(engine.policy_count, 0)
        self.assertFalse(engine.remove_policy("nonexistent"))

    def test_get_policy(self):
        engine = PolicyEngine()
        p = ScanPolicy("test")
        engine.add_policy(p)
        self.assertIs(engine.get_policy("test"), p)
        self.assertIsNone(engine.get_policy("missing"))

    def test_evaluate_target(self):
        engine = PolicyEngine()
        engine.add_policy(ScanPolicy("scope").exclude_targets(["*.gov"]))
        r = engine.evaluate_target("whitehouse.gov")
        self.assertFalse(r.allowed)
        r2 = engine.evaluate_target("example.com")
        self.assertTrue(r2.allowed)

    def test_evaluate_module(self):
        engine = PolicyEngine()
        engine.add_policy(ScanPolicy("restrict").restrict_modules(denied={"sfp_bad"}))
        self.assertFalse(engine.evaluate_module("sfp_bad").allowed)
        self.assertTrue(engine.evaluate_module("sfp_good").allowed)

    def test_evaluate_event_type(self):
        engine = PolicyEngine()
        engine.add_policy(ScanPolicy("ev").deny_event_types({"RAW_DATA"}))
        self.assertFalse(engine.evaluate_event_type("RAW_DATA").allowed)

    def test_multiple_policies(self):
        engine = PolicyEngine()
        engine.add_policy(ScanPolicy("p1").exclude_targets(["*.gov"]))
        engine.add_policy(ScanPolicy("p2").restrict_modules(denied={"sfp_bad"}))

        # Target blocked by p1
        self.assertFalse(engine.evaluate_target("test.gov").allowed)
        # Module blocked by p2
        self.assertFalse(engine.evaluate_module("sfp_bad").allowed)
        # Both OK
        self.assertTrue(engine.evaluate_target("example.com").allowed)

    def test_policy_names(self):
        engine = PolicyEngine()
        engine.add_policy(ScanPolicy("b"))
        engine.add_policy(ScanPolicy("a"))
        self.assertEqual(engine.policy_names, ["a", "b"])

    def test_get_all_violations(self):
        engine = PolicyEngine()
        engine.add_policy(ScanPolicy("p1").set_max_depth(1))
        engine.add_policy(ScanPolicy("p2").set_max_depth(1))
        # Force violations by evaluating through individual policies
        engine.get_policy("p1").check_depth(5)
        engine.get_policy("p2").check_depth(5)
        self.assertEqual(len(engine.get_all_violations()), 2)
        engine.clear_all_violations()
        self.assertEqual(len(engine.get_all_violations()), 0)

    def test_chaining(self):
        engine = PolicyEngine()
        result = engine.add_policy(ScanPolicy("a"))
        self.assertIs(result, engine)

    def test_to_dict(self):
        engine = PolicyEngine()
        engine.add_policy(ScanPolicy("test").set_max_events(100))
        d = engine.to_dict()
        self.assertIn("policies", d)
        self.assertIn("test", d["policies"])


if __name__ == "__main__":
    unittest.main()
