import pytest
import unittest
from unittest.mock import patch

from modules.sfp_venmo import sfp_venmo
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class DummyEventListener:
    def __init__(self):
        self.events = []
    def notifyListeners(self, event):
        self.events.append(event)

class TestModuleIntegrationVenmo(unittest.TestCase):
    def setUp(self):
        self.options = {
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent'
        }
        self.sf = SpiderFoot(self.options)
        self.module = sfp_venmo()
        self.module.setup(self.sf, self.options)
        self.module.__name__ = 'sfp_venmo'  # Needed for event emission
        self.listener = DummyEventListener()
        self.module.notifyListeners = self.listener.notifyListeners

    @patch('sflib.SpiderFoot.fetchUrl')
    def test_handleEvent_emits_events_on_valid_username(self, mock_fetch):
        # Simulate Venmo API positive response
        mock_fetch.return_value = {
            'content': '{"data": {"display_name": "John Doe", "first_name": "John", "last_name": "Doe"}}'
        }
        event = SpiderFootEvent('USERNAME', 'johndoe', 'test_module', None)
        self.module.handleEvent(event)
        event_types = [e.eventType for e in self.listener.events]
        event_datas = [e.data for e in self.listener.events]
        assert 'HUMAN_NAME' in event_types
        assert 'RAW_RIR_DATA' in event_types
        assert 'John Doe' in event_datas
        assert '{' in event_datas[1] or '{' in event_datas[0]  # RAW_RIR_DATA is JSON
