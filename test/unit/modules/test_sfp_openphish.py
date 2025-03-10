import pytest
import unittest

from modules.sfp_openphish import sfp_openphish
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleOpenphish(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_openphish()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_openphish()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_openphish()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_openphish()
        self.assertIsInstance(module.producedEvents(), list)
        
    def test_handleEvent_should_detect_phishing_site(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_openphish()
        module.setup(sf, dict())
        
        # Mock the fetchUrl method to return a specific response
        def fetch_url_mock(url, timeout, useragent="SpiderFoot", headers=None):
            return {
                'code': "200",
                'content': """
                http://malicious-example.com/phishing/page
                http://evil-example.net/fake/login
                http://example.com/legitimate/page
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
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_openphish)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check if the expected event was generated
        self.assertGreater(len(generated_events), 0)
        
        # Verify the MALICIOUS_INTERNET_NAME event
        malicious_events = [e for e in generated_events if e.eventType == 'MALICIOUS_INTERNET_NAME']
        self.assertGreater(len(malicious_events), 0)
        self.assertIn('OpenPhish [', malicious_events[0].data)
