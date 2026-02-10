"""Tests for spiderfoot.event_registry."""
from __future__ import annotations

import unittest

from spiderfoot.event_registry import (
    EventTypeMeta,
    EventTypeRegistry,
    ModuleNode,
    get_event_registry,
)


SAMPLE_EVENT_DETAILS = [
    ['ROOT', 'Internal SpiderFoot Root event', 1, 'INTERNAL'],
    ['IP_ADDRESS', 'IP Address', 0, 'ENTITY'],
    ['INTERNET_NAME', 'Internet Name', 0, 'ENTITY'],
    ['DOMAIN_NAME', 'Domain Name', 0, 'ENTITY'],
    ['EMAILADDR', 'Email Address', 0, 'ENTITY'],
    ['MALICIOUS_IPADDR', 'Malicious IP Address', 0, 'DESCRIPTOR'],
    ['TARGET_WEB_CONTENT', 'Web Content', 1, 'DATA'],
    ['TCP_PORT_OPEN', 'Open TCP Port', 0, 'SUBENTITY'],
]


class TestEventTypeMeta(unittest.TestCase):
    """Tests for EventTypeMeta."""

    def test_entity(self):
        m = EventTypeMeta("IP_ADDRESS", "IP Address", False, "ENTITY")
        self.assertTrue(m.is_entity)
        self.assertFalse(m.is_descriptor)
        self.assertFalse(m.is_data)

    def test_descriptor(self):
        m = EventTypeMeta("MALICIOUS_IPADDR", "Malicious", False, "DESCRIPTOR")
        self.assertTrue(m.is_descriptor)
        self.assertFalse(m.is_entity)

    def test_data(self):
        m = EventTypeMeta("TARGET_WEB_CONTENT", "Content", True, "DATA")
        self.assertTrue(m.is_data)
        self.assertTrue(m.is_raw)

    def test_subentity(self):
        m = EventTypeMeta("TCP_PORT_OPEN", "Port", False, "SUBENTITY")
        self.assertTrue(m.is_subentity)

    def test_internal(self):
        m = EventTypeMeta("ROOT", "Root", True, "INTERNAL")
        self.assertTrue(m.is_internal)

    def test_frozen(self):
        m = EventTypeMeta("IP_ADDRESS", "IP", False, "ENTITY")
        with self.assertRaises(AttributeError):
            m.event_type = "CHANGED"


class TestEventTypeRegistry(unittest.TestCase):
    """Tests for EventTypeRegistry."""

    def setUp(self):
        self.registry = EventTypeRegistry()

    def test_register_and_get(self):
        self.registry.register("IP_ADDRESS", "IP Address", False, "ENTITY")
        meta = self.registry.get("IP_ADDRESS")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.event_type, "IP_ADDRESS")
        self.assertEqual(meta.description, "IP Address")
        self.assertEqual(meta.category, "ENTITY")

    def test_is_valid(self):
        self.registry.register("IP_ADDRESS", "IP Address")
        self.assertTrue(self.registry.is_valid("IP_ADDRESS"))
        self.assertFalse(self.registry.is_valid("NONEXISTENT"))

    def test_contains(self):
        self.registry.register("IP_ADDRESS", "IP Address")
        self.assertIn("IP_ADDRESS", self.registry)
        self.assertNotIn("NONEXISTENT", self.registry)

    def test_len(self):
        self.assertEqual(len(self.registry), 0)
        self.registry.register("IP_ADDRESS", "IP Address")
        self.assertEqual(len(self.registry), 1)

    def test_all_types(self):
        self.registry.load_from_list(SAMPLE_EVENT_DETAILS)
        types = self.registry.all_types()
        self.assertIn("IP_ADDRESS", types)
        self.assertIn("ROOT", types)
        self.assertEqual(types, sorted(types))

    def test_by_category(self):
        self.registry.load_from_list(SAMPLE_EVENT_DETAILS)
        entities = self.registry.by_category("ENTITY")
        self.assertIn("IP_ADDRESS", entities)
        self.assertIn("INTERNET_NAME", entities)
        self.assertNotIn("MALICIOUS_IPADDR", entities)

    def test_categories(self):
        self.registry.load_from_list(SAMPLE_EVENT_DETAILS)
        cats = self.registry.categories
        self.assertIn("ENTITY", cats)
        self.assertIn("DESCRIPTOR", cats)
        self.assertIn("DATA", cats)
        self.assertIn("INTERNAL", cats)

    def test_load_from_list(self):
        count = self.registry.load_from_list(SAMPLE_EVENT_DETAILS)
        self.assertEqual(count, len(SAMPLE_EVENT_DETAILS))
        self.assertEqual(len(self.registry), len(SAMPLE_EVENT_DETAILS))

    def test_load_from_db_class(self):
        count = self.registry.load_from_db_class()
        # Should load 100+ event types from SpiderFootDb
        self.assertGreater(count, 100)
        self.assertTrue(self.registry.is_valid("IP_ADDRESS"))
        self.assertTrue(self.registry.is_valid("INTERNET_NAME"))
        self.assertTrue(self.registry.is_valid("ROOT"))

    def test_validate_module_events_valid(self):
        self.registry.load_from_list(SAMPLE_EVENT_DETAILS)
        warnings = self.registry.validate_module_events(
            "sfp_dns",
            ["INTERNET_NAME", "DOMAIN_NAME"],
            ["IP_ADDRESS"],
        )
        self.assertEqual(warnings, [])

    def test_validate_module_events_unknown(self):
        self.registry.load_from_list(SAMPLE_EVENT_DETAILS)
        warnings = self.registry.validate_module_events(
            "sfp_bad",
            ["FAKE_WATCHED"],
            ["FAKE_PRODUCED"],
        )
        self.assertEqual(len(warnings), 2)
        self.assertIn("FAKE_WATCHED", warnings[0])
        self.assertIn("FAKE_PRODUCED", warnings[1])

    def test_validate_wildcard_watch(self):
        self.registry.load_from_list(SAMPLE_EVENT_DETAILS)
        warnings = self.registry.validate_module_events(
            "sfp_all", ["*"], ["IP_ADDRESS"]
        )
        self.assertEqual(warnings, [])

    def test_to_dict(self):
        self.registry.load_from_list(SAMPLE_EVENT_DETAILS)
        d = self.registry.to_dict()
        self.assertEqual(d["total_types"], len(SAMPLE_EVENT_DETAILS))
        self.assertIn("categories", d)
        self.assertIn("types", d)
        self.assertIn("IP_ADDRESS", d["types"])


