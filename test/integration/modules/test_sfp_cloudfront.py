# filepath: spiderfoot/test/integration/modules/test_sfpcloudfront.py
import unittest
from unittest.mock import patch, MagicMock
import os

from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_cloudfront import sfp_cloudfront


class TestModuleIntegrationCloudfront(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
            '_debug': False,
            '_genericusers': 'info,admin',
        })
        self.module = sfp_cloudfront()
        self.module.__name__ = 'sfp_cloudfront'
        self.options = {
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
            '_debug': False,
            '_genericusers': 'info,admin',
            'verify_cname': True,
            'verify_dns': True,
            'verify_headers': True,
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append

    @patch('dns.resolver.resolve')
    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_cloudfront_cname(self, mock_fetch, mock_resolve):
        # Simulate DNS CNAME response for CloudFront
        mock_answer = MagicMock()
        mock_answer.__str__.return_value = 'd123.cloudfront.net.'
        mock_resolve.return_value = [mock_answer]
        # Simulate HTTP headers (not used in this test)
        mock_fetch.return_value = {'headers': {}}
        target = SpiderFootTarget('example.com', 'INTERNET_NAME')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('DOMAIN_NAME', 'example.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'CLOUD_PROVIDER' in event_types, 'CLOUD_PROVIDER event not emitted.'
        assert 'CLOUD_INSTANCE_TYPE' in event_types, 'CLOUD_INSTANCE_TYPE event not emitted.'
        assert 'RAW_DNS_RECORDS' in event_types, 'RAW_DNS_RECORDS event not emitted.'

    @patch('dns.resolver.resolve', side_effect=Exception('No CNAME'))
    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_cloudfront_headers(self, mock_fetch, _mock_resolve):
        # Simulate HTTP headers indicating CloudFront
        mock_fetch.return_value = {'headers': {'X-Amz-Cf-Id': 'cloudfront-xyz'}}
        target = SpiderFootTarget('example.com', 'INTERNET_NAME')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('DOMAIN_NAME', 'example.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'CLOUD_PROVIDER' in event_types, 'CLOUD_PROVIDER event not emitted.'
        assert 'CLOUD_INSTANCE_TYPE' in event_types, 'CLOUD_INSTANCE_TYPE event not emitted.'
        assert 'WEBSERVER_BANNER' in event_types, 'WEBSERVER_BANNER event not emitted.'
