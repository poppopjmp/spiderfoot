"""Tests for spiderfoot.module_caps module."""
from __future__ import annotations

import threading
import unittest

from spiderfoot.module_caps import (
    Capability,
    CapabilityCategory,
    CapabilityRegistry,
    ModuleCapabilityDeclaration,
    Requirement,
    get_capability_registry,
)


class TestCapabilityCategory(unittest.TestCase):
    def test_values(self):
        self.assertEqual(CapabilityCategory.NETWORK.value, "network")
        self.assertEqual(CapabilityCategory.DATA_SOURCE.value, "data_source")
        self.assertEqual(CapabilityCategory.ANALYSIS.value, "analysis")


class TestCapability(unittest.TestCase):
    def test_creation(self):
        c = Capability("dns_resolution", CapabilityCategory.NETWORK, "Resolves DNS")
        self.assertEqual(c.name, "dns_resolution")
        self.assertEqual(c.category, CapabilityCategory.NETWORK)

    def test_str(self):
        c = Capability("dns_resolution", CapabilityCategory.NETWORK)
        self.assertEqual(str(c), "network:dns_resolution")

    def test_frozen(self):
        c = Capability("dns", CapabilityCategory.NETWORK)
        with self.assertRaises(AttributeError):
            c.name = "other"

    def test_hashable(self):
        c1 = Capability("dns", CapabilityCategory.NETWORK)
        c2 = Capability("dns", CapabilityCategory.NETWORK)
        self.assertEqual(c1, c2)
        self.assertEqual(hash(c1), hash(c2))
        s = {c1, c2}
        self.assertEqual(len(s), 1)


class TestRequirement(unittest.TestCase):
    def test_defaults(self):
        r = Requirement("api_key")
        self.assertTrue(r.required)

    def test_optional(self):
        r = Requirement("proxy", required=False)
        self.assertFalse(r.required)

    def test_str(self):
        self.assertIn("required", str(Requirement("api_key")))
        self.assertIn("optional", str(Requirement("proxy", required=False)))


class TestModuleCapabilityDeclaration(unittest.TestCase):
    def test_creation(self):
        d = ModuleCapabilityDeclaration(module_name="sfp_dns")
        self.assertEqual(d.module_name, "sfp_dns")
        self.assertEqual(len(d.provides), 0)

    def test_add_capability_chaining(self):
        d = (
            ModuleCapabilityDeclaration(module_name="sfp_dns")
            .add_capability("dns_resolution", CapabilityCategory.NETWORK)
            .add_capability("reverse_dns", CapabilityCategory.NETWORK)
        )
        self.assertEqual(len(d.provides), 2)
        self.assertIn("dns_resolution", d.capability_names)

    def test_add_requirement_chaining(self):
        d = (
            ModuleCapabilityDeclaration(module_name="sfp_shodan")
            .add_requirement("api_key")
            .add_requirement("proxy", required=False)
        )
        self.assertEqual(len(d.requires), 2)
        self.assertIn("api_key", d.required_names)
        self.assertIn("proxy", d.optional_names)

    def test_add_conflict(self):
        d = ModuleCapabilityDeclaration(module_name="sfp_dns")
        d.add_conflict("sfp_dns_alt")
        self.assertIn("sfp_dns_alt", d.conflicts_with)

    def test_add_tag(self):
        d = ModuleCapabilityDeclaration(module_name="sfp_dns")
        d.add_tag("passive").add_tag("free")
        self.assertIn("passive", d.tags)
        self.assertIn("free", d.tags)

    def test_to_dict(self):
        d = (
            ModuleCapabilityDeclaration(module_name="sfp_dns", priority=10)
            .add_capability("dns", CapabilityCategory.NETWORK)
            .add_requirement("network_access")
            .add_tag("passive")
        )
        result = d.to_dict()
        self.assertEqual(result["module"], "sfp_dns")
        self.assertEqual(result["priority"], 10)
        self.assertEqual(len(result["provides"]), 1)
        self.assertEqual(len(result["requires"]), 1)
        self.assertIn("passive", result["tags"])


