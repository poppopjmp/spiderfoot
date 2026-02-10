from __future__ import annotations

"""Tests for sfp_dehashed module."""

import pytest
import unittest
from test.unit.utils.test_module_base import TestModuleBase

from modules.sfp_dehashed import sfp_dehashed
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationDehashed(TestModuleBase):


    def setUp(self):
        """Enhanced setUp with ThreadReaper module tracking."""
        super().setUp()
        # ThreadReaper infrastructure is automatically initialized
        
    def tearDown(self):
        """Enhanced tearDown with ThreadReaper cleanup."""
        # ThreadReaper infrastructure automatically cleans up
        super().tearDown()
    @unittest.skip("todo")
    def test_handleEvent(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_dehashed()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'EMAILADDR'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)
