import pytest
import unittest

from modules.sfp_bingsharedip import sfp_bingsharedip
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleBingsharedip(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_bingsharedip()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_bingsharedip()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_bingsharedip()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_bingsharedip()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_api_key_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_bingsharedip()
        module.setup(sf, dict())

        target_value = 'example target value'
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

    def test_handleEvent_ip_address_should_return_shared_hosting(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_bingsharedip()
        module.setup(sf, dict())
        
        # Mock the fetchUrl method to return a specific HTML response
        def fetch_url_mock(url, timeout, useragent="SpiderFoot", headers=None):
            return {
                'code': "200",
                'content': """
                <html>
                <body>
                <div id="b_results">
                    <li class="b_algo">
                        <h2><a href="http://shared1.example.com">Shared Site 1</a></h2>
                    </li>
                    <li class="b_algo">
                        <h2><a href="http://shared2.example.com">Shared Site 2</a></h2>
                    </li>
                </div>
                </body>
                </html>
                """
            }
        
        # Replace the fetchUrl method with our mock
        module.sf.fetchUrl = fetch_url_mock

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_bingsharedip)

        event_type = 'IP_ADDRESS'
        event_data = '192.168.1.1'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check if the expected events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for co-hosted sites
        found_cohosted = False
        for event in generated_events:
            if event.eventType == 'CO_HOSTED_SITE':
                found_cohosted = True
                break
                
        self.assertTrue(found_cohosted, "CO_HOSTED_SITE event not generated")
