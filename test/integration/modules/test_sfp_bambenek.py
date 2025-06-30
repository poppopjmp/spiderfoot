# filepath: spiderfoot/test/integration/modules/test_sfpbambenek.py
import pytest
from unittest.mock import patch
import os

from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_bambenek import sfp_bambenek


class TestModuleIntegrationBambenek:
    """Integration testing for the Bambenek module."""

    @pytest.fixture
    def module(self):
        sf = SpiderFoot({
            '_debug': True,
            '__logging': True,
            '__outputfilter': None,
            'checkaffiliates': True,
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
            '_socks1type': '',
            '_socks2addr': '',
            '_socks3port': '',
            '_socks4user': '',
            '_socks5pwd': '',
        })
        module = sfp_bambenek()
        module.setup(sf, {
            'checkaffiliates': True,
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
            '_socks1type': '',
            '_socks2addr': '',
            '_socks3port': '',
            '_socks4user': '',
            '_socks5pwd': '',
        })
        module.sf.events = []
        module.notifyListeners = lambda evt: module.sf.events.append({'type': evt.eventType, 'data': evt.data})
        return module

    @patch.object(sfp_bambenek, 'retrieveDataFromFeed')
    def test_module_produces_events(self, mock_retrieve, module):
        # Mock the feeds so 'example.com' is present in dga_domains and c2_domains
        def fake_feed(url):
            if 'dga-feed' in url or 'c2-dommasterlist' in url:
                return ['example.com']
            if 'c2-ipmasterlist' in url:
                return []
            return []
        mock_retrieve.side_effect = fake_feed
        module.feedCache = {
            'dga_domains': ['example.com'],
            'c2_ips': [],
            'c2_domains': ['example.com'],
        }
        target_value = "example.com"
        target_type = "INTERNET_NAME"
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        event_type = "INTERNET_NAME"
        event_data = "example.com"
        event_module = "test"
        source_event = SpiderFootEvent("ROOT", "root", "test", None)
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        module.handleEvent(evt)
        # Assert that the module produced events
        assert len(module.sf.events) > 0
        # Each event should be a dict with certain required fields
        for event in module.sf.events:
            assert event.get('type') is not None
            assert event.get('data') is not None
