import pytest
import unittest

from modules.sfp_spur import sfp_spur
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleSpur(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_spur()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_spur()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_spur()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_spur()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_api_key_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_spur()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)
        self.assertTrue(module.errorState)
        
    def test_apiStartsWith(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_spur()
        module.setup(sf, dict())
        
        self.assertEqual(module.apiStartsWith('1.2.3.4'), 'ip')
        self.assertEqual(module.apiStartsWith('example.com'), 'domain')
        self.assertEqual(module.apiStartsWith('http://example.com'), 'url')
        self.assertEqual(module.apiStartsWith('https://example.com'), 'url')
        self.assertEqual(module.apiStartsWith('test@example.com'), 'email')
        self.assertEqual(module.apiStartsWith('not-a-valid-type'), 'domain')  # Default
        
    def test_handleEvent_with_api_key_should_process_domain(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_spur()
        module.setup(sf, dict())
        module.opts['api_key'] = 'test_api_key'  # Set a mock API key
        
        # Mock the query function to return a controlled response
        def mock_query(api_type, identifier):
            return {
                "success": True,
                "message": "OK",
                "results": {
                    "verdict": {
                        "determination": "malicious",
                        "score": 90
                    },
                    "domain": "example.com",
                    "categories": ["phishing", "malware"]
                }
            }
            
        # Replace the query function
        module.query = mock_query

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_spur)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'sfp_dnsresolve'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.errorState = False  # Reset error state
        module.handleEvent(evt)
        
        # Check if the expected events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for malicious info
        found_malicious = False
        for event in generated_events:
            if event.eventType == 'MALICIOUS_INTERNET_NAME':
                found_malicious = True
                break
                
        self.assertTrue(found_malicious, "No MALICIOUS_INTERNET_NAME event was generated")
