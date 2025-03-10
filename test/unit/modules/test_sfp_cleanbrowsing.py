import pytest
import unittest

from modules.sfp_cleanbrowsing import sfp_cleanbrowsing
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleCleanbrowsing(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_cleanbrowsing()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_cleanbrowsing()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_cleanbrowsing()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_cleanbrowsing()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_domain_name_event_should_check_blocklist(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_cleanbrowsing()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the queryAddr method to simulate different response types
        def mock_query_addr_blocked(addr, family, filterId):
            return "146.112.61.106"  # CleanBrowsing's block address
            
        def mock_query_addr_not_blocked(addr, family, filterId):
            return "93.184.216.34"  # Example.com's real IP
        
        # Test with domain that is blocked
        module.queryAddr = mock_query_addr_blocked
        
        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_cleanbrowsing)
        
        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check that blocked events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for BLACKLISTED_DOMAIN event
        found_blacklist = False
        for event in generated_events:
            if event.eventType == 'BLACKLISTED_DOMAIN':
                found_blacklist = True
                self.assertIn("CleanBrowsing", event.data)
                
        self.assertTrue(found_blacklist, "BLACKLISTED_DOMAIN event not found when domain is blocked")
        
        # Clear events and test with domain that is not blocked
        generated_events = []
        module.queryAddr = mock_query_addr_not_blocked
        
        # Re-run the event handler with the new mock
        module.handleEvent(evt)
        
        # Check that no blacklist events were generated
        blacklisted_events = [e for e in generated_events if e.eventType == 'BLACKLISTED_DOMAIN']
        self.assertEqual(len(blacklisted_events), 0, "No BLACKLISTED_DOMAIN events should be generated for non-blocked domains")
