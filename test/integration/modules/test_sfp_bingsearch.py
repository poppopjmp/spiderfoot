import pytest
import unittest
from unittest.mock import patch

from modules.sfp_bingsearch import sfp_bingsearch
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationbingsearch(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({'api_key': 'dummy', '_fetchtimeout': 5, '_useragent': 'SpiderFootTestAgent'})
        self.module = sfp_bingsearch()
        self.module.setup(self.sf, {'api_key': 'dummy', '_fetchtimeout': 5, '_useragent': 'SpiderFootTestAgent'})
        self.module.__name__ = 'sfp_bingsearch'
        self.events = []
        self.module.notifyListeners = lambda evt: self.events.append(evt)

    @patch.object(SpiderFoot, 'bingIterate')
    def test_handleEvent(self, mock_bingIterate):
        # Simulate a valid Bing API response for an INTERNET_NAME event
        mock_bingIterate.return_value = {
            'urls': ['http://sub.example.com/page1', 'http://other.com/page2']
        }
        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)
        event_type = 'INTERNET_NAME'
        event_data = 'example.com'
        event_module = 'test'
        source_event = SpiderFootEvent('ROOT', 'root', 'test', None)
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        self.module.handleEvent(evt)
        # The module should emit at least one LINKED_URL_INTERNAL event for sub.example.com
        found = any(evt.eventType == 'LINKED_URL_INTERNAL' and evt.data == 'http://sub.example.com/page1' for evt in self.events)
        self.assertTrue(found, 'LINKED_URL_INTERNAL event not emitted for internal link')
