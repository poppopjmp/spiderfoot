import pytest
import unittest

from modules.sfp_namechk import sfp_namechk
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleNamechk(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_namechk()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_namechk()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_namechk()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_namechk()
        self.assertIsInstance(module.producedEvents(), list)
        
    def test_handleEvent_username_event_should_return_social_media(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_namechk()
        module.setup(sf, dict())
        
        # Mock the check_username function
        module.check_username = lambda username: [{'site_url': 'https://test-service.com/username', 'site_name': 'Test Service'}]

        target_value = 'testuser'
        target_type = 'USERNAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_namechk)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'USERNAME'
        event_data = 'testuser'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check if the expected event was generated
        self.assertEqual(len(generated_events), 1)
        self.assertEqual(generated_events[0].eventType, 'SOCIAL_MEDIA')
        self.assertEqual(generated_events[0].data, "Test Service: testuser")
        self.assertEqual(generated_events[0].moduleDataSource, "https://test-service.com/username")
