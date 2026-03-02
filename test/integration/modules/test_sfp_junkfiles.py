from __future__ import annotations

"""Tests for sfp_junkfiles module."""

import pytest
import unittest

from modules.sfp_junkfiles import sfp_junkfiles
from test.unit.utils.test_module_base import TestModuleBase
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleIntegrationJunkfiles(TestModuleBase):
    """Integration tests for sfp_junkfiles module."""

    @property
    def default_options(self):
        return {
            '__database': ':memory:',
            '__modules__': {},
            '_debug': False,
        }

    def setup_module_instance(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_junkfiles()
        module.setup(sf, dict())
        return sf, module

    def test_meta_is_valid(self):
        """Module meta dict contains required keys."""
        sf, module = self.setup_module_instance()
        meta = module.meta
        self.assertIn('name', meta)
        self.assertIn('summary', meta)
        self.assertIsInstance(meta['name'], str)
        self.assertTrue(len(meta['name']) > 0)

    def test_produced_events_non_empty(self):
        """Module declares at least one produced event type."""
        sf, module = self.setup_module_instance()
        produced = module.producedEvents()
        self.assertIsInstance(produced, list)
        self.assertGreater(len(produced), 0)
        self.assertIn('JUNK_FILE', produced)

    def test_watched_events_non_empty(self):
        """Module declares at least one watched event type."""
        sf, module = self.setup_module_instance()
        watched = module.watchedEvents()
        self.assertIsInstance(watched, list)
        self.assertGreater(len(watched), 0)
        self.assertIn('LINKED_URL_INTERNAL', watched)

    def test_handle_event_returns_none(self):
        """handleEvent should not raise on valid input."""
        sf, module = self.setup_module_instance()
        target = SpiderFootTarget('spiderfoot.net', 'INTERNET_NAME')
        module.setTarget(target)
        evt = SpiderFootEvent(
            'LINKED_URL_INTERNAL',
            'https://spiderfoot.net/test.bak',
            'sfp_spider',
            None,
        )
        evt.actualSource = 'https://spiderfoot.net/'
        result = module.handleEvent(evt)
        self.assertIsNone(result)
