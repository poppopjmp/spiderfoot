"""Tests for spiderfoot.module_resolver."""
from __future__ import annotations

import unittest

from spiderfoot.plugins.module_resolver import (
    DepKind,
    ModuleDescriptor,
    ModuleResolver,
    ResolveStatus,
)


def _make_desc(name, watched=None, produced=None, required=None, optional=None):
    return ModuleDescriptor(
        name=name,
        watched_events=watched or [],
        produced_events=produced or [],
        required_events=required or [],
        optional_events=optional or [],
    )


class TestModuleDescriptor(unittest.TestCase):
    def test_watched_set(self):
        d = _make_desc("m", watched=["A", "B"])
        self.assertEqual(d.watched_set, frozenset(["A", "B"]))

    def test_produced_set(self):
        d = _make_desc("m", produced=["X"])
        self.assertEqual(d.produced_set, frozenset(["X"]))

    def test_to_dict(self):
        d = _make_desc("m", watched=["A"], produced=["B"])
        out = d.to_dict()
        self.assertEqual(out["name"], "m")
        self.assertEqual(out["watched_events"], ["A"])


class TestModuleResolver(unittest.TestCase):
    def setUp(self):
        self.r = ModuleResolver()
        # Build a chain: target → dns → portscan → vulnscan
        self.r.register(_make_desc(
            "sfp_target",
            watched_events=["ROOT"],
            produced_events=["DOMAIN_NAME", "IP_ADDRESS_INTERNAL"],
        ))
        self.r.register(_make_desc(
            "sfp_dns",
            watched_events=["DOMAIN_NAME"],
            produced_events=["IP_ADDRESS"],
        ))
        self.r.register(_make_desc(
            "sfp_portscan",
            watched_events=["IP_ADDRESS"],
            produced_events=["TCP_PORT_OPEN"],
        ))
        self.r.register(_make_desc(
            "sfp_vulnscan",
            watched_events=["TCP_PORT_OPEN"],
            produced_events=["VULNERABILITY"],
        ))

    def test_register_and_list(self):
        self.assertEqual(len(self.r.list_modules()), 4)

    def test_register_many(self):
        r2 = ModuleResolver()
        n = r2.register_many([
            _make_desc("a", produced=["X"]),
            _make_desc("b", watched=["X"]),
        ])
        self.assertEqual(n, 2)

    def test_unregister(self):
        self.assertTrue(self.r.unregister("sfp_vulnscan"))
        self.assertFalse(self.r.unregister("nonexistent"))
        self.assertEqual(len(self.r.list_modules()), 3)

    def test_get_module(self):
        m = self.r.get_module("sfp_dns")
        self.assertEqual(m.name, "sfp_dns")
        self.assertIsNone(self.r.get_module("nope"))

    def test_producers_of(self):
        p = self.r.producers_of("IP_ADDRESS")
        self.assertIn("sfp_dns", p)

    def test_consumers_of(self):
        c = self.r.consumers_of("DOMAIN_NAME")
        self.assertIn("sfp_dns", c)

    def test_all_event_types(self):
        evts = self.r.all_event_types()
        self.assertIn("VULNERABILITY")
        self.assertIn("ROOT")

    def test_resolve_target_events(self):
        result = self.r.resolve(target_events=["VULNERABILITY"])
        self.assertTrue(result.ok)
        self.assertIn("sfp_vulnscan", result.selected_modules)
        self.assertIn("sfp_portscan", result.selected_modules)
        self.assertIn("sfp_dns", result.selected_modules)
        # Load order: dns before portscan before vulnscan
        order = result.load_order
        self.assertLess(
            order.index("sfp_dns"),
            order.index("sfp_portscan"),
        )
        self.assertLess(
            order.index("sfp_portscan"),
            order.index("sfp_vulnscan"),
        )

    def test_resolve_required_modules(self):
        result = self.r.resolve(required_modules=["sfp_portscan"])
        self.assertTrue(result.ok)
        self.assertIn("sfp_portscan", result.selected_modules)

    def test_resolve_exclude(self):
        result = self.r.resolve(
            target_events=["VULNERABILITY"],
            exclude_modules={"sfp_dns"},
        )
        self.assertNotIn("sfp_dns", result.selected_modules)

    def test_resolve_missing_deps(self):
        r2 = ModuleResolver()
        r2.register(_make_desc(
            "sfp_orphan",
            watched_events=["NONEXISTENT_EVENT"],
            produced_events=["RESULT"],
        ))
        result = r2.resolve(target_events=["RESULT"])
        self.assertEqual(result.status, ResolveStatus.MISSING_DEPS)
        self.assertTrue(len(result.missing_events) > 0)

    def test_resolve_missing_target(self):
        result = self.r.resolve(target_events=["DOES_NOT_EXIST"])
        self.assertEqual(result.status, ResolveStatus.MISSING_DEPS)

    def test_resolve_circular(self):
        r2 = ModuleResolver()
        r2.register(_make_desc("a", watched=["X"], produced=["Y"]))
        r2.register(_make_desc("b", watched=["Y"], produced=["X"]))
        result = r2.resolve(target_events=["X"])
        # Both modules selected, they form a cycle
        self.assertEqual(result.status, ResolveStatus.CIRCULAR)
        self.assertTrue(len(result.circular_chains) > 0)

    def test_resolve_for_modules(self):
        result = self.r.resolve_for_modules(["sfp_portscan"])
        self.assertIn("sfp_portscan", result.selected_modules)

    def test_check_satisfaction(self):
        # sfp_portscan needs IP_ADDRESS, sfp_dns needs DOMAIN_NAME
        unsat = self.r.check_satisfaction(["sfp_portscan"])
        self.assertIn("sfp_portscan", unsat)
        self.assertIn("IP_ADDRESS", unsat["sfp_portscan"])

    def test_check_satisfaction_satisfied(self):
        unsat = self.r.check_satisfaction(
            ["sfp_target", "sfp_dns", "sfp_portscan"]
        )
        self.assertNotIn("sfp_portscan", unsat)

    def test_to_dict(self):
        result = self.r.resolve(target_events=["TCP_PORT_OPEN"])
        d = result.to_dict()
        self.assertEqual(d["status"], "ok")
        self.assertIsInstance(d["load_order"], list)

    def test_stats(self):
        s = self.r.stats()
        self.assertEqual(s["total_modules"], 4)
        self.assertGreater(s["total_event_types"], 0)

    def test_load_order_deterministic(self):
        r1 = self.r.resolve(target_events=["VULNERABILITY"])
        r2 = self.r.resolve(target_events=["VULNERABILITY"])
        self.assertEqual(r1.load_order, r2.load_order)


if __name__ == "__main__":
    unittest.main()
