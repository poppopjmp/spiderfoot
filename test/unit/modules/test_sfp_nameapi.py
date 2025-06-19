import pytest
import unittest

from modules.sfp_nameapi import sfp_nameapi
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleNameapi(SpiderFootTestBase):
    def test_setup(self):
        """
        Test setup(self, sfc, userOpts=dict())
        """
        module = self.create_module_wrapper(sfp_nameapi)
        module.setup("example.com", self.default_options)
        self.assertTrue(hasattr(module, 'opts'))

    def test_watchedEvents_should_return_list(self):
        """
        Test watchedEvents(self)
        """
        module = self.create_module_wrapper(sfp_nameapi)
        watched_events = module.watchedEvents()
        self.assertIsInstance(watched_events, list)

    def test_producedEvents_should_return_list(self):
        """
        Test producedEvents(self)
        """
        module = self.create_module_wrapper(sfp_nameapi)
        produced_events = module.producedEvents()
        self.assertIsInstance(produced_events, list)

    @safe_recursion(max_depth=5)
    def test_handleEvent_no_api_key_should_set_errorState(self, depth=0):
        sf = SpiderFoot(self.default_options)

        module = sfp_nameapi()
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
        self.assertTrue(module.errorState)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
