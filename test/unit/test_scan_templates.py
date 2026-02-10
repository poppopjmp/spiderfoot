"""Tests for spiderfoot.scan_templates."""
from __future__ import annotations

import unittest
from spiderfoot.scan_templates import (
    TemplateCategory, ScanTemplate, TemplateRegistry,
)


class TestScanTemplate(unittest.TestCase):
    def test_defaults(self):
        t = ScanTemplate(name="test")
        self.assertEqual(t.name, "test")
        self.assertEqual(t.category, TemplateCategory.CUSTOM)
        self.assertEqual(t.modules, set())

    def test_add_modules(self):
        t = ScanTemplate(name="t")
        t.add_modules("sfp_dns", "sfp_whois")
        self.assertEqual(t.modules, {"sfp_dns", "sfp_whois"})

    def test_exclude_modules(self):
        t = ScanTemplate(name="t")
        t.add_modules("sfp_dns", "sfp_whois", "sfp_bad")
        t.exclude_modules("sfp_bad")
        self.assertEqual(t.get_effective_modules(), {"sfp_dns", "sfp_whois"})

    def test_add_event_types(self):
        t = ScanTemplate(name="t")
        t.add_event_types("IP_ADDRESS", "DOMAIN_NAME")
        self.assertEqual(t.event_types, {"IP_ADDRESS", "DOMAIN_NAME"})

    def test_set_option(self):
        t = ScanTemplate(name="t")
        t.set_option("max_depth", 3)
        self.assertEqual(t.options["max_depth"], 3)

    def test_chaining(self):
        t = ScanTemplate(name="t")
        result = t.add_modules("a").exclude_modules("b").set_option("k", 1)
        self.assertIs(result, t)

    def test_clone(self):
        t = ScanTemplate(name="orig", modules={"sfp_dns"})
        c = t.clone("copy")
        self.assertEqual(c.name, "copy")
        self.assertEqual(c.modules, {"sfp_dns"})
        c.add_modules("sfp_new")
        self.assertNotIn("sfp_new", t.modules)

    def test_to_dict(self):
        t = ScanTemplate(name="t", category=TemplateCategory.VULNERABILITY, tags={"a"})
        d = t.to_dict()
        self.assertEqual(d["name"], "t")
        self.assertEqual(d["category"], "vulnerability")
        self.assertEqual(d["tags"], ["a"])

    def test_from_dict(self):
        data = {
            "name": "test",
            "category": "threat_intel",
            "modules": ["sfp_dns", "sfp_whois"],
            "tags": ["osint"],
        }
        t = ScanTemplate.from_dict(data)
        self.assertEqual(t.name, "test")
        self.assertEqual(t.category, TemplateCategory.THREAT_INTEL)
        self.assertEqual(t.modules, {"sfp_dns", "sfp_whois"})

    def test_from_dict_defaults(self):
        t = ScanTemplate.from_dict({"name": "minimal"})
        self.assertEqual(t.category, TemplateCategory.CUSTOM)

    def test_roundtrip(self):
        t = ScanTemplate(name="rt", modules={"m1"}, tags={"tag1"})
        t2 = ScanTemplate.from_dict(t.to_dict())
        self.assertEqual(t2.name, "rt")
        self.assertEqual(t2.modules, {"m1"})


class TestTemplateRegistry(unittest.TestCase):
    def test_defaults_loaded(self):
        reg = TemplateRegistry()
        templates = reg.list_templates()
        self.assertIn("passive_recon", templates)
        self.assertIn("full_scan", templates)
        self.assertIn("vulnerability_scan", templates)
        self.assertIn("threat_intel", templates)
        self.assertIn("identity_search", templates)

    def test_get(self):
        reg = TemplateRegistry()
        t = reg.get("passive_recon")
        self.assertIsNotNone(t)
        self.assertEqual(t.category, TemplateCategory.RECONNAISSANCE)

    def test_get_missing(self):
        reg = TemplateRegistry()
        self.assertIsNone(reg.get("nonexistent"))

    def test_register(self):
        reg = TemplateRegistry()
        custom = ScanTemplate(name="custom")
        reg.register(custom)
        self.assertIsNotNone(reg.get("custom"))

    def test_unregister(self):
        reg = TemplateRegistry()
        self.assertTrue(reg.unregister("passive_recon"))
        self.assertFalse(reg.unregister("passive_recon"))

    def test_get_by_category(self):
        reg = TemplateRegistry()
        recon = reg.get_by_category(TemplateCategory.RECONNAISSANCE)
        names = {t.name for t in recon}
        self.assertIn("passive_recon", names)

    def test_search(self):
        reg = TemplateRegistry()
        results = reg.search("threat")
        names = {t.name for t in results}
        self.assertIn("threat_intel", names)

    def test_search_by_tag(self):
        reg = TemplateRegistry()
        results = reg.search("passive")
        names = {t.name for t in results}
        self.assertIn("passive_recon", names)

    def test_summary(self):
        reg = TemplateRegistry()
        s = reg.summary()
        self.assertEqual(s["total"], 5)
        self.assertIn("reconnaissance", s["categories"])

    def test_to_dict(self):
        reg = TemplateRegistry()
        d = reg.to_dict()
        self.assertIn("passive_recon", d)

    def test_empty_registry(self):
        reg = TemplateRegistry(load_defaults=False)
        self.assertEqual(reg.list_templates(), [])


if __name__ == "__main__":
    unittest.main()
