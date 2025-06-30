import pytest
import unittest

from modules.sfp_bitcoin import sfp_bitcoin
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleBitcoin(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_bitcoin()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_bitcoin()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_bitcoin()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_bitcoin()
        self.assertIsInstance(module.producedEvents(), list)

    @safe_recursion(max_depth=5)
    def test_handleEvent_event_data_containing_bitcoin_string_in_legacy_base58_format_should_return_event(self, selfdepth=0):
        """
        Test handleEvent(self, event) with event data containing bitcoin string in legacy base58 format should return event
        """
        sf = SpiderFoot(self.default_options)

        module = sfp_bitcoin()
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            expected = 'BITCOIN_ADDRESS'
            if str(event.eventType) != expected:
                raise Exception(f"{event.eventType} != {expected}")

            expected = '1HesYJSP1QqcyPEjnQ9vzBL1wujruNGe7R'
            if str(event.data) != expected:
                raise Exception(f"{event.data} != {expected}")

            raise Exception("OK")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_bitcoin)

        event_type = 'ROOT'
        event_data = 'example data 1HesYJSP1QqcyPEjnQ9vzBL1wujruNGe7R example data'
        event_module = ''
        source_event = ''

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        with self.assertRaises(Exception) as cm:
            module.handleEvent(evt)

        self.assertEqual("OK", str(cm.exception))

    @safe_recursion(max_depth=5)
    def test_handleEvent_event_data_containing_bitcoin_string_in_bech32_format_should_return_event(self, selfdepth=0):
        """
        Test handleEvent(self, event) with event data containing bitcoin string in bech32 format should return event
        """
        sf = SpiderFoot(self.default_options)

        module = sfp_bitcoin()
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            expected = 'BITCOIN_ADDRESS'
            if str(event.eventType) != expected:
                raise Exception(f"{event.eventType} != {expected}")

            expected = 'bc1q4r8h8vqk02gnvlus758qmpk8jmajpy2ld23xtr73a39ps0r9z82qq0qqye'
            if str(event.data) != expected:
                raise Exception(f"{event.data} != {expected}")

            raise Exception("OK")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_bitcoin)

        event_type = 'ROOT'
        event_data = 'example data bc1q4r8h8vqk02gnvlus758qmpk8jmajpy2ld23xtr73a39ps0r9z82qq0qqye example data'
        event_module = ''
        source_event = ''

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        with self.assertRaises(Exception) as cm:
            module.handleEvent(evt)

        self.assertEqual("OK", str(cm.exception))

    @safe_recursion(max_depth=5)
    def test_handleEvent_event_data_not_containing_bitcoin_string_should_not_return_event(self, selfdepth=0):
        """
        Test handleEvent(self, event) with event data not containing bitcoin string should not return event
        """
        sf = SpiderFoot(self.default_options)

        module = sfp_bitcoin()
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            raise Exception(f"Raised event {event.eventType}: {event.data}")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_bitcoin)

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
