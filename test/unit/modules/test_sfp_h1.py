# filepath: c:\Users\van1sh\Documents\GitHub\spiderfoot\test\unit\modules\test_sfp_h1.py
import pytest
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_h1 import sfp_h1
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleH1(SpiderFootModuleTestCase):

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
            sfp_h1,
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
    
    def test_handleEvent_domain_should_return_bug_bounty_program(self):
        sf = SpiderFoot(self.default_options)

        module = self.module_class()
        module.setup(sf, dict())
        
        # Mock the fetchUrl method
        def fetch_url_mock(url, *args, **kwargs):
            return {
                'code': 200,
                'content': '<html><body><h1>Directory Listing</h1><ul><li><a href="example.com.json">example.com.json</a></li></ul></body></html>'
            }
            
        def fetch_url_json_mock(url, *args, **kwargs):
            if "example.com.json" in url:
                return {
                    'code': 200,
                    'content': '{"handle": "example", "url": "https://hackerone.com/example"}'
                }
            return {'code': 404, 'content': ''}
            
        # Set up mocked functions
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
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_h1)
        
        # Define a custom get_h1_data for testing
        def get_h1_data_mock(domain):
            return {"handle": "example", "url": "https://hackerone.com/example"}
            
        module.get_h1_data = get_h1_data_mock

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check if the expected event was generated
        self.assertGreater(len(generated_events), 0)
        
        # Verify bug bounty event
        found_bug_bounty = False
        for event in generated_events:
            if event.eventType == 'VULNERABILITY_DISCLOSURE_PROGRAM':
                found_bug_bounty = True
                self.assertIn('example', event.data)
                
        self.assertTrue(found_bug_bounty, "VULNERABILITY_DISCLOSURE_PROGRAM event not generated")