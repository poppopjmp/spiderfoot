import pytest
import unittest
import datetime

from modules.sfp_sslcert import sfp_sslcert
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleSslcert(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_sslcert()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_sslcert()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_sslcert()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_sslcert()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_internet_name_event_should_extract_certificate_data(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_sslcert()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the fetchCert method
        cert_info = {
            'subject': {'commonName': 'example.com'},
            'subjectAltName': (('DNS', 'example.com'), ('DNS', 'www.example.com')),
            'issuer': {'commonName': 'Example CA'},
            'validity': {
                'notBefore': datetime.datetime.now() - datetime.timedelta(days=30),
                'notAfter': datetime.datetime.now() + datetime.timedelta(days=335)
            },
            'serialNumber': '1234567890',
            'version': 3
        }
        def mock_fetchCert(hostname, port):
            return cert_info
        
        module.fetchCert = mock_fetchCert

        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_sslcert)
        
        event_type = 'INTERNET_NAME'
        event_data = 'example.com'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check event types
        event_types = [e.eventType for e in generated_events]
        expected_types = ['SSL_CERTIFICATE_ISSUED', 'SSL_CERTIFICATE_MISMATCH', 
                          'SSL_CERTIFICATE_EXPIRY', 'INTERNET_NAME', 'DOMAIN_NAME']
        
        for expected_type in expected_types:
            self.assertIn(expected_type, event_types, f"{expected_type} event not generated")
