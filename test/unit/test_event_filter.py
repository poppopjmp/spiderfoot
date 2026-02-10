"""Tests for spiderfoot.event_filter module."""
from __future__ import annotations

import unittest

from spiderfoot.event_filter import (
    EventFilterChain,
    FilterAction,
    FilterResult,
    ModuleFilter,
    PatternFilter,
    PredicateFilter,
    RiskFilter,
    TypeFilter,
)


class TestTypeFilter(unittest.TestCase):
    def test_allowed_types(self):
        f = TypeFilter(allowed_types={"IP_ADDRESS", "EMAILADDR"})
        self.assertEqual(f.evaluate("IP_ADDRESS", "1.2.3.4"), FilterResult.PASS)
        self.assertEqual(f.evaluate("RAW_DATA", "x"), FilterResult.BLOCK)

    def test_denied_types(self):
        f = TypeFilter(denied_types={"RAW_DATA"})
        self.assertEqual(f.evaluate("RAW_DATA", "x"), FilterResult.BLOCK)
        self.assertEqual(f.evaluate("IP_ADDRESS", "1.2.3.4"), FilterResult.PASS)

    def test_no_restriction(self):
        f = TypeFilter()
        self.assertEqual(f.evaluate("ANYTHING", "data"), FilterResult.PASS)


class TestPatternFilter(unittest.TestCase):
    def test_deny_pattern(self):
        f = PatternFilter(r"password", action=FilterAction.DENY)
        self.assertEqual(f.evaluate("TEST", "my password is 123"), FilterResult.BLOCK)
        self.assertEqual(f.evaluate("TEST", "hello world"), FilterResult.SKIP)

    def test_allow_pattern(self):
        f = PatternFilter(r"^192\.168\.", action=FilterAction.ALLOW)
        self.assertEqual(f.evaluate("IP_ADDRESS", "192.168.1.1"), FilterResult.PASS)
        self.assertEqual(f.evaluate("IP_ADDRESS", "10.0.0.1"), FilterResult.SKIP)

    def test_case_insensitive(self):
        f = PatternFilter(r"SECRET", action=FilterAction.DENY)
        self.assertEqual(f.evaluate("TEST", "this is a secret"), FilterResult.BLOCK)


class TestRiskFilter(unittest.TestCase):
    def test_min_risk(self):
        f = RiskFilter(min_risk=50)
        self.assertEqual(f.evaluate("TEST", "x", risk=60), FilterResult.PASS)
        self.assertEqual(f.evaluate("TEST", "x", risk=30), FilterResult.BLOCK)

    def test_max_risk(self):
        f = RiskFilter(max_risk=80)
        self.assertEqual(f.evaluate("TEST", "x", risk=60), FilterResult.PASS)
        self.assertEqual(f.evaluate("TEST", "x", risk=90), FilterResult.BLOCK)

    def test_range(self):
        f = RiskFilter(min_risk=20, max_risk=80)
        self.assertEqual(f.evaluate("TEST", "x", risk=50), FilterResult.PASS)
        self.assertEqual(f.evaluate("TEST", "x", risk=10), FilterResult.BLOCK)

    def test_default_risk(self):
        f = RiskFilter(min_risk=10)
        # No risk kwarg → defaults to 0
        self.assertEqual(f.evaluate("TEST", "x"), FilterResult.BLOCK)


class TestModuleFilter(unittest.TestCase):
    def test_allowed_modules(self):
        f = ModuleFilter(allowed_modules={"sfp_dns", "sfp_ssl"})
        self.assertEqual(f.evaluate("TEST", "x", module="sfp_dns"), FilterResult.PASS)
        self.assertEqual(f.evaluate("TEST", "x", module="sfp_shodan"), FilterResult.BLOCK)

    def test_denied_modules(self):
        f = ModuleFilter(denied_modules={"sfp_test"})
        self.assertEqual(f.evaluate("TEST", "x", module="sfp_test"), FilterResult.BLOCK)
        self.assertEqual(f.evaluate("TEST", "x", module="sfp_dns"), FilterResult.PASS)


class TestPredicateFilter(unittest.TestCase):
    def test_predicate_pass(self):
        f = PredicateFilter(lambda et, d, **kw: len(d) > 3)
        self.assertEqual(f.evaluate("TEST", "long data"), FilterResult.PASS)
        self.assertEqual(f.evaluate("TEST", "ab"), FilterResult.BLOCK)

    def test_predicate_error(self):
        f = PredicateFilter(lambda et, d, **kw: 1 / 0, name="bad")
        result = f.evaluate("TEST", "x")
        self.assertEqual(result, FilterResult.SKIP)


