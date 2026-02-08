"""Tests for spiderfoot.module_deps module."""

import unittest

from spiderfoot.module_deps import (
    DepStatus,
    ModuleDependencyResolver,
    ModuleNode,
    ResolutionResult,
)


class TestModuleNode(unittest.TestCase):
    def test_frozen(self):
        node = ModuleNode(name="sfp_test", produces=frozenset({"IP"}), consumes=frozenset({"DOMAIN"}))
        self.assertEqual(node.name, "sfp_test")
        self.assertIn("IP", node.produces)
        self.assertIn("DOMAIN", node.consumes)


class TestModuleDependencyResolver(unittest.TestCase):
    def setUp(self):
        self.resolver = ModuleDependencyResolver()

    def test_add_remove_module(self):
        self.resolver.add_module("sfp_a", produces={"IP_ADDRESS"})
        self.assertEqual(self.resolver.module_count, 1)
        self.assertTrue(self.resolver.remove_module("sfp_a"))
        self.assertEqual(self.resolver.module_count, 0)
        self.assertFalse(self.resolver.remove_module("sfp_nonexistent"))

    def test_chaining(self):
        r = (
            self.resolver
            .add_module("a", produces={"X"})
            .add_module("b", consumes={"X"})
        )
        self.assertIs(r, self.resolver)
        self.assertEqual(self.resolver.module_count, 2)

    def test_simple_linear_deps(self):
        self.resolver.add_module("sfp_target", produces={"DOMAIN_NAME"})
        self.resolver.add_module("sfp_dns", produces={"IP_ADDRESS"}, consumes={"DOMAIN_NAME"})
        self.resolver.add_module("sfp_geoip", produces={"GEOINFO"}, consumes={"IP_ADDRESS"})

        result = self.resolver.resolve()
        self.assertTrue(result.is_resolved)
        order = result.load_order
        self.assertLess(order.index("sfp_target"), order.index("sfp_dns"))
        self.assertLess(order.index("sfp_dns"), order.index("sfp_geoip"))

    def test_layers(self):
        self.resolver.add_module("sfp_target", produces={"DOMAIN_NAME"})
        self.resolver.add_module("sfp_dns", produces={"IP_ADDRESS"}, consumes={"DOMAIN_NAME"})
        self.resolver.add_module("sfp_whois", produces={"DOMAIN_WHOIS"}, consumes={"DOMAIN_NAME"})

        result = self.resolver.resolve()
        self.assertTrue(result.is_resolved)
        # dns and whois should be in the same layer (both depend on target)
        self.assertTrue(len(result.layers) >= 2)
        # First layer has target, second has dns + whois
        self.assertIn("sfp_target", result.layers[0])

    def test_cycle_detection(self):
        self.resolver.add_module("a", produces={"X"}, consumes={"Y"})
        self.resolver.add_module("b", produces={"Y"}, consumes={"X"})

        result = self.resolver.resolve()
        self.assertEqual(result.status, DepStatus.CIRCULAR)
        self.assertTrue(len(result.cycles) > 0)

    def test_missing_provider(self):
        self.resolver.add_module("sfp_dns", produces={"IP_ADDRESS"}, consumes={"DOMAIN_NAME"})

        result = self.resolver.resolve()
        self.assertEqual(result.status, DepStatus.MISSING_PROVIDER)
        self.assertIn("DOMAIN_NAME", result.missing_providers)

    def test_empty_resolver(self):
        result = self.resolver.resolve()
        self.assertTrue(result.is_resolved)
        self.assertEqual(len(result.load_order), 0)

    def test_standalone_modules(self):
        self.resolver.add_module("sfp_a", produces={"X"})
        self.resolver.add_module("sfp_b", produces={"Y"})

        result = self.resolver.resolve()
        self.assertTrue(result.is_resolved)
        self.assertEqual(len(result.load_order), 2)

    def test_get_producers(self):
        self.resolver.add_module("sfp_dns", produces={"IP_ADDRESS"})
        self.resolver.add_module("sfp_scan", produces={"IP_ADDRESS"})
        producers = self.resolver.get_producers("IP_ADDRESS")
        self.assertEqual(producers, {"sfp_dns", "sfp_scan"})

    def test_get_consumers(self):
        self.resolver.add_module("sfp_a", consumes={"IP_ADDRESS"})
        self.resolver.add_module("sfp_b", optional_consumes={"IP_ADDRESS"})
        consumers = self.resolver.get_consumers("IP_ADDRESS")
        self.assertEqual(consumers, {"sfp_a", "sfp_b"})

    def test_get_dependencies(self):
        self.resolver.add_module("sfp_target", produces={"DOMAIN_NAME"})
        self.resolver.add_module("sfp_dns", consumes={"DOMAIN_NAME"})
        deps = self.resolver.get_dependencies("sfp_dns")
        self.assertEqual(deps, {"sfp_target"})

    def test_get_dependents(self):
        self.resolver.add_module("sfp_target", produces={"DOMAIN_NAME"})
        self.resolver.add_module("sfp_dns", consumes={"DOMAIN_NAME"})
        dependents = self.resolver.get_dependents("sfp_target")
        self.assertEqual(dependents, {"sfp_dns"})

    def test_get_impact(self):
        self.resolver.add_module("a", produces={"X"})
        self.resolver.add_module("b", produces={"Y"}, consumes={"X"})
        self.resolver.add_module("c", consumes={"Y"})

        impact = self.resolver.get_impact("a")
        self.assertEqual(impact, {"b", "c"})

    def test_get_critical_path(self):
        self.resolver.add_module("a", produces={"X"})
        self.resolver.add_module("b", produces={"Y"}, consumes={"X"})
        self.resolver.add_module("c", produces={"Z"}, consumes={"Y"})

        path = self.resolver.get_critical_path("c")
        self.assertEqual(path, ["a", "b", "c"])

    def test_optional_consumes_not_required(self):
        self.resolver.add_module("sfp_a", produces={"X"}, optional_consumes={"MISSING"})
        result = self.resolver.resolve()
        # Optional consumes shouldn't cause MISSING_PROVIDER
        self.assertTrue(result.is_resolved)

    def test_self_loop_ignored(self):
        self.resolver.add_module("sfp_a", produces={"X"}, consumes={"X"})
        result = self.resolver.resolve()
        # Self-loops are filtered out in edge building
        self.assertTrue(result.is_resolved)

    def test_module_names(self):
        self.resolver.add_module("sfp_b")
        self.resolver.add_module("sfp_a")
        self.assertEqual(self.resolver.module_names, ["sfp_a", "sfp_b"])

    def test_to_dict(self):
        self.resolver.add_module("sfp_dns", produces={"IP_ADDRESS"}, consumes={"DOMAIN_NAME"})
        d = self.resolver.to_dict()
        self.assertIn("modules", d)
        self.assertIn("sfp_dns", d["modules"])
        self.assertIn("producer_index", d)

    def test_resolution_result_summary(self):
        self.resolver.add_module("a", produces={"X"})
        result = self.resolver.resolve()
        s = result.summary()
        self.assertIn("resolved", s)

    def test_resolution_result_to_dict(self):
        self.resolver.add_module("a", produces={"X"})
        result = self.resolver.resolve()
        d = result.to_dict()
        self.assertIn("status", d)
        self.assertIn("load_order", d)
        self.assertIn("layers", d)

    def test_diamond_dependency(self):
        """A -> B, A -> C, B -> D, C -> D (diamond)."""
        self.resolver.add_module("a", produces={"X"})
        self.resolver.add_module("b", produces={"Y"}, consumes={"X"})
        self.resolver.add_module("c", produces={"Z"}, consumes={"X"})
        self.resolver.add_module("d", consumes={"Y", "Z"})

        result = self.resolver.resolve()
        self.assertTrue(result.is_resolved)
        order = result.load_order
        self.assertLess(order.index("a"), order.index("b"))
        self.assertLess(order.index("a"), order.index("c"))
        self.assertLess(order.index("b"), order.index("d"))
        self.assertLess(order.index("c"), order.index("d"))

    def test_multiple_producers(self):
        self.resolver.add_module("a", produces={"IP_ADDRESS"})
        self.resolver.add_module("b", produces={"IP_ADDRESS"})
        self.resolver.add_module("c", consumes={"IP_ADDRESS"})

        result = self.resolver.resolve()
        self.assertTrue(result.is_resolved)
        edges = [e for e in result.edges if e.consumer == "c"]
        self.assertEqual(len(edges), 2)

    def test_get_dependencies_nonexistent(self):
        self.assertEqual(self.resolver.get_dependencies("nonexistent"), set())

    def test_get_dependents_nonexistent(self):
        self.assertEqual(self.resolver.get_dependents("nonexistent"), set())

    def test_get_critical_path_nonexistent(self):
        self.assertEqual(self.resolver.get_critical_path("nonexistent"), [])

    def test_get_impact_nonexistent(self):
        self.assertEqual(self.resolver.get_impact("nonexistent"), set())


if __name__ == "__main__":
    unittest.main()
