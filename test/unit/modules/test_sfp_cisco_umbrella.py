import pytest
import unittest

from modules.sfp_cisco_umbrella import sfp_cisco_umbrella
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleCiscoUmbrella(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_cisco_umbrella()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_cisco_umbrella()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_cisco_umbrella()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_cisco_umbrella()
        self.assertIsInstance(module.producedEvents(), list)

    def test_parseApiResponse_should_handle_json_data(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_cisco_umbrella()
        module.setup(sf, dict())

        api_response = {
            'code': 200,
            'content': '{"rankings": [{"rank": 123, "domain": "example.com"}]}'
        }

        result = module.parseApiResponse(api_response)
        self.assertIsInstance(result, dict)
        self.assertIn('rankings', result)

    def test_parseApiResponse_should_handle_errors(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_cisco_umbrella()
        module.setup(sf, dict())

        # Test with invalid JSON
        api_response = {
            'code': 200,
            'content': 'not json'
        }

        result = module.parseApiResponse(api_response)
        self.assertIsNone(result)

        # Test with error code
        api_response = {
            'code': 404,
            'content': '{"error": "Not found"}'
        }

        result = module.parseApiResponse(api_response)
        self.assertIsNone(result)

    def test_handleEvent_should_process_domain_data(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_cisco_umbrella()
        module.setup(sf, dict())
        
        # Mock fetchUrl to return sample data
        def fetch_url_mock(url, *args, **kwargs):
            return {
                'code': 200,
                'content': '{"rankings": [{"rank": 123, "domain": "example.com"}]}'
            }
            
        module.sf.fetchUrl = fetch_url_mock

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_cisco_umbrella)
        
        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for specific event types
        event_types = [e.eventType for e in generated_events]
        self.assertIn('RAW_RIR_DATA', event_types)
        self.assertIn('DOMAIN_POPULARITY_RANK', event_types)