class TestEventFilterChain(unittest.TestCase):
    def test_empty_chain_passes_all(self):
        chain = EventFilterChain()
        self.assertTrue(chain.check("TEST", "data"))

    def test_type_deny(self):
        chain = EventFilterChain()
        chain.add(TypeFilter(denied_types={"RAW_DATA"}))
        self.assertFalse(chain.check("RAW_DATA", "x"))
        self.assertTrue(chain.check("IP_ADDRESS", "1.2.3.4"))

    def test_multiple_filters_all_pass(self):
        chain = EventFilterChain(mode="all_pass")
        chain.add(TypeFilter(denied_types={"RAW_DATA"}))
        chain.add(RiskFilter(min_risk=10))

        # Passes type but fails risk
        self.assertFalse(chain.check("IP_ADDRESS", "1.2.3.4", risk=5))
        # Passes both
        self.assertTrue(chain.check("IP_ADDRESS", "1.2.3.4", risk=50))

    def test_any_pass_mode(self):
        chain = EventFilterChain(mode="any_pass")
        chain.add(TypeFilter(allowed_types={"IP_ADDRESS"}))
        chain.add(RiskFilter(min_risk=50))

        # Type passes, risk fails → at least one passed
        self.assertTrue(chain.check("IP_ADDRESS", "1.2.3.4", risk=10))
        # Both fail
        self.assertFalse(chain.check("RAW_DATA", "x", risk=10))

    def test_chaining(self):
        chain = (
            EventFilterChain()
            .add(TypeFilter(denied_types={"RAW_DATA"}))
            .add(RiskFilter(min_risk=10))
        )
        self.assertEqual(chain.filter_count, 2)

    def test_remove_filter(self):
        chain = EventFilterChain()
        chain.add(TypeFilter(name="my_type_filter"))
        self.assertTrue(chain.remove("my_type_filter"))
        self.assertEqual(chain.filter_count, 0)

    def test_disabled_filter_skipped(self):
        chain = EventFilterChain()
        f = TypeFilter(denied_types={"RAW_DATA"})
        f.disable()
        chain.add(f)
        # Would normally block, but filter is disabled
        self.assertTrue(chain.check("RAW_DATA", "x"))

    def test_stats(self):
        chain = EventFilterChain(name="test_chain")
        chain.add(TypeFilter(denied_types={"RAW_DATA"}, name="type_f"))
        chain.check("IP_ADDRESS", "1.2.3.4")
        chain.check("RAW_DATA", "x")

        stats = chain.get_stats()
        self.assertEqual(stats["name"], "test_chain")
        self.assertEqual(stats["total_checked"], 2)
        self.assertEqual(stats["total_passed"], 1)
        self.assertEqual(stats["total_blocked"], 1)

    def test_filter_stats(self):
        chain = EventFilterChain()
        chain.add(TypeFilter(denied_types={"RAW_DATA"}, name="tf"))
        chain.check("IP_ADDRESS", "1.2.3.4")
        chain.check("RAW_DATA", "x")

        stats = chain.get_stats()
        tf_stats = stats["filters"][0]
        self.assertEqual(tf_stats["evaluated"], 2)
        self.assertEqual(tf_stats["passed"], 1)
        self.assertEqual(tf_stats["blocked"], 1)

    def test_check_batch(self):
        chain = EventFilterChain()
        chain.add(TypeFilter(denied_types={"RAW_DATA"}))

        events = [
            {"event_type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"event_type": "RAW_DATA", "data": "x"},
            {"event_type": "EMAILADDR", "data": "a@b.com"},
        ]
        results = chain.check_batch(events)
        self.assertEqual(results, [True, False, True])

    def test_reset_stats(self):
        chain = EventFilterChain()
        chain.add(TypeFilter(name="tf"))
        chain.check("TEST", "x")
        chain.reset_stats()

        stats = chain.get_stats()
        self.assertEqual(stats["total_checked"], 0)

    def test_get_filter_names(self):
        chain = EventFilterChain()
        chain.add(TypeFilter(name="a"))
        chain.add(RiskFilter(name="b"))
        self.assertEqual(chain.get_filter_names(), ["a", "b"])

    def test_to_dict(self):
        chain = EventFilterChain(name="test")
        chain.add(TypeFilter(name="tf"))
        d = chain.to_dict()
        self.assertIn("name", d)
        self.assertIn("filters", d)


if __name__ == "__main__":
    unittest.main()
