import pytest
import unittest

from modules.sfp_ethereum import sfp_ethereum
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleEthereum(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_ethereum()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_ethereum()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_ethereum()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_ethereum()
        self.assertIsInstance(module.producedEvents(), list)

    @safe_recursion(max_depth=5)
    def test_handleEvent_event_data_containing_ethereum_string_should_return_event(selfdepth=0):
        sf = SpiderFoot(self.default_options)

        module = sfp_ethereum()
        module.setup(sf, dict())

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            expected = 'ETHEREUM_ADDRESS'
            if str(event.eventType) != expected:
                raise Exception(f"{event.eventType} != {expected}")

            expected = '0x89205A3A3b2A69De6Dbf7f01ED13B2108B2c43e7'
            if str(event.data) != expected:
                raise Exception(f"{event.data} != {expected}")

            raise Exception("OK")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_ethereum)

        event_type = 'ROOT'
        event_data = 'example data 0x89205A3A3b2A69De6Dbf7f01ED13B2108B2c43e7 example data'
        event_module = ''
        source_event = ''

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        with self.assertRaises(Exception) as cm:
            module.handleEvent(evt)

        self.assertEqual("OK", str(cm.exception))

    @safe_recursion(max_depth=5)
    def test_handleEvent_event_data_not_containing_ethereum_string_should_not_return_event(selfdepth=0):
        sf = SpiderFoot(self.default_options)

        module = sfp_ethereum()
        module.setup(sf, dict())

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            raise Exception(f"Raised event {event.eventType}: {event.data}")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_ethereum)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)
        result = module.handleEvent(evt)

        self.assertIsNone(result)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
