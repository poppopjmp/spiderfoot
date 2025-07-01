import pytest
import unittest
from unittest.mock import patch

from modules.sfp_neutrinoapi import sfp_neutrinoapi
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class DummyEventListener:
    def __init__(self):
        self.events = []
    def notifyListeners(self, event):
        self.events.append(event)

class TestModuleIntegrationNeutrinoapi(unittest.TestCase):
    def setUp(self):
        self.options = {
            'user_id': 'dummy_user',
            'api_key': 'dummy_key',
            'timeout': 5,
            '_useragent': 'SpiderFootTestAgent'
        }
        self.sf = SpiderFoot(self.options)
        self.module = sfp_neutrinoapi()
        self.module.setup(self.sf, self.options)
        self.module.__name__ = 'sfp_neutrinoapi'  # Needed for event emission
        self.listener = DummyEventListener()
        self.module.notifyListeners = self.listener.notifyListeners

    @patch('spiderfoot.sflib.SpiderFoot.fetchUrl')
    def test_handleEvent_emits_events_on_valid_ip(self, mock_fetch):
        # Simulate NeutrinoAPI responses for all three API calls
        def fetchUrl_side_effect(url, **kwargs):
            if 'ip-info' in url:
                return {'code': '200', 'content': '{"city": "TestCity", "region": "TestRegion", "country-code": "TC"}'}
            if 'ip-blocklist' in url:
                return {'code': '200', 'content': '{"is-listed": true, "is-proxy": true, "is-vpn": true, "is-tor": true}'}
            if 'host-reputation' in url:
                return {'code': '200', 'content': '{"is-listed": true}'}
            return {'code': '200', 'content': '{}'}
        mock_fetch.side_effect = fetchUrl_side_effect
        event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'test_module', None)
        self.module.handleEvent(event)
        event_types = [e.eventType for e in self.listener.events]
        # Check for all expected event types
        assert 'GEOINFO' in event_types
        assert 'MALICIOUS_IPADDR' in event_types
        assert 'BLACKLISTED_IPADDR' in event_types
        assert 'RAW_RIR_DATA' in event_types
        assert 'PROXY_HOST' in event_types
        assert 'VPN_HOST' in event_types
        assert 'TOR_EXIT_NODE' in event_types
        # Check GEOINFO event data
        geo_event = next(e for e in self.listener.events if e.eventType == 'GEOINFO')
        assert geo_event.data == 'TestCity, TestRegion, TC'
