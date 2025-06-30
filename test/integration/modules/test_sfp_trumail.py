import pytest
import unittest
from unittest.mock import patch

from modules.sfp_trumail import sfp_trumail
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationTrumail(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({'_fetchtimeout': 5, '_useragent': 'SpiderFootTestAgent'})
        self.module = sfp_trumail()
        self.module.__name__ = "sfp_trumail"  # Monkeypatch for event emission
        self.module.setup(self.sf, {'_fetchtimeout': 5, '_useragent': 'SpiderFootTestAgent'})
        self.target_value = 'test@example.com'
        self.target_type = 'EMAILADDR'
        self.target = SpiderFootTarget(self.target_value, self.target_type)
        self.module.setTarget(self.target)
        self.events = []
        self.module.notifyListeners = self.events.append

    def test_handleEvent_emits_events(self):
        # Mock Trumail API response for a disposable email
        mock_response = {'code': '200', 'content': '{"disposable": true, "other": "data"}'}
        with patch.object(self.module.sf, 'fetchUrl', return_value=mock_response):
            event = SpiderFootEvent('EMAILADDR', 'test@example.com', 'sfp_trumail', None)
            self.module.handleEvent(event)
        event_types = [e.eventType for e in self.events]
        event_datas = [e.data for e in self.events]
        # Check RAW_RIR_DATA event
        self.assertIn('RAW_RIR_DATA', event_types)
        self.assertTrue(any('disposable' in d for d in event_datas))
        # Check EMAILADDR_DISPOSABLE event
        self.assertIn('EMAILADDR_DISPOSABLE', event_types)
        self.assertIn('test@example.com', event_datas)
