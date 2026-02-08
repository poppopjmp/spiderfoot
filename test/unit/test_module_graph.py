#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for spiderfoot.module_graph."""

import unittest

from spiderfoot.module_graph import ModuleGraph, ModuleInfo


class TestModuleInfo(unittest.TestCase):
    """Test ModuleInfo dataclass."""

    def test_defaults(self):
        info = ModuleInfo(name="sfp_test", filename="sfp_test.py")
        self.assertEqual(info.name, "sfp_test")
        self.assertEqual(info.watched_events, [])
        self.assertEqual(info.produced_events, [])
        self.assertEqual(info.display_name, "sfp_test")

    def test_display_name_with_meta(self):
        info = ModuleInfo(
            name="sfp_test", filename="sfp_test.py",
            meta={"name": "Test Module"})
        self.assertEqual(info.display_name, "Test Module")

    def test_to_dict(self):
        info = ModuleInfo(
            name="sfp_test", filename="sfp_test.py",
            watched_events=["IP_ADDRESS"],
            produced_events=["GEOINFO"])
        d = info.to_dict()
        self.assertEqual(d["name"], "sfp_test")
        self.assertIn("IP_ADDRESS", d["watched_events"])


class TestModuleGraph(unittest.TestCase):
    """Test ModuleGraph."""

    def _make_graph(self):
        """Create a graph with 4 modules forming a chain + branch."""
        g = ModuleGraph()

        # Chain: resolver -> geo -> vuln
        # Branch: resolver -> whois
        g.add_module(ModuleInfo(
            name="sfp_resolver",
            filename="sfp_resolver.py",
            watched_events=["DOMAIN_NAME"],
            produced_events=["IP_ADDRESS"],
        ))
        g.add_module(ModuleInfo(
            name="sfp_geo",
            filename="sfp_geo.py",
            watched_events=["IP_ADDRESS"],
            produced_events=["GEOINFO"],
        ))
        g.add_module(ModuleInfo(
            name="sfp_whois",
            filename="sfp_whois.py",
            watched_events=["IP_ADDRESS"],
            produced_events=["WHOIS_DATA"],
        ))
        g.add_module(ModuleInfo(
            name="sfp_vuln",
            filename="sfp_vuln.py",
            watched_events=["IP_ADDRESS", "GEOINFO"],
            produced_events=["VULNERABILITY_CVE_CRITICAL"],
        ))

        g._build_edges()
        return g

    def test_add_module(self):
        g = ModuleGraph()
        g.add_module(ModuleInfo(
            name="sfp_test", filename="sfp_test.py",
            produced_events=["TEST_EVENT"]))
        self.assertIn("sfp_test", g.modules)
        self.assertIn("sfp_test", g._producers["TEST_EVENT"])

    def test_producers_of(self):
        g = self._make_graph()
        self.assertEqual(g.producers_of("IP_ADDRESS"), ["sfp_resolver"])
        self.assertEqual(g.producers_of("GEOINFO"), ["sfp_geo"])
        self.assertEqual(g.producers_of("NONEXISTENT"), [])

    def test_consumers_of(self):
        g = self._make_graph()
        consumers = g.consumers_of("IP_ADDRESS")
        self.assertIn("sfp_geo", consumers)
        self.assertIn("sfp_whois", consumers)
        self.assertIn("sfp_vuln", consumers)

    def test_dependencies_of(self):
        g = self._make_graph()
        deps = g.dependencies_of("sfp_vuln")
        self.assertIn("sfp_resolver", deps)  # produces IP_ADDRESS
        self.assertIn("sfp_geo", deps)       # produces GEOINFO

    def test_dependents_of(self):
        g = self._make_graph()
        dependents = g.dependents_of("sfp_resolver")
        self.assertIn("sfp_geo", dependents)
        self.assertIn("sfp_whois", dependents)
        self.assertIn("sfp_vuln", dependents)

    def test_resolve_for_output(self):
        g = self._make_graph()
        needed = g.resolve_for_output(["VULNERABILITY_CVE_CRITICAL"])
        # Must include vuln + its deps
        self.assertIn("sfp_vuln", needed)
        self.assertIn("sfp_geo", needed)
        self.assertIn("sfp_resolver", needed)
        # whois not needed for VULNERABILITY
        self.assertNotIn("sfp_whois", needed)

    def test_topological_order(self):
        g = self._make_graph()
        order = g.topological_order()
        self.assertEqual(len(order), 4)
        # resolver must come before geo, whois, vuln
        r_idx = order.index("sfp_resolver")
        self.assertTrue(order.index("sfp_geo") > r_idx)
        self.assertTrue(order.index("sfp_whois") > r_idx)
        self.assertTrue(order.index("sfp_vuln") > r_idx)

    def test_detect_cycles_no_cycles(self):
        g = self._make_graph()
        cycles = g.detect_cycles()
        self.assertEqual(cycles, [])

    def test_detect_cycles_with_cycle(self):
        g = ModuleGraph()
        g.add_module(ModuleInfo(
            name="sfp_a", filename="a.py",
            watched_events=["B_EVENT"],
            produced_events=["A_EVENT"]))
        g.add_module(ModuleInfo(
            name="sfp_b", filename="b.py",
            watched_events=["A_EVENT"],
            produced_events=["B_EVENT"]))
        g._build_edges()

        cycles = g.detect_cycles()
        self.assertTrue(len(cycles) > 0)

    def test_all_event_types(self):
        g = self._make_graph()
        types = g.all_event_types()
        self.assertIn("IP_ADDRESS", types)
        self.assertIn("DOMAIN_NAME", types)
        self.assertIn("VULNERABILITY_CVE_CRITICAL", types)

    def test_stats(self):
        g = self._make_graph()
        s = g.stats()
        self.assertEqual(s["module_count"], 4)
        self.assertTrue(s["edge_count"] > 0)
        self.assertEqual(s["cycles"], 0)

    def test_to_mermaid(self):
        g = self._make_graph()
        mermaid = g.to_mermaid()
        self.assertTrue(mermaid.startswith("graph LR;"))
        self.assertIn("-->", mermaid)

    def test_to_dot(self):
        g = self._make_graph()
        dot = g.to_dot()
        self.assertIn("digraph", dot)
        self.assertIn("->", dot)

    def test_to_mermaid_max_modules(self):
        g = self._make_graph()
        mermaid = g.to_mermaid(max_modules=2)
        # Should contain at most 2 modules
        self.assertTrue(mermaid.startswith("graph LR;"))

    def test_resolve_empty(self):
        g = self._make_graph()
        needed = g.resolve_for_output(["NONEXISTENT"])
        self.assertEqual(needed, set())

    def test_dependencies_unknown_module(self):
        g = self._make_graph()
        deps = g.dependencies_of("sfp_nonexistent")
        self.assertEqual(deps, set())

    def test_load_modules_bad_dir(self):
        g = ModuleGraph()
        count = g.load_modules("/nonexistent/dir")
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
