import pytest
import unittest

from modules.sfp_sociallinks import sfp_sociallinks
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModuleSociallinks(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_sociallinks()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_sociallinks()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_sociallinks()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_sociallinks()
        self.assertIsInstance(module.producedEvents(), list)

    @safe_recursion(max_depth=5)
    def test_handleEvent_no_api_key_should_set_errorState(selfdepth=0):
        sf = SpiderFoot(self.default_options)

        module = sfp_sociallinks()
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

    def test_searchTelegramChannels(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_sociallinks()
        module.setup(sf, dict())

        query = "test query"
        result = module.searchTelegramChannels(query)
        self.assertIsNotNone(result)

    def test_handleEvent_with_telegram_search(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_sociallinks()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'USERNAME'
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