class TestCapabilityRegistry(unittest.TestCase):
    def _make_decl(self, name, caps=None, reqs=None, conflicts=None, tags=None, priority=50):
        d = ModuleCapabilityDeclaration(module_name=name, priority=priority)
        for c in (caps or []):
            d.add_capability(c, CapabilityCategory.NETWORK)
        for r in (reqs or []):
            if isinstance(r, tuple):
                d.add_requirement(r[0], required=r[1])
            else:
                d.add_requirement(r)
        for cf in (conflicts or []):
            d.add_conflict(cf)
        for t in (tags or []):
            d.add_tag(t)
        return d

    def test_register_and_get(self):
        reg = CapabilityRegistry()
        decl = self._make_decl("sfp_dns", caps=["dns"])
        reg.register(decl)
        self.assertIsNotNone(reg.get("sfp_dns"))
        self.assertIsNone(reg.get("sfp_nonexistent"))

    def test_unregister(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns", caps=["dns"]))
        reg.unregister("sfp_dns")
        self.assertIsNone(reg.get("sfp_dns"))
        self.assertEqual(reg.find_providers("dns"), [])

    def test_find_providers(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns", caps=["dns_resolution"]))
        reg.register(self._make_decl("sfp_dns_alt", caps=["dns_resolution"]))
        reg.register(self._make_decl("sfp_ssl", caps=["ssl_check"]))

        providers = reg.find_providers("dns_resolution")
        self.assertEqual(len(providers), 2)
        self.assertIn("sfp_dns", providers)
        self.assertIn("sfp_dns_alt", providers)

    def test_find_providers_empty(self):
        reg = CapabilityRegistry()
        self.assertEqual(reg.find_providers("nonexistent"), [])

    def test_find_by_category(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns", caps=["dns"]))
        d2 = ModuleCapabilityDeclaration(module_name="sfp_shodan")
        d2.add_capability("shodan_api", CapabilityCategory.DATA_SOURCE)
        reg.register(d2)

        network = reg.find_by_category(CapabilityCategory.NETWORK)
        self.assertIn("sfp_dns", network)
        self.assertNotIn("sfp_shodan", network)

    def test_find_by_tag(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns", tags=["passive", "free"]))
        reg.register(self._make_decl("sfp_shodan", tags=["active", "api_key"]))

        passive = reg.find_by_tag("passive")
        self.assertEqual(passive, ["sfp_dns"])

    def test_find_conflicts(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns", conflicts=["sfp_dns_alt"]))
        reg.register(self._make_decl("sfp_dns_alt"))
        reg.register(self._make_decl("sfp_ssl"))

        conflicts = reg.find_conflicts(["sfp_dns", "sfp_dns_alt", "sfp_ssl"])
        self.assertEqual(len(conflicts), 1)
        pair = conflicts[0]
        self.assertIn("sfp_dns", pair)
        self.assertIn("sfp_dns_alt", pair)

    def test_find_conflicts_none(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns"))
        reg.register(self._make_decl("sfp_ssl"))
        self.assertEqual(reg.find_conflicts(["sfp_dns", "sfp_ssl"]), [])

    def test_check_requirements_met(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns", caps=["dns_resolution"]))
        reg.register(self._make_decl("sfp_ssl", reqs=["dns_resolution"]))

        unmet = reg.check_requirements(["sfp_dns", "sfp_ssl"])
        self.assertEqual(len(unmet), 0)

    def test_check_requirements_unmet(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_ssl", reqs=["dns_resolution"]))

        unmet = reg.check_requirements(["sfp_ssl"])
        self.assertIn("sfp_ssl", unmet)
        self.assertIn("dns_resolution", unmet["sfp_ssl"])

    def test_check_requirements_optional_not_flagged(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_ssl", reqs=[("proxy", False)]))

        unmet = reg.check_requirements(["sfp_ssl"])
        self.assertEqual(len(unmet), 0)

    def test_dependency_order(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns", priority=10))
        reg.register(self._make_decl("sfp_ssl", priority=50, reqs=["dns"]))
        reg.register(self._make_decl("sfp_report", priority=90))

        order = reg.get_dependency_order(["sfp_report", "sfp_ssl", "sfp_dns"])
        self.assertEqual(order[0], "sfp_dns")
        self.assertEqual(order[-1], "sfp_report")

    def test_get_all_capabilities(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns", caps=["dns"]))
        reg.register(self._make_decl("sfp_ssl", caps=["ssl", "dns"]))

        all_caps = reg.get_all_capabilities()
        self.assertIn("dns", all_caps)
        self.assertEqual(len(all_caps["dns"]), 2)

    def test_get_all_tags(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns", tags=["passive"]))
        reg.register(self._make_decl("sfp_ssl", tags=["passive", "tls"]))

        tags = reg.get_all_tags()
        self.assertEqual(tags["passive"], 2)
        self.assertEqual(tags["tls"], 1)

    def test_counts(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns", caps=["dns"]))
        reg.register(self._make_decl("sfp_ssl", caps=["ssl"]))
        self.assertEqual(reg.module_count, 2)
        self.assertEqual(reg.capability_count, 2)

    def test_to_dict(self):
        reg = CapabilityRegistry()
        reg.register(self._make_decl("sfp_dns", caps=["dns"]))
        d = reg.to_dict()
        self.assertIn("modules", d)
        self.assertIn("capabilities", d)
        self.assertEqual(d["module_count"], 1)

    def test_thread_safety(self):
        reg = CapabilityRegistry()
        errors = []

        def register_modules(prefix):
            try:
                for i in range(50):
                    name = f"{prefix}_{i}"
                    reg.register(self._make_decl(name, caps=[f"cap_{name}"]))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_modules, args=(f"t{t}",))
            for t in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(reg.module_count, 200)


class TestSingleton(unittest.TestCase):
    def test_get_capability_registry(self):
        r1 = get_capability_registry()
        r2 = get_capability_registry()
        self.assertIs(r1, r2)


if __name__ == "__main__":
    unittest.main()
