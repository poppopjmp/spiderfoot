import pytest
import unittest
import base64

from modules.sfp_fofa import sfp_fofa
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleFofa(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_fofa()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_fofa()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_fofa()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_fofa()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_api_key_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_fofa()
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

        module = sfp_fofa()
        module.setup(sf, dict())
        module.opts['api_key'] = 'test_api_key'
        module.opts['username'] = 'test_username'

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # FOFA uses base64 encoded queries, so let's prepare that
        query = f"domain=\"example.com\""
        encoded_query = base64.b64encode(query.encode('utf-8')).decode('utf-8')

        # Mock the API response
        def fetchUrl_mock(url, *args, **kwargs):
            if encoded_query in url:
                return {
                    'code': 200,
                    'content': '{"error":false,"size":1,"results":[["example.com","93.184.216.34","443","US","Example Organization"]]}'
                }
            return {
                'code': 404,
                'content': '{"error":true,"errmsg":"Not found"}'
            }

        module.sf.fetchUrl = fetchUrl_mock

        # Track generated events
        generated_events = []
        def notifyListeners_mock(event):
            generated_events.append(event)

        module.notifyListeners = notifyListeners_mock.__get__(module, sfp_fofa)

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
        self.assertIn('RAW_RIR_DATA', event_types)
        self.assertIn('IP_ADDRESS', event_types)
        self.assertIn('TCP_PORT_OPEN', event_types)
        self.assertIn('COMPANY_NAME', event_types)
        self.assertIn('PHYSICAL_COORDINATES', event_types)
