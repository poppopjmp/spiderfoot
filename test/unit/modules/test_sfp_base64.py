import pytest
import unittest

from modules.sfp_base64 import sfp_base64
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleBase64(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_base64()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_base64()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_base64()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_base64()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_event_data_containing_base64_should_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_base64()
        module.setup(sf, dict())

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
        
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_base64)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        # Base64 for "test message"
        event_type = 'TARGET_WEB_CONTENT'
        event_data = 'This string contains some base64: dGVzdCBtZXNzYWdl and should be decoded'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check if the expected event was generated
        self.assertEqual(len(generated_events), 1)
        self.assertEqual(generated_events[0].eventType, 'BASE64_DATA')
        self.assertEqual(generated_events[0].data, "test message")

    def test_handleEvent_event_data_not_containing_base64_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_base64()
        module.setup(sf, dict())

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
        
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_base64)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'TARGET_WEB_CONTENT'
        event_data = 'This string contains no valid base64 data'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check that no events were generated
        self.assertEqual(len(generated_events), 0)
