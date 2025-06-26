import pytest
import unittest
from unittest.mock import patch

from modules.sfp_onionsearchengine import sfp_onionsearchengine
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent



class DummyEventListener:
    def __init__(self):
        self.events = []
    def notifyListeners(self, event):
        self.events.append(event)

class TestModuleIntegrationOnionsearchengine(unittest.TestCase):
    def setUp(self):
        self.options = {
            '_useragent': 'SpiderFootTestAgent',
            '_fetchtimeout': 5,
            'timeout': 5,
            'max_pages': 1,
            'fetchlinks': True,
            'blacklist': [],  # Ensure blacklist is empty
            'fullnames': True
        }
        self.sf = SpiderFoot(self.options)
        self.module = sfp_onionsearchengine()
        self.module.setup(self.sf, self.options)
        self.module.__name__ = 'sfp_onionsearchengine'  # Needed for event emission
        self.listener = DummyEventListener()
        self.module.notifyListeners = self.listener.notifyListeners

    @patch('sflib.SpiderFoot.fetchUrl')
    @patch('sflib.SpiderFoot.urlFQDN', lambda self, url: 'sometarget.onion')
    def test_handleEvent_emits_events_on_domain(self, mock_fetchUrl):
        # Simulate search result page and .onion page
        def fetchUrl_side_effect(url, **kwargs):
            if 'onionsearchengine.com/search.php' in url:
                # Simulate a search result with a .onion link (with trailing quote)
                return {'content': "url.php?u=http://sometarget.onion/page'", 'code': '200'}
            if 'sometarget.onion' in url:
                # Simulate the .onion page content containing the event data
                return {'content': '...sometarget...', 'code': '200'}
            return {'content': '', 'code': '200'}
        mock_fetchUrl.side_effect = fetchUrl_side_effect
        event = SpiderFootEvent('DOMAIN_NAME', 'sometarget', 'test_module', None)
        self.module.handleEvent(event)
        event_types = [e.eventType for e in self.listener.events]
        print('Emitted event types:', event_types)
        for e in self.listener.events:
            print('Event:', e.eventType, e.data)
        assert 'DARKNET_MENTION_URL' in event_types
        assert 'DARKNET_MENTION_CONTENT' in event_types
        darknet_url_event = next(e for e in self.listener.events if e.eventType == 'DARKNET_MENTION_URL')
        assert darknet_url_event.data.startswith('http://sometarget.onion')
        darknet_content_event = next(e for e in self.listener.events if e.eventType == 'DARKNET_MENTION_CONTENT')
        assert 'sometarget' in darknet_content_event.data
