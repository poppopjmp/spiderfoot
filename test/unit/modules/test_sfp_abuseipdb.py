import pytest
import unittest

from modules.sfp_abuseipdb import sfp_abuseipdb
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleAbuseipdb(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_abuseipdb()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_abuseipdb()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_abuseipdb()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_abuseipdb()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_api_key_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_abuseipdb()
        module.setup(sf, dict())

        target_value = '1.1.1.1'
        target_type = 'IP_ADDRESS'
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

    def test_handleEvent_with_api_key_should_make_api_request(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_abuseipdb()
        module.setup(sf, dict())
        module.opts['api_key'] = 'test_api_key'

        target_value = '1.1.1.1'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the API response
        def fetchUrl_mock(url, *args, **kwargs):
            return {
                'code': 200,
                'content': '{"data":{"abuseConfidenceScore":0,"countryCode":"AU","domain":"one.one.one.one","hostnames":["one.one.one.one"],"ipAddress":"1.1.1.1","isp":"Cloudflare, Inc","isPublic":true,"isWhitelisted":false,"totalReports":0,"usageType":"CDN/Content Delivery Network"}}'
            }

        module.sf.fetchUrl = fetchUrl_mock

        # Mock notifyListeners
        generated_events = []
        def notifyListeners_mock(event):
            generated_events.append(event)

        module.notifyListeners = notifyListeners_mock.__get__(module, sfp_abuseipdb)

        event_type = 'IP_ADDRESS'
        event_data = '1.1.1.1'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)

        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for specific event types
        event_types = [e.eventType for e in generated_events]
        self.assertIn('PROVIDER_NETWORK', event_types)
        self.assertIn('RAW_RIR_DATA', event_types)
