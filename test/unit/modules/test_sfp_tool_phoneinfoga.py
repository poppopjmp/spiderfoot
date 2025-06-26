import unittest
from unittest.mock import patch, MagicMock
from modules.sfp_tool_phoneinfoga import sfp_tool_phoneinfoga
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
import json

class TestPhoneInfogaModuleUnit(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({'_useragent': 'SpiderFootTestAgent'})
        self.module = sfp_tool_phoneinfoga()
        self.module.__name__ = 'sfp_tool_phoneinfoga'
        self.options = {
            'api_endpoint': 'http://localhost:5000/api/v2/scan',
            'timeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_valid_response(self, mock_fetch):
        api_response = {
            'valid': True,
            'country': 'United States',
            'carrier': 'Verizon',
            'line_type': 'mobile',
            'region': 'California',
        }
        mock_fetch.return_value = {'code': '200', 'content': json.dumps(api_response)}
        target = SpiderFootTarget('+14155552671', 'PHONE_NUMBER')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('PHONE_NUMBER', '+14155552671', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'PHONE_NUMBER' in event_types
        assert 'COUNTRY_NAME' in event_types
        assert 'CARRIER_NAME' in event_types
        assert 'LINE_TYPE' in event_types
        assert 'REGION_NAME' in event_types
        assert 'RAW_RIR_DATA' in event_types

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_invalid_response(self, mock_fetch):
        api_response = {'valid': False}
        mock_fetch.return_value = {'code': '200', 'content': json.dumps(api_response)}
        target = SpiderFootTarget('+14155552671', 'PHONE_NUMBER')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('PHONE_NUMBER', '+14155552671', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'PHONE_NUMBER' not in event_types
        assert 'RAW_RIR_DATA' in event_types

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_full_response(self, mock_fetch):
        api_response = {
            'valid': True,
            'country': 'United States',
            'carrier': 'Verizon',
            'line_type': 'mobile',
            'region': 'California',
            'international_format': '+1 415-555-2671',
            'local_format': '4155552671',
            'number_type': 'mobile',
            'is_possible': True,
            'is_valid': True,
            'location': 'San Francisco',
            'carrier_type': 'wireless',
        }
        mock_fetch.return_value = {'code': '200', 'content': json.dumps(api_response)}
        target = SpiderFootTarget('+14155552671', 'PHONE_NUMBER')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('PHONE_NUMBER', '+14155552671', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'PHONE_NUMBER' in event_types
        assert 'COUNTRY_NAME' in event_types
        assert 'CARRIER_NAME' in event_types
        assert 'LINE_TYPE' in event_types
        assert 'REGION_NAME' in event_types
        assert 'RAW_RIR_DATA' in event_types
        assert 'INTERNATIONAL_FORMAT' in event_types
        assert 'LOCAL_FORMAT' in event_types
        assert 'NUMBER_TYPE' in event_types
        assert 'IS_POSSIBLE' in event_types
        assert 'IS_VALID' in event_types
        assert 'LOCATION' in event_types
        assert 'CARRIER_TYPE' in event_types

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_error_and_retry(self, mock_fetch):
        # Simulate API error on first call, success on retry
        api_response = {
            'valid': True,
            'country': 'United States',
            'carrier': 'Verizon',
            'line_type': 'mobile',
            'region': 'California',
        }
        mock_fetch.side_effect = [None, {'code': '200', 'content': json.dumps(api_response)}]
        target = SpiderFootTarget('+14155552671', 'PHONE_NUMBER')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('PHONE_NUMBER', '+14155552671', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'PHONE_NUMBER' in event_types
        assert 'RAW_RIR_DATA' in event_types
