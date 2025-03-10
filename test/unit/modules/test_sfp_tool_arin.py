import pytest
import unittest

from modules.sfp_tool_arin import sfp_tool_arin
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleToolArin(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_tool_arin()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_arin()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_arin()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_arin()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_tool_path_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_tool_arin()
        module.setup(sf, dict())
        
        # Ensure the tool path is empty
        module.opts['arin_path'] = ''

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
        
    def test_handleEvent_with_tool_path_should_process_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_tool_arin()
        module.setup(sf, dict())
        module.opts['arin_path'] = '/usr/bin/arin-tool'  # Mock tool path

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the command execution
        def mock_shcmd(cmd):
            return """
            Organization Name:   Example LLC
            Address:            123 Example St, City, Country
            NetRange:           192.168.0.0 - 192.168.255.255
            CIDR:               192.168.0.0/16
            """, None
            
        module.shcmd = mock_shcmd

        # Track generated events
        generated_events = []
        def notifyListeners_mock(event):
            generated_events.append(event)
            
        module.notifyListeners = notifyListeners_mock.__get__(module, sfp_tool_arin)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'test_module'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)

        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for specific event types
        event_types = [e.eventType for e in generated_events]
        self.assertIn('RAW_RIR_DATA', event_types)
        
        # Check event content
        for event in generated_events:
            if event.eventType == 'RAW_RIR_DATA':
                self.assertIn('Example LLC', event.data)
                self.assertIn('192.168.0.0/16', event.data)
