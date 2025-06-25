import pytest
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_trashpanda import sfp_trashpanda
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationTrashpanda(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        })
        self.module = sfp_trashpanda()
        self.module.__name__ = "sfp_trashpanda"  # Monkeypatch for event emission
        self.options = {
            'api_key_username': 'dummyuser',
            'api_key_password': 'dummypass',
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        }
        self.module.setup(self.sf, self.options)
        self.target_value = 'test@example.com'
        self.target_type = 'EMAILADDR'
        self.target = SpiderFootTarget(self.target_value, self.target_type)
        self.module.setTarget(self.target)
        self.events = []
        self.module.notifyListeners = self.events.append

    def test_handleEvent_emits_events(self):
        # Mock Trashpanda API response and leaksite fetch
        api_response = [
            {
                'email': 'test@example.com',
                'password': 'hunter2',
                'paste': 'http://pastebin.com/abc123'
            }
        ]
        # The leaksite content must match the regex in the module (contain test@example.com with non-alphanumeric chars around)
        leaksite_content = ': test@example.com : hunter2 leaked!'
        with patch.object(self.module.sf, 'fetchUrl') as mock_fetchUrl:
            mock_fetchUrl.side_effect = [
                {'code': '200', 'content': '[{"email": "test@example.com", "password": "hunter2", "paste": "http://pastebin.com/abc123"}]'},
                {'code': '200', 'content': leaksite_content}
            ]
            event = SpiderFootEvent('EMAILADDR', 'test@example.com', 'sfp_trashpanda', None)
            self.module.handleEvent(event)
        event_types = [e.eventType for e in self.events]
        event_datas = [e.data for e in self.events]
        # Check PASSWORD_COMPROMISED event
        self.assertIn('PASSWORD_COMPROMISED', event_types)
        self.assertTrue(any('test@example.com:hunter2' in d for d in event_datas))
        # Check LEAKSITE_URL event
        self.assertIn('LEAKSITE_URL', event_types)
        self.assertIn('http://pastebin.com/abc123', event_datas)
        # Check LEAKSITE_CONTENT event
        self.assertIn('LEAKSITE_CONTENT', event_types)
        self.assertIn(leaksite_content, event_datas)
