import pytest
import unittest

from modules.sfp_ipapico import sfp_ipapico
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleIpapico(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_ipapico()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_ipapico()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_ipapico()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_ipapico()
        self.assertIsInstance(module.producedEvents(), list)
    
    def test_handleEvent_ip_address_should_return_geoinfo(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_ipapico()
        module.setup(sf, dict())
        
        # Mock the fetchUrl method to return a specific response
        def fetch_url_mock(url, timeout, useragent="SpiderFoot", headers=None):
            return {
                'code': "200",
                'content': '{"ip":"1.1.1.1","country":"Australia","country_iso":"AU","city":"Research","latitude":-37.7,"longitude":145.1833}'
            }
        
        # Replace the fetchUrl method with our mock
        module.sf.fetchUrl = fetch_url_mock

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

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

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
        
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_ipapico)

        module.handleEvent(evt)
        
        # Check if the expected events were generated
        self.assertEqual(len(generated_events), 4)
        self.assertEqual(generated_events[0].eventType, 'GEOINFO')
        self.assertEqual(generated_events[1].eventType, 'PHYSICAL_COORDINATES')
        self.assertEqual(generated_events[2].eventType, 'PHYSICAL_ADDRESS')
        self.assertEqual(generated_events[3].eventType, 'COUNTRY_NAME')
