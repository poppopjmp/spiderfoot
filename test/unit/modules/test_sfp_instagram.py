from __future__ import annotations

"""Tests for sfp_instagram module."""

import unittest
from test.unit.utils.test_module_base import TestModuleBase
from spiderfoot import SpiderFootEvent
from modules.sfp_instagram import sfp_instagram

class TestSfpInstagram(TestModuleBase):
    def setUp(self):
        self.plugin = sfp_instagram()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('access_token', self.plugin.opts)
        self.assertIn('usernames', self.plugin.opts)
        self.assertIn('max_items', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('INSTAGRAM_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
