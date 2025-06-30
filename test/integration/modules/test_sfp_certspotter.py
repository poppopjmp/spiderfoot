import pytest
import unittest
from unittest.mock import patch
import json

from modules.sfp_certspotter import sfp_certspotter
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationCertspotter(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
        })
        self.module = sfp_certspotter()
        self.module.__name__ = 'sfp_certspotter'
        self.options = {
            'api_key': 'DUMMYKEY',
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append
        # Patch parseCert to return a minimal valid cert dict
        self.module.sf.parseCert = lambda rawcert, domain, days: {
            'text': 'CERTDATA',
            'issuer': 'Test Issuer',
            'issued': '2025-01-01',
            'altnames': ['alt.example.com'],
            'expired': False,
            'expiring': False
        }
        # Patch resolveHost/resolveHost6 to always resolve
        self.module.sf.resolveHost = lambda d: True
        self.module.sf.resolveHost6 = lambda d: True
        self.module.getTarget = lambda: SpiderFootTarget('example.com', 'INTERNET_NAME')

    @patch('time.sleep', return_value=None)
    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_domain_name(self, mock_fetch, mock_sleep):
        # Simulate CertSpotter API response with one certificate
        api_response = [
            {
                'id': 'abc123',
                'dns_names': ['alt.example.com'],
                'cert': {'data': 'BASE64CERTDATA'}
            }
        ]
        mock_fetch.return_value = {'code': '200', 'content': json.dumps(api_response)}
        target = SpiderFootTarget('example.com', 'INTERNET_NAME')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('DOMAIN_NAME', 'example.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'SSL_CERTIFICATE_RAW' in event_types
        assert 'INTERNET_NAME' in event_types or 'CO_HOSTED_SITE' in event_types
        # Check event data for SSL_CERTIFICATE_RAW
        found = any('CERTDATA' in e.data for e in self.events if e.eventType == 'SSL_CERTIFICATE_RAW')
        assert found, 'SSL_CERTIFICATE_RAW event data does not contain expected certificate data.'
