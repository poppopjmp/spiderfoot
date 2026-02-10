"""Tests for spiderfoot.event_taxonomy."""
from __future__ import annotations

import unittest
from spiderfoot.event_taxonomy import (
    EventCategory, RiskLevel, EventTypeInfo, EventTaxonomy,
)


class TestEventCategory(unittest.TestCase):
    def test_values(self):
        self.assertEqual(EventCategory.NETWORK.value, "network")
        self.assertEqual(EventCategory.VULNERABILITY.value, "vulnerability")

class TestRiskLevel(unittest.TestCase):
    def test_values(self):
        self.assertEqual(RiskLevel.CRITICAL.value, "critical")
        self.assertEqual(RiskLevel.NONE.value, "none")


class TestEventTypeInfo(unittest.TestCase):
    def test_defaults(self):
        info = EventTypeInfo(name="TEST_TYPE")
        self.assertEqual(info.category, EventCategory.OTHER)
        self.assertEqual(info.risk_level, RiskLevel.INFO)
        self.assertFalse(info.is_raw)

    def test_to_dict(self):
        info = EventTypeInfo(
            name="IP_ADDRESS",
            description="An IP",
            category=EventCategory.NETWORK,
            risk_level=RiskLevel.INFO,
            related_types={"NETBLOCK_MEMBER"},
            tags={"osint"},
        )
        d = info.to_dict()
        self.assertEqual(d["name"], "IP_ADDRESS")
        self.assertEqual(d["category"], "network")
        self.assertEqual(d["related_types"], ["NETBLOCK_MEMBER"])
        self.assertEqual(d["tags"], ["osint"])

    def test_parent_type(self):
        info = EventTypeInfo(name="IPV6_ADDRESS", parent_type="IP_ADDRESS")
        self.assertEqual(info.parent_type, "IP_ADDRESS")


class TestEventTaxonomy(unittest.TestCase):
    def setUp(self):
        self.tax = EventTaxonomy()

    def test_defaults_loaded(self):
        self.assertTrue(len(self.tax.all_types) > 0)
        self.assertIn("IP_ADDRESS", self.tax.all_types)

    def test_get(self):
        info = self.tax.get("IP_ADDRESS")
        self.assertIsNotNone(info)
        self.assertEqual(info.category, EventCategory.NETWORK)

    def test_get_missing(self):
        self.assertIsNone(self.tax.get("NONEXISTENT"))

    def test_exists(self):
        self.assertTrue(self.tax.exists("IP_ADDRESS"))
        self.assertFalse(self.tax.exists("FOOBAR"))

    def test_get_category(self):
        self.assertEqual(self.tax.get_category("IP_ADDRESS"), EventCategory.NETWORK)
        self.assertIsNone(self.tax.get_category("NOPE"))

    def test_get_risk(self):
        self.assertEqual(self.tax.get_risk("VULNERABILITY_CVE_CRITICAL"), RiskLevel.CRITICAL)
        self.assertIsNone(self.tax.get_risk("NOPE"))

    def test_get_by_category(self):
        network_types = self.tax.get_by_category(EventCategory.NETWORK)
        self.assertTrue(len(network_types) > 0)
        names = {t.name for t in network_types}
        self.assertIn("IP_ADDRESS", names)

    def test_get_by_risk(self):
        critical = self.tax.get_by_risk(RiskLevel.CRITICAL)
        names = {t.name for t in critical}
        self.assertIn("VULNERABILITY_CVE_CRITICAL", names)

    def test_get_children(self):
        children = self.tax.get_children("IP_ADDRESS")
        names = {t.name for t in children}
        self.assertIn("IPV6_ADDRESS", names)

    def test_get_ancestors(self):
        ancestors = self.tax.get_ancestors("IPV6_ADDRESS")
        self.assertIn("IP_ADDRESS", ancestors)

    def test_get_ancestors_no_parent(self):
        ancestors = self.tax.get_ancestors("IP_ADDRESS")
        self.assertEqual(ancestors, [])

    def test_is_descendant(self):
        self.assertTrue(self.tax.is_descendant("IPV6_ADDRESS", "IP_ADDRESS"))
        self.assertFalse(self.tax.is_descendant("IP_ADDRESS", "IPV6_ADDRESS"))

    def test_register(self):
        info = EventTypeInfo(name="CUSTOM_TYPE", description="Custom", category=EventCategory.OTHER)
        self.tax.register(info)
        self.assertTrue(self.tax.exists("CUSTOM_TYPE"))
        self.assertEqual(self.tax.get("CUSTOM_TYPE").description, "Custom")

    def test_register_chaining(self):
        result = self.tax.register(EventTypeInfo(name="A"))
        self.assertIs(result, self.tax)

    def test_unregister(self):
        self.assertTrue(self.tax.unregister("IP_ADDRESS"))
        self.assertFalse(self.tax.exists("IP_ADDRESS"))

    def test_unregister_missing(self):
        self.assertFalse(self.tax.unregister("NONEXISTENT"))

    def test_validate_type(self):
        self.assertTrue(self.tax.validate_type("DOMAIN_NAME"))
        self.assertFalse(self.tax.validate_type("BOGUS"))

    def test_categories(self):
        cats = self.tax.categories
        self.assertIn("network", cats)
        self.assertTrue(cats["network"] > 0)

    def test_risk_distribution(self):
        dist = self.tax.risk_distribution
        self.assertIn("info", dist)
        self.assertIn("critical", dist)

    def test_search(self):
        results = self.tax.search("email")
        names = {t.name for t in results}
        self.assertIn("EMAILADDR", names)

    def test_search_case_insensitive(self):
        results = self.tax.search("EMAIL")
        self.assertTrue(len(results) > 0)

    def test_search_no_results(self):
        results = self.tax.search("zzzznonexistent")
        self.assertEqual(results, [])

    def test_summary(self):
        s = self.tax.summary()
        self.assertIn("total_types", s)
        self.assertTrue(s["total_types"] > 0)

    def test_to_dict(self):
        d = self.tax.to_dict()
        self.assertIn("IP_ADDRESS", d)
        self.assertEqual(d["IP_ADDRESS"]["category"], "network")

    def test_empty_taxonomy(self):
        tax = EventTaxonomy(load_defaults=False)
        self.assertEqual(len(tax.all_types), 0)

    def test_parent_chain(self):
        """Multi-level parent chain."""
        tax = EventTaxonomy(load_defaults=False)
        tax.register(EventTypeInfo(name="A"))
        tax.register(EventTypeInfo(name="B", parent_type="A"))
        tax.register(EventTypeInfo(name="C", parent_type="B"))
        ancestors = tax.get_ancestors("C")
        self.assertEqual(ancestors, ["B", "A"])
        self.assertTrue(tax.is_descendant("C", "A"))

    def test_raw_event_types(self):
        info = self.tax.get("SSL_CERTIFICATE_RAW")
        self.assertTrue(info.is_raw)


if __name__ == "__main__":
    unittest.main()
