import unittest
from unittest.mock import patch, MagicMock
import json
from modules.sfp_tool_phoneinfoga import sfp_tool_phoneinfoga
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget

class TestModuleIntegrationPhoneInfoga(unittest.TestCase):
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
    def test_integration_phoneinfoga(self, mock_fetch):
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
    def test_integration_phoneinfoga_full(self, mock_fetch):
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
    def test_integration_phoneinfoga_error_and_retry(self, mock_fetch):
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

    @patch('paramiko.SSHClient')
    def test_integration_phoneinfoga_remote(self, mock_sshclient):
        mock_ssh = MagicMock()
        mock_sshclient.return_value = mock_ssh
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = json.dumps({
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
        }).encode()
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b''
        mock_ssh.exec_command.return_value = (None, mock_stdout, mock_stderr)
        self.module.opts['remote_enabled'] = True
        self.module.opts['remote_host'] = '1.2.3.4'
        self.module.opts['remote_user'] = 'testuser'
        self.module.opts['remote_tool_path'] = '/usr/bin/phoneinfoga'
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
