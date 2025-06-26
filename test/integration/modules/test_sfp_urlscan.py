import pytest
import unittest
from unittest.mock import patch

from modules.sfp_urlscan import sfp_urlscan
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationUrlscan(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({'_fetchtimeout': 5, '_useragent': 'SpiderFootTestAgent', '_internettlds': ['com']})
        self.module = sfp_urlscan()
        self.module.__name__ = "sfp_urlscan"  # Monkeypatch for event emission
        self.module.setup(self.sf, {'_fetchtimeout': 5, '_useragent': 'SpiderFootTestAgent', '_internettlds': ['com']})
        self.target_value = 'example.com'
        self.target_type = 'INTERNET_NAME'
        self.target = SpiderFootTarget(self.target_value, self.target_type)
        self.module.setTarget(self.target)
        self.events = []
        self.module.notifyListeners = self.events.append
        # Patch resolveHost and resolveHost6 to always return True for deterministic test
        self.sf.resolveHost = lambda d: True
        self.sf.resolveHost6 = lambda d: False
        self.sf.isDomain = lambda d, tlds: True
        self.sf.urlFQDN = lambda url: 'example.com'

    def test_handleEvent_emits_events(self):
        # Mock URLScan API response with all event types, including a subdomain
        mock_results = [
            {
                'page': {
                    'domain': 'example.com',
                    'asn': 'AS12345',
                    'city': 'Test City',
                    'country': 'Test Country',
                    'server': 'nginx'
                },
                'task': {
                    'url': 'http://example.com/page'
                }
            },
            {
                'page': {
                    'domain': 'sub.example.com',
                    'asn': 'AS54321',
                    'city': 'Other City',
                    'country': 'Other Country',
                    'server': 'apache'
                },
                'task': {
                    'url': 'http://sub.example.com/page'
                }
            }
        ]
        mock_response = {'code': '200', 'content': '{"results": ' + str(mock_results).replace("'", '"') + '}'}
        with patch.object(self.module.sf, 'fetchUrl', return_value=mock_response):
            event = SpiderFootEvent('INTERNET_NAME', 'example.com', 'sfp_urlscan', None)
            self.module.handleEvent(event)
        event_types = [e.eventType for e in self.events]
        event_datas = [e.data for e in self.events]
        # Check RAW_RIR_DATA event
        self.assertIn('RAW_RIR_DATA', event_types)
        # Check LINKED_URL_INTERNAL event
        self.assertIn('LINKED_URL_INTERNAL', event_types)
        self.assertIn('http://example.com/page', event_datas)
        # Check GEOINFO event
        self.assertIn('GEOINFO', event_types)
        self.assertIn('Test City, Test Country', event_datas)
        # Check INTERNET_NAME event (should be for 'sub.example.com')
        self.assertIn('INTERNET_NAME', event_types)
        self.assertIn('sub.example.com', event_datas)
        # Check DOMAIN_NAME event (should be for 'sub.example.com')
        self.assertIn('DOMAIN_NAME', event_types)
        self.assertIn('sub.example.com', event_datas)
        # Check BGP_AS_MEMBER event
        self.assertIn('BGP_AS_MEMBER', event_types)
        self.assertIn('12345', event_datas)
        # Check WEBSERVER_BANNER event
        self.assertIn('WEBSERVER_BANNER', event_types)
        self.assertIn('nginx', event_datas)