class TestModuleGraph(unittest.TestCase):
    """Tests for module graph operations."""

    def setUp(self):
        self.registry = EventTypeRegistry()
        self.registry.load_from_list(SAMPLE_EVENT_DETAILS)

        self.modules = {
            "sfp_dns": {
                "watchedEvents": ["INTERNET_NAME", "DOMAIN_NAME"],
                "producedEvents": ["IP_ADDRESS"],
            },
            "sfp_spider": {
                "watchedEvents": ["INTERNET_NAME"],
                "producedEvents": ["INTERNET_NAME", "EMAILADDR", "TARGET_WEB_CONTENT"],
            },
            "sfp_portscan": {
                "watchedEvents": ["IP_ADDRESS"],
                "producedEvents": ["TCP_PORT_OPEN"],
            },
            "sfp_malicious": {
                "watchedEvents": ["IP_ADDRESS"],
                "producedEvents": ["MALICIOUS_IPADDR"],
            },
            "sfp_all": {
                "watchedEvents": ["*"],
                "producedEvents": ["ROOT"],
            },
        }

    def test_build_module_graph(self):
        graph = self.registry.build_module_graph(self.modules)
        self.assertEqual(len(graph), 5)
        self.assertIn("sfp_dns", graph)
        node = graph["sfp_dns"]
        self.assertIsInstance(node, ModuleNode)
        self.assertIn("IP_ADDRESS", node.produces)
        self.assertIn("INTERNET_NAME", node.watches)

    def test_find_producers(self):
        graph = self.registry.build_module_graph(self.modules)
        producers = self.registry.find_producers("IP_ADDRESS", graph)
        self.assertIn("sfp_dns", producers)
        self.assertNotIn("sfp_portscan", producers)

    def test_find_consumers(self):
        graph = self.registry.build_module_graph(self.modules)
        consumers = self.registry.find_consumers("IP_ADDRESS", graph)
        self.assertIn("sfp_portscan", consumers)
        self.assertIn("sfp_malicious", consumers)
        self.assertIn("sfp_all", consumers)  # wildcard watcher

    def test_find_orphaned_types(self):
        graph = self.registry.build_module_graph(self.modules)
        orphaned = self.registry.find_orphaned_types(graph)
        # DOMAIN_NAME is in registry but no module produces it in our test set
        self.assertIn("DOMAIN_NAME", orphaned)

    def test_find_unregistered_types(self):
        # Add a module that uses an unregistered type
        modules = {
            "sfp_custom": {
                "watchedEvents": ["CUSTOM_EVENT"],
                "producedEvents": ["ANOTHER_CUSTOM"],
            },
        }
        graph = self.registry.build_module_graph(modules)
        unreg = self.registry.find_unregistered_types(graph)
        self.assertIn("CUSTOM_EVENT", unreg)
        self.assertIn("ANOTHER_CUSTOM", unreg)

    def test_get_dependency_chain(self):
        graph = self.registry.build_module_graph(self.modules)
        chains = self.registry.get_dependency_chain("TCP_PORT_OPEN", graph)
        # Should find: sfp_portscan -> (watches IP_ADDRESS) -> sfp_dns
        self.assertTrue(len(chains) > 0)
        # First chain starts with the producer
        self.assertEqual(chains[0][0], "sfp_portscan")

    def test_dependency_chain_max_depth(self):
        graph = self.registry.build_module_graph(self.modules)
        chains = self.registry.get_dependency_chain(
            "TCP_PORT_OPEN", graph, max_depth=1
        )
        # With max_depth=1, only direct producer is found
        self.assertTrue(all(len(c) <= 1 for c in chains))

    def test_alternative_keys(self):
        """Test that 'provides'/'consumes' keys also work."""
        modules = {
            "sfp_test": {
                "provides": ["IP_ADDRESS"],
                "consumes": ["INTERNET_NAME"],
            },
        }
        graph = self.registry.build_module_graph(modules)
        node = graph["sfp_test"]
        self.assertIn("IP_ADDRESS", node.produces)
        self.assertIn("INTERNET_NAME", node.watches)


class TestSingleton(unittest.TestCase):
    """Test singleton behavior."""

    def test_get_event_registry(self):
        r1 = get_event_registry()
        r2 = get_event_registry()
        self.assertIs(r1, r2)
        self.assertIsInstance(r1, EventTypeRegistry)


if __name__ == "__main__":
    unittest.main()
