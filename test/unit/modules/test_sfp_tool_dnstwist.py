import pytest
import unittest

from modules.sfp_tool_dnstwist import sfp_tool_dnstwist
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleToolDnstwist(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_tool_dnstwist()
        self.assertEqual(len(module.opts), 3)

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_dnstwist()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_dnstwist()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_dnstwist()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_tool_path_configured_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_tool_dnstwist()
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
        
    def test_handleEvent_with_tool_path_should_process_domain(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_tool_dnstwist()
        module.setup(sf, dict())
        module.opts['dnstwist_path'] = '/usr/bin/dnstwist'  # Set a mock tool path
        
        # Mock the helper._sanitise method to control test
        module._sanitise = lambda domain: domain
        
        # Mock the helper.shcmd method to control test output
        def mock_shcmd(cmd):
            return '[{"domain-name": "examp1e.com", "fuzzer": "replacement", "dns-a": "192.168.1.1"}]', None
            
        module.shcmd = mock_shcmd

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_tool_dnstwist)

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

        module.errorState = False  # Reset the error state
        module.handleEvent(evt)
        
        # Check if the expected events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Look for the events
        found_types = [e.eventType for e in generated_events]
        self.assertIn('AFFILIATE_INTERNET_NAME', found_types)
        self.assertIn('AFFILIATE_IPADDR', found_types)
