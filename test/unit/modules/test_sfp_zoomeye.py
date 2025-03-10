import pytest
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_zoomeye import sfp_zoomeye
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleZoomeye(SpiderFootModuleTestCase):

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
            sfp_zoomeye,
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

    def test_handleEvent_no_api_key_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = self.module_class()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def test_handleEvent_with_api_key_should_make_api_request(self):
        sf = SpiderFoot(self.default_options)

        module = self.module_class()
        module.setup(sf, dict())
        module.opts['api_key'] = 'test_api_key'

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the API response
        def fetchUrl_mock(url, *args, **kwargs):
            return {
                'code': 200,
                'content': '{"matches": [{"ip": "93.184.216.34", "portinfo": {"port": 80, "service": "http"}, "site": "example.com"}], "total": 1}'
            }

        module.sf.fetchUrl = fetchUrl_mock

        # Track generated events
        generated_events = []
        def notifyListeners_mock(event):
            generated_events.append(event)

        module.notifyListeners = notifyListeners_mock.__get__(module, sfp_zoomeye)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)

        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for specific event types
        event_types = [e.eventType for e in generated_events]
        self.assertIn('IP_ADDRESS', event_types)
        self.assertIn('TCP_PORT_OPEN', event_types)
        self.assertIn('RAW_RIR_DATA', event_types)
