import pytest
import unittest
from unittest.mock import patch
import json

from modules.sfp_virustotal import sfp_virustotal
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationVirustotal(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
            '_debug': False,
        })
        self.module = sfp_virustotal()
        self.options = {
            'api_key': 'DUMMYKEY',
            'publicapi': False,
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
            '_debug': False,
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append
        self.module.getTarget = lambda: SpiderFootTarget('example.com', 'INTERNET_NAME')
        # Patch resolveHost/resolveHost6 to always resolve
        self.sf.resolveHost = lambda d: True
        self.sf.resolveHost6 = lambda d: True

    @patch('time.sleep', return_value=None)
    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_ip_address(self, mock_fetch, mock_sleep):
        vt_response = json.dumps({'detected_urls': [{}]})
        mock_fetch.return_value = {'code': '200', 'content': vt_response}
        target = SpiderFootTarget('8.8.8.8', 'IP_ADDRESS')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('IP_ADDRESS', '8.8.8.8', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'MALICIOUS_IPADDR' in event_types, 'MALICIOUS_IPADDR event not emitted.'
        found = any('VirusTotal' in e.data for e in self.events if e.eventType == 'MALICIOUS_IPADDR')
        assert found, 'MALICIOUS_IPADDR event data does not contain expected VirusTotal info.'

    @patch('time.sleep', return_value=None)
    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_internet_name(self, mock_fetch, mock_sleep):
        vt_response = json.dumps({'detected_urls': [{}], 'domain_siblings': ['alt.example.com'], 'subdomains': ['sub.example.com']})
        mock_fetch.return_value = {'code': '200', 'content': vt_response}
        target = SpiderFootTarget('example.com', 'INTERNET_NAME')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('INTERNET_NAME', 'example.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'MALICIOUS_INTERNET_NAME' in event_types, 'MALICIOUS_INTERNET_NAME event not emitted.'
        assert 'INTERNET_NAME' in event_types or 'AFFILIATE_INTERNET_NAME' in event_types, 'Expected domain events not emitted.'
        found = any('VirusTotal' in e.data for e in self.events if e.eventType == 'MALICIOUS_INTERNET_NAME')
        assert found, 'MALICIOUS_INTERNET_NAME event data does not contain expected VirusTotal info.'
