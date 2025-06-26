import pytest
import unittest
from unittest.mock import patch

from modules.sfp_numverify import sfp_numverify
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class DummyEventListener:
    def __init__(self):
        self.events = []
    def notifyListeners(self, event):
        self.events.append(event)

class TestModuleIntegrationNumverify(unittest.TestCase):
    def setUp(self):
        self.options = {
            'api_key': 'dummy_key',
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent'
        }
        self.sf = SpiderFoot(self.options)
        self.module = sfp_numverify()
        self.module.setup(self.sf, self.options)
        self.module.__name__ = 'sfp_numverify'  # Needed for event emission
        self.listener = DummyEventListener()
        self.module.notifyListeners = self.listener.notifyListeners

    @patch('sflib.SpiderFoot.fetchUrl')
    def test_handleEvent_emits_events_on_valid_phone(self, mock_fetch):
        # Simulate Numverify API positive response
        mock_fetch.return_value = {
            'code': '200',
            'content': '{"country_code": "US", "location": "California", "carrier": "Verizon"}'
        }
        event = SpiderFootEvent('PHONE_NUMBER', '+14155552671', 'test_module', None)
        self.module.handleEvent(event)
        event_types = [e.eventType for e in self.listener.events]
        event_datas = [e.data for e in self.listener.events]
        assert 'RAW_RIR_DATA' in event_types
        assert 'GEOINFO' in event_types
        assert 'PROVIDER_TELCO' in event_types
        # Check GEOINFO event data
        geo_event = next(e for e in self.listener.events if e.eventType == 'GEOINFO')
        assert 'California' in geo_event.data
        assert 'United States' in geo_event.data or 'US' in geo_event.data  # Accept either country name or code
        # Check PROVIDER_TELCO event data
        telco_event = next(e for e in self.listener.events if e.eventType == 'PROVIDER_TELCO')
        assert telco_event.data == 'Verizon'
