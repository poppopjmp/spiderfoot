import pytest
import unittest
from unittest.mock import patch

from modules.sfp_onioncity import sfp_onioncity
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class DummyEventListener:
    def __init__(self):
        self.events = []
    def notifyListeners(self, event):
        self.events.append(event)

class TestModuleIntegrationOnioncity(unittest.TestCase):
    def setUp(self):
        self.options = {
            'api_key': 'dummy_key',
            'cse_id': 'dummy_cse',
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
            'fetchlinks': True,
            'fullnames': True
        }
        self.sf = SpiderFoot(self.options)
        self.module = sfp_onioncity()
        self.module.setup(self.sf, self.options)
        self.module.__name__ = 'sfp_onioncity'  # Needed for event emission
        self.listener = DummyEventListener()
        self.module.notifyListeners = self.listener.notifyListeners

    @patch('sflib.SpiderFoot.fetchUrl')
    @patch('sflib.SpiderFoot.googleIterate')
    @patch('sflib.SpiderFoot.urlFQDN', lambda self, url: url.split('/')[2])
    def test_handleEvent_emits_events_on_domain(self, mock_googleIterate, mock_fetchUrl):
        # Simulate Google search result with .onion.link URL
        mock_googleIterate.return_value = {
            'urls': ['http://sometarget.onion.link/page'],
            'webSearchUrl': 'http://google.com/search?q=site:onion.link+sometarget'
        }
        # Simulate fetchUrl for Google search and .onion page
        def fetchUrl_side_effect(url, **kwargs):
            if 'google.com' in url:
                return {'code': '200', 'content': 'search result content'}
            if '.onion' in url:
                return {'code': '200', 'content': '...sometarget...'}
            return {'code': '200', 'content': ''}
        mock_fetchUrl.side_effect = fetchUrl_side_effect
        event = SpiderFootEvent('DOMAIN_NAME', 'sometarget', 'test_module', None)
        self.module.handleEvent(event)
        event_types = [e.eventType for e in self.listener.events]
        assert 'RAW_RIR_DATA' in event_types
        assert 'DARKNET_MENTION_URL' in event_types
        assert 'DARKNET_MENTION_CONTENT' in event_types
        darknet_url_event = next(e for e in self.listener.events if e.eventType == 'DARKNET_MENTION_URL')
        assert darknet_url_event.data.startswith('http://sometarget.onion')
        darknet_content_event = next(e for e in self.listener.events if e.eventType == 'DARKNET_MENTION_CONTENT')
        assert 'sometarget' in darknet_content_event.data
