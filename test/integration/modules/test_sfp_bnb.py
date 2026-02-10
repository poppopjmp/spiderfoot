from __future__ import annotations

"""Tests for sfp_bnb module."""

import unittest
from test.unit.utils.test_module_base import TestModuleBase
from modules.sfp_bnb import sfp_bnb
from spiderfoot import SpiderFootEvent

class TestSfpBnbIntegration(TestModuleBase):
    def setUp(self):
        self.plugin = sfp_bnb()
        self.plugin.setup(None, {})

    def test_produced_event_type(self):
        self.assertIn('BNB_ADDRESS', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
