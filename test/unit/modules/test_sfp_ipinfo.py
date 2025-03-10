import pytest
import unittest

from modules.sfp_ipinfo import sfp_ipinfo
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleIpinfo(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_ipinfo()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_ipinfo()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_ipinfo()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_ipinfo()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_with_api_key_and_valid_response_should_generate_events(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_ipinfo()
        module.setup(sf, dict())
        # Set an API key
        module.opts['api_key'] = 'test_api_key'

        target_value = '1.1.1.1'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock API response
        def fetchUrl_mock(url, *args, **kwargs):
            return {
                'code': 200,
                'content': '{"ip": "1.1.1.1", "hostname": "one.one.one.one", "city": "Los Angeles", "region": "California", "country": "US", "loc": "34.0522,-118.2437", "org": "AS13335 Cloudflare, Inc.", "postal": "90001", "timezone": "America/Los_Angeles"}'
            }
        
        module.sf.fetchUrl = fetchUrl_mock

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_ipinfo)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'IP_ADDRESS'
        event_data = '1.1.1.1'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check the events generated
        self.assertGreater(len(generated_events), 0)
        
        # Check specific events we expect to be generated
        event_types = [e.eventType for e in generated_events]
        self.assertIn('GEOINFO', event_types)
        self.assertIn('PHYSICAL_COORDINATES', event_types)
        self.assertIn('PROVIDER_HOSTING', event_types)
        self.assertIn('RAW_RIR_DATA', event_types)
        self.assertIn('INTERNET_NAME', event_types)

    def test_handleEvent_no_api_key_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_ipinfo()
        module.setup(sf, dict())

        target_value = '1.1.1.1'
        target_type = 'IP_ADDRESS'
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
