import pytest
import unittest
from unittest.mock import patch

from modules.sfp_onyphe import sfp_onyphe
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class DummyEventListener:
    def __init__(self):
        self.events = []

    def notifyListeners(self, event):
        self.events.append(event)


class TestModuleIntegrationOnyphe(unittest.TestCase):
    def setUp(self):
        self.options = {
            'api_key': 'dummy_key',
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
            'paid_plan': False,
            'max_page': 1,
            'verify': False,
            'age_limit_days': 0,
            'cohostsamedomain': False,
            'maxcohost': 100
        }
        self.sf = SpiderFoot(self.options)
        self.module = sfp_onyphe()
        self.module.setup(self.sf, self.options)
        self.module.__name__ = 'sfp_onyphe'  # Needed for event emission
        self.listener = DummyEventListener()
        self.module.notifyListeners = self.listener.notifyListeners

    @patch('sflib.SpiderFoot.fetchUrl')
    @patch('sflib.SpiderFoot.cveInfo', lambda self, cve: ('VULNERABILITY_CVE_CRITICAL', cve))
    def test_handleEvent_emits_events_on_ip(self, mock_fetchUrl):
        # Simulate Onyphe API responses for all endpoints
        def fetchUrl_side_effect(url, **kwargs):
            if 'geoloc' in url:
                return {'code': '200', 'content': '{"page": 1, "max_page": 1, "results": [{"city": "Paris", "country": "France", "location": "48.8566,2.3522", "subdomains": [], "domain": [], "@timestamp": "2025-06-25T12:00:00.000Z"}] }'}
            if 'pastries' in url:
                return {'code': '200', 'content': '{"page": 1, "max_page": 1, "results": [{"content": "leaked data", "@timestamp": "2025-06-25T12:00:00.000Z"}] }'}
            if 'threatlist' in url:
                return {'code': '200', 'content': '{"page": 1, "max_page": 1, "results": [{"threatlist": "malicious", "@timestamp": "2025-06-25T12:00:00.000Z"}] }'}
            if 'vulnscan' in url:
                return {'code': '200', 'content': '{"page": 1, "max_page": 1, "results": [{"cve": ["CVE-2025-0001"], "@timestamp": "2025-06-25T12:00:00.000Z"}] }'}
            return {'code': '200', 'content': '{"page": 1, "max_page": 1, "results": []}'}
        mock_fetchUrl.side_effect = fetchUrl_side_effect
        event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'test_module', None)
        self.module.handleEvent(event)
        event_types = [e.eventType for e in self.listener.events]
        assert 'GEOINFO' in event_types
        assert 'PHYSICAL_COORDINATES' in event_types
        assert 'LEAKSITE_CONTENT' in event_types
        assert 'MALICIOUS_IPADDR' in event_types
        assert 'VULNERABILITY_CVE_CRITICAL' in event_types
        assert 'RAW_RIR_DATA' in event_types
        geo_event = next(e for e in self.listener.events if e.eventType == 'GEOINFO')
        assert 'Paris' in geo_event.data and 'France' in geo_event.data
        leak_event = next(e for e in self.listener.events if e.eventType == 'LEAKSITE_CONTENT')
        assert 'leaked data' in leak_event.data
        vuln_event = next(e for e in self.listener.events if e.eventType == 'VULNERABILITY_CVE_CRITICAL')
        assert 'CVE-2025-0001' in vuln_event.data
