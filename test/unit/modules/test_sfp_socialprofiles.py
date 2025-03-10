import pytest
import unittest

from modules.sfp_socialprofiles import sfp_socialprofiles
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleSocialprofiles(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_socialprofiles()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_socialprofiles()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_socialprofiles()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_socialprofiles()
        self.assertIsInstance(module.producedEvents(), list)
    
    def test_handleEvent_username_event_should_extract_social_media(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_socialprofiles()
        module.setup(sf, dict())
        
        # Mock the fetchUrl method to return a specific response
        def fetch_url_mock(url, *args, **kwargs):
            if "twitter.com/testuser" in url:
                return {
                    'code': "200",
                    'content': "<html><head><title>Test User (@testuser) / Twitter</title></head><body></body></html>"
                }
            return {
                'code': "404",
                'content': "Not found"
            }
        
        # Replace the fetchUrl method with our mock
        module.sf.fetchUrl = fetch_url_mock

        target_value = 'testuser'
        target_type = 'USERNAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_socialprofiles)

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
        
        # Check if any events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Look for the SOCIAL_MEDIA event
        found_social_media = False
        for event in generated_events:
            if event.eventType == 'SOCIAL_MEDIA':
                if 'Twitter:' in event.data:
                    found_social_media = True
                    break
        
        self.assertTrue(found_social_media, "No Twitter SOCIAL_MEDIA event was generated")
