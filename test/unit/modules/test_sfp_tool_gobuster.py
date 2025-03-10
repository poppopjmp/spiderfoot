import pytest
import unittest
from unittest.mock import patch, MagicMock
import json
import tempfile
import os

from modules.sfp_tool_gobuster import sfp_tool_gobuster
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleToolGobuster(SpiderFootModuleTestCase):

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
            sfp_tool_gobuster,
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
        
    def test_handleEvent_no_tool_path_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = self.module_class()
        module.setup(sf, dict())
        module.opts['gobuster_path'] = ''  # Empty path should cause error

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
    
    def test_handleEvent_with_tool_path_should_process_url(self):
        sf = SpiderFoot(self.default_options)

        module = self.module_class()
        module.setup(sf, dict())
        module.opts['gobuster_path'] = '/usr/bin/gobuster'  # Mock path
        
        # Create a temporary wordlist file for testing
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"admin\nlogin\ndashboard")
            module.opts['wordlist'] = tmp.name
        
        # Mock the command execution
        def mock_execute_command(cmd):
            # Prepare sample output that mimics gobuster output format
            output = {
                "results": [
                    {"path": "/admin", "status": 200},
                    {"path": "/login", "status": 200},
                    {"path": "/dashboard", "status": 302}
                ]
            }
            
            # Create a temporary file with the JSON output
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as output_file:
                json.dump(output, output_file)
                return output_file.name
        
        module.execute_command = mock_execute_command

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_tool_gobuster)
        
        event_type = 'URL'
        event_data = 'https://example.com'
        event_module = 'sfp_spider'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Clean up temporary files
        os.unlink(module.opts['wordlist'])
        
        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for URL_DIRECTORY events
        url_dirs = [e for e in generated_events if e.eventType == 'URL_DIRECTORY']
        self.assertGreater(len(url_dirs), 0)
        
        expected_paths = ['/admin', '/login', '/dashboard']
        found_paths = []
        
        for event in url_dirs:
            for path in expected_paths:
                if path in event.data:
                    found_paths.append(path)
        
        for path in expected_paths:
            self.assertIn(path, found_paths)
