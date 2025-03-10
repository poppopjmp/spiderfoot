import pytest
import unittest

from modules.sfp_dnsresolve import sfp_dnsresolve
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleDnsresolve(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_dnsresolve()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_dnsresolve()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_dnsresolve()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_dnsresolve()
        self.assertIsInstance(module.producedEvents(), list)
    
    def test_handleEvent_internet_name_should_resolve(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_dnsresolve()
        module.setup(sf, dict())
        
        # Mock the resolveHost method to return controlled test data
        def mock_resolveHost(host, dnsserver):
            return {"4": ["1.2.3.4"], "6": ["2001:db8::1"], "addresses": ["1.2.3.4", "2001:db8::1"]}
        
        module.sf.resolveHost = mock_resolveHost

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_dnsresolve)
        
        event_type = 'INTERNET_NAME'
        event_data = 'www.example.com'
        event_module = 'sfp_dnsbrute'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for specific event types
        event_types = [e.eventType for e in generated_events]
        self.assertIn('IP_ADDRESS', event_types, "IP_ADDRESS event not generated")
        self.assertIn('IPV6_ADDRESS', event_types, "IPV6_ADDRESS event not generated")
        
        # Check IPv4 address value
        for event in generated_events:
            if event.eventType == 'IP_ADDRESS':
                self.assertEqual(event.data, "1.2.3.4")
            elif event.eventType == 'IPV6_ADDRESS':
                self.assertEqual(event.data, "2001:db8::1")
