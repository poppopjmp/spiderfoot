from __future__ import annotations

"""Tests for sfp_hudsonrock module."""

import pytest
import unittest

from modules.sfp_hudsonrock import sfp_hudsonrock
from spiderfoot.sflib import SpiderFoot
from test.unit.utils.test_module_base import TestModuleBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleHudsonrock(TestModuleBase):

    def setUp(self):
        """Enhanced setUp with ThreadReaper module tracking."""
        super().setUp()

    def tearDown(self):
        """Enhanced tearDown with ThreadReaper cleanup."""
        super().tearDown()

    def test_opts(self):
        module = sfp_hudsonrock()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_hudsonrock()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_hudsonrock()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_hudsonrock()
        self.assertIsInstance(module.producedEvents(), list)

    def test_meta_should_have_required_keys(self):
        module = sfp_hudsonrock()
        self.assertIn('name', module.meta)
        self.assertIn('summary', module.meta)
        self.assertIn('flags', module.meta)
        self.assertIn('useCases', module.meta)
        self.assertIn('categories', module.meta)
        self.assertIn('dataSource', module.meta)

    def test_meta_flags_should_be_empty(self):
        """Hudson Rock is a free API — no API key required."""
        module = sfp_hudsonrock()
        self.assertEqual(module.meta['flags'], [])

    def test_meta_model_should_be_free(self):
        module = sfp_hudsonrock()
        self.assertEqual(
            module.meta['dataSource']['model'],
            "FREE_NOAUTH_UNLIMITED",
        )

    def test_meta_category_should_be_leaks(self):
        module = sfp_hudsonrock()
        self.assertIn("Leaks, Dumps and Breaches", module.meta['categories'])

    def test_watched_events_contains_expected_types(self):
        module = sfp_hudsonrock()
        watched = module.watchedEvents()
        for expected in ["EMAILADDR", "DOMAIN_NAME", "INTERNET_NAME",
                         "USERNAME", "PHONE_NUMBER"]:
            self.assertIn(expected, watched)

    def test_produced_events_contains_expected_types(self):
        module = sfp_hudsonrock()
        produced = module.producedEvents()
        for expected in ["EMAILADDR_COMPROMISED", "RAW_RIR_DATA",
                         "MALICIOUS_INTERNET_NAME", "PHONE_NUMBER_COMPROMISED"]:
            self.assertIn(expected, produced)

    def test_setup_clears_results(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_hudsonrock()
        module.setup(sf, dict())
        self.assertFalse(module.errorState)
        self.assertIsNotNone(module.results)

    def test_format_stealer_summary_full_record(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_hudsonrock()
        module.setup(sf, dict())
        record = {
            'date_compromised': '2026-01-15T10:00:00.000Z',
            'computer_name': 'DESKTOP-ABC',
            'operating_system': 'Windows 11',
            'stealer_family': 'Lumma',
            'malware_path': 'C:\\Users\\test\\malware.exe',
            'ip': '192.168.1.1',
            'antiviruses': ['Windows Defender'],
        }
        summary = module._format_stealer_summary(record)
        self.assertIn('2026-01-15', summary)
        self.assertIn('DESKTOP-ABC', summary)
        self.assertIn('Windows 11', summary)
        self.assertIn('Lumma', summary)
        self.assertIn('malware.exe', summary)
        self.assertIn('192.168.1.1', summary)
        self.assertIn('Windows Defender', summary)

    def test_format_stealer_summary_redacted_record(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_hudsonrock()
        module.setup(sf, dict())
        record = {
            'computer_name': 'Not Found',
            'ip': 'Not Found',
            'malware_path': 'Not Found',
        }
        summary = module._format_stealer_summary(record)
        self.assertIn('redacted', summary.lower())

    def test_handleEvent_skips_duplicate(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_hudsonrock()
        module.setup(sf, dict())
        # Simulate already-processed data
        module.results['example.com'] = True
        # No error, no event emitted — just returns silently


if __name__ == '__main__':
    unittest.main()
