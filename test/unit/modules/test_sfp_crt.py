import pytest
import unittest

from modules.sfp_crt import sfp_crt
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleCrt(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_crt()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_crt()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_crt()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_crt()
        self.assertIsInstance(module.producedEvents(), list)

    def test_parseApiResponse_nonfatal_http_response_code_should_not_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        http_codes = ["200", "404"]
        for code in http_codes:
            with self.subTest(code=code):
                module = sfp_crt()
                module.setup(sf, dict())
                result = module.parseApiResponse({"code": code, "content": None})
                self.assertIsNone(result)
                self.assertFalse(module.errorState)

    def test_parseApiResponse_fatal_http_response_error_code_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        http_codes = ["401", "403", "429", "500", "502", "503"]
        for code in http_codes:
            with self.subTest(code=code):
                module = sfp_crt()
                module.setup(sf, dict())
                result = module.parseApiResponse({"code": code, "content": None})
                self.assertIsNone(result)
                self.assertTrue(module.errorState)
                
    def test_handleEvent_domain_name_should_return_certificate_data(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_crt()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the fetchUrl method
        def fetch_url_mock(url, timeout, useragent="SpiderFoot", headers=None):
            return {
                'code': 200,
                'content': """
                [
                  {
                    "issuer_ca_id": 16418,
                    "issuer_name": "C=US, O=Let's Encrypt, CN=Let's Encrypt Authority X3",
                    "common_name": "example.com",
                    "name_value": "example.com",
                    "id": 5550408742,
                    "entry_timestamp": "2021-11-01T12:34:56",
                    "not_before": "2021-11-01T11:11:11",
                    "not_after": "2022-01-30T11:11:11",
                    "serial_number": "0123456789abcdef0123456789abcdef",
                    "san": "example.com,www.example.com,api.example.com,dev.example.com"
                  },
                  {
                    "issuer_ca_id": 16418,
                    "issuer_name": "C=US, O=Let's Encrypt, CN=Let's Encrypt Authority X3",
                    "common_name": "example.com",
                    "name_value": "example.com",
                    "id": 5550408743,
                    "entry_timestamp": "2021-08-01T12:34:56",
                    "not_before": "2021-08-01T11:11:11",
                    "not_after": "2021-10-30T11:11:11",
                    "serial_number": "fedcba9876543210fedcba9876543210",
                    "san": "example.com,mail.example.com,blog.example.com"
                  }
                ]
                """
            }
            
        module.sf.fetchUrl = fetch_url_mock

        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_crt)
        
        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for INTERNET_NAME events
        internet_names = [e for e in generated_events if e.eventType == 'INTERNET_NAME']
        self.assertGreater(len(internet_names), 0)
        
        # Check that all domains in SAN fields were captured
        expected_domains = ['www.example.com', 'api.example.com', 'dev.example.com', 
                           'mail.example.com', 'blog.example.com']
        
        found_domains = [e.data for e in internet_names]
        
        for domain in expected_domains:
            self.assertIn(domain, found_domains)
