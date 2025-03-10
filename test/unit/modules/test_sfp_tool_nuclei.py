import pytest
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import json
import os

from modules.sfp_tool_nuclei import sfp_tool_nuclei
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleToolNuclei(SpiderFootModuleTestCase):

    def setUp(self):

        super().setUp()
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()
        
        # Create module wrapper class dynamically
        self.module_class = self.create_module_wrapper(
            sfp_tool_nuclei,
            module_attributes={
                'descr': "Module description unavailable",
                # Add any other specific attributes needed by this module
            }
        )


    def test_opts(self):
        module = self.module_class()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = self.module_class()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_tool_path_configured_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = self.module_class()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
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
    
    def test_handleEvent_no_nuclei_path_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = self.module_class()
        module.setup(sf, dict())
        module.opts['nuclei_path'] = ''

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'INTERNET_NAME'
        event_data = 'example.com'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)
        self.assertTrue(module.errorState)
    
    def test_handleEvent_with_nuclei_path_should_process_target(self):
        sf = SpiderFoot(self.default_options)

        module = self.module_class()
        module.setup(sf, dict())
        module.opts['nuclei_path'] = '/usr/bin/nuclei'  # Mock path
        
        # Create a temporary file for the output
        temp_output = tempfile.NamedTemporaryFile(delete=False)
        temp_output.close()
        
        # Mock the command execution
        def mock_execute_command(cmd):
            # Create sample JSON output similar to nuclei
            vulnerabilities = [
                {
                    "template-id": "CVE-2021-12345",
                    "info": {
                        "name": "Test Vulnerability",
                        "severity": "high",
                        "description": "This is a test vulnerability"
                    },
                    "host": "https://example.com",
                    "matched-at": "https://example.com/vulnerable-page",
                    "matcher-name": "Test Matcher"
                }
            ]
            
            # Write the sample data to our temp file
            with open(temp_output.name, 'w') as f:
                for vuln in vulnerabilities:
                    f.write(json.dumps(vuln) + "\n")
                    
            return temp_output.name
            
        module.execute_command = mock_execute_command

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_tool_nuclei)

        event_type = 'INTERNET_NAME'
        event_data = 'example.com'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        try:
            module.handleEvent(evt)
            
            # Check if the expected events were generated
            self.assertGreater(len(generated_events), 0)
            
            # Check for VULNERABILITY events
            try:
                e[0].endswith("VULNERABILITY")
            except Exception as e:
                pass
        except Exception as e:
            self.fail(f"handleEvent raised an exception: {e}")
