"""FK constraint satisfaction test — Cycle 19.

Validates that EVERY event type produced or consumed by all 309 modules
resolves against the canonical DB event catalog (SpiderFootDb.eventDetails).

This test is the CI guardrail that prevents FK violations when modules
emit events whose types aren't registered in tbl_event_types.

Also validates the event catalog itself for structural correctness.
"""
from __future__ import annotations

import unittest

from spiderfoot.sflib.core import SpiderFoot


class TestEventCatalogIntegrity(unittest.TestCase):
    """Validate the event catalog itself."""

    @classmethod
    def setUpClass(cls):
        from spiderfoot.db import SpiderFootDb
        cls.catalog = SpiderFootDb.eventDetails
        cls.valid_events = {e[0] for e in cls.catalog}

    def test_catalog_has_minimum_entries(self):
        """Must have at least 200 event types (v5 had 200+, v6 has 260)."""
        self.assertGreaterEqual(len(self.catalog), 200,
                                f"Only {len(self.catalog)} event types — expected 200+")

    def test_catalog_entries_have_correct_structure(self):
        """Each entry must be a tuple of (name, category, description)."""
        for entry in self.catalog:
            self.assertIsInstance(entry, (list, tuple),
                                 f"Entry is not list/tuple: {entry}")
            self.assertGreaterEqual(len(entry), 3,
                                    f"Entry has <3 fields: {entry}")
            name, category, description = entry[0], entry[1], entry[2]
            self.assertIsInstance(name, str,
                                 f"Event name not str: {name}")
            self.assertTrue(len(name) > 0,
                           f"Empty event name in catalog")

    def test_no_duplicate_event_names(self):
        """Event names must be unique."""
        names = [e[0] for e in self.catalog]
        duplicates = {n for n in names if names.count(n) > 1}
        self.assertEqual(len(duplicates), 0,
                         f"Duplicate event types in catalog: {duplicates}")

    def test_core_event_types_present(self):
        """Essential v5/v6 event types must exist."""
        core_types = [
            "IP_ADDRESS", "IPV6_ADDRESS", "DOMAIN_NAME", "INTERNET_NAME",
            "EMAILADDR", "TCP_PORT_OPEN", "LINKED_URL_INTERNAL",
            "LINKED_URL_EXTERNAL", "SSL_CERTIFICATE_RAW", "SSL_CERTIFICATE_ISSUED",
            "DOMAIN_WHOIS", "DOMAIN_REGISTRAR", "NETBLOCK_OWNER",
            "RAW_RIR_DATA", "RAW_DNS_RECORDS", "HTTP_CODE", "WEBSERVER_BANNER",
            "GEOINFO", "CO_HOSTED_SITE", "VULNERABILITY_GENERAL",
            "HUMAN_NAME", "USERNAME", "PHONE_NUMBER",
        ]
        for evt in core_types:
            self.assertIn(evt, self.valid_events,
                          f"Core event type '{evt}' missing from catalog")


class TestModuleEventsFKSatisfied(unittest.TestCase):
    """Validate all module event types resolve against the DB catalog."""

    @classmethod
    def setUpClass(cls):
        from spiderfoot.db import SpiderFootDb
        cls.valid_events = {e[0] for e in SpiderFootDb.eventDetails}
        # Load all modules
        sf = SpiderFoot({"__modules__": {}, "__logging": False, "_debug": False})
        sf.loadModules()
        cls.modules = sf.opts.get("__modules__", {})

    def test_modules_loaded(self):
        """Sanity: at least 300 modules should load."""
        self.assertGreaterEqual(len(self.modules), 300,
                                f"Only {len(self.modules)} modules loaded")

    def test_all_produced_events_in_catalog(self):
        """Every producedEvents() value must exist in eventDetails."""
        violations = {}
        for mod_name, info in self.modules.items():
            provides = info.get("provides", [])
            for evt in provides:
                if evt not in self.valid_events:
                    violations.setdefault(mod_name, []).append(evt)

        self.assertEqual(len(violations), 0,
                         f"FK violations in producedEvents:\n" +
                         "\n".join(f"  {m}: {evts}" for m, evts in violations.items()))

    def test_all_consumed_events_in_catalog(self):
        """Every watchedEvents() value must exist in eventDetails (except '*')."""
        violations = {}
        for mod_name, info in self.modules.items():
            consumes = info.get("consumes", [])
            for evt in consumes:
                if evt == "*":
                    continue
                if evt not in self.valid_events:
                    violations.setdefault(mod_name, []).append(evt)

        self.assertEqual(len(violations), 0,
                         f"FK violations in watchedEvents:\n" +
                         "\n".join(f"  {m}: {evts}" for m, evts in violations.items()))

    def test_every_module_produces_something(self):
        """Every module must declare at least one produced event."""
        empty = [m for m, info in self.modules.items()
                 if not info.get("provides")]
        # Storage sinks and example modules may not produce events
        excluded = {"sfp__stor_db", "sfp__stor_stdout", "sfp__stor_elasticsearch",
                    "sfp__stor_s3", "sfp__stor_redis", "sfp__stor_jsonl",
                    "sfp_example"}
        non_sink_empty = [m for m in empty if m not in excluded]
        self.assertEqual(len(non_sink_empty), 0,
                         f"Modules with empty producedEvents: {non_sink_empty}")

    def test_every_module_consumes_something(self):
        """Every module must declare at least one watched event."""
        empty = [m for m, info in self.modules.items()
                 if not info.get("consumes")]
        self.assertEqual(len(empty), 0,
                         f"Modules with empty watchedEvents: {empty}")


if __name__ == "__main__":
    unittest.main()
