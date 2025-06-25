import pytest
import unittest
from unittest.mock import patch

from modules.sfp_twilio import sfp_twilio
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationTwilio(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({'_fetchtimeout': 5, '_useragent': 'SpiderFootTestAgent'})
        self.module = sfp_twilio()
        self.module.__name__ = "sfp_twilio"  # Monkeypatch for event emission
        self.module.setup(self.sf, {
            'api_key_account_sid': 'dummy_sid',
            'api_key_auth_token': 'dummy_token',
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent'
        })
        self.target_value = '+1234567890'
        self.target_type = 'PHONE_NUMBER'
        self.target = SpiderFootTarget(self.target_value, self.target_type)
        self.module.setTarget(self.target)
        self.events = []
        self.module.notifyListeners = self.events.append

    def test_handleEvent_emits_events(self):
        # Mock Twilio API response with a caller_name
        mock_content = '{"caller_name": {"caller_name": "Test Company"}, "other": "data"}'
        mock_response = {'code': '200', 'content': mock_content}
        with patch.object(self.module.sf, 'fetchUrl', return_value=mock_response):
            event = SpiderFootEvent('PHONE_NUMBER', '+1234567890', 'sfp_twilio', None)
            self.module.handleEvent(event)
        event_types = [e.eventType for e in self.events]
        event_datas = [e.data for e in self.events]
        # Check RAW_RIR_DATA event
        self.assertIn('RAW_RIR_DATA', event_types)
        self.assertTrue(any('caller_name' in d for d in event_datas))
        # Check COMPANY_NAME event
        self.assertIn('COMPANY_NAME', event_types)
        self.assertIn('Test Company', event_datas)
