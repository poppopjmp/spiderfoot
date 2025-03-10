import pytest
import unittest

from modules.sfp_networktools import sfp_networktools
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleNetworktools(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_networktools()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_networktools()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_networktools()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_networktools()
        self.assertIsInstance(module.producedEvents(), list)
        
    def test_handleEvent_ip_address_should_extract_data(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_networktools()
        module.setup(sf, dict())
        
        # Mock the fetchUrl method to return a specific HTML response
        def fetch_url_mock(url, timeout, useragent="SpiderFoot", headers=None):
            return {
                'code': "200",
                'content': """
                <div class="main">
                    <h2>ASN Information</h2>
                    <p>ASN: AS13335</p>
                    <p>ISP: Cloudflare, Inc.</p>
                </div>
                """
            }
        
        # Replace the fetchUrl method with our mock
        module.sf.fetchUrl = fetch_url_mock

        target_value = '1.1.1.1'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_networktools)

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
        
        # Check if any events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Look for the BGP_AS event
        for event in generated_events:
            if event.eventType == 'BGP_AS':
                self.assertIn('13335', event.data)
                return
                
        # If we reach here, we didn't find a BGP_AS event
        self.fail("No BGP_AS event was generated")
