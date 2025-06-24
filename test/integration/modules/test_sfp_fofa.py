import pytest
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_fofa import sfp_fofa
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationFofa(unittest.TestCase):
    def setUp(self):
        self.sf = MagicMock()
        self.plugin = sfp_fofa()
        self.plugin.setup(self.sf, {'api_email': 'test@example.com', 'api_key': 'key', 'max_age_days': 30})
        self.plugin.notifyListeners = MagicMock()

    def test_watchedEvents(self):
        self.assertEqual(self.plugin.watchedEvents(), ["DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"])

    def test_producedEvents(self):
        self.assertEqual(self.plugin.producedEvents(), ["INTERNET_NAME", "DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS", "RAW_RIR_DATA"])

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_emits_events(self, mock_sleep):
        self.sf.fetchUrl.return_value = {
            'code': 200,
            'content': '{"results": [ {"host": "host1", "domain": "domain1", "ip": "1.2.3.4", "ipv6": "::1"} ]}'
        }
        event = SpiderFootEvent('DOMAIN_NAME', 'example.com', 'integration', None)
        self.plugin.handleEvent(event)
        # 1 RAW_RIR_DATA + 4 unique events
        self.assertEqual(self.plugin.notifyListeners.call_count, 5)
        args, _ = self.plugin.notifyListeners.call_args
        evt = args[0]
        self.assertIn(evt.eventType, ['INTERNET_NAME', 'DOMAIN_NAME', 'IP_ADDRESS', 'IPV6_ADDRESS', 'RAW_RIR_DATA'])

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_no_results(self, mock_sleep):
        self.sf.fetchUrl.return_value = {'code': 200, 'content': '{"results": []}'}
        event = SpiderFootEvent('DOMAIN_NAME', 'noresults.com', 'integration', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_called_once()  # Only RAW_RIR_DATA

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_api_error(self, mock_sleep):
        self.sf.fetchUrl.return_value = {'code': 500, 'errmsg': 'API error', 'content': '{}'}
        event = SpiderFootEvent('DOMAIN_NAME', 'error.com', 'integration', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_invalid_key(self, mock_sleep):
        plugin = sfp_fofa()
        plugin.setup(self.sf, {'api_email': '', 'api_key': '', 'max_age_days': 30})
        plugin.notifyListeners = MagicMock()
        event = SpiderFootEvent('DOMAIN_NAME', 'badkey.com', 'integration', None)
        plugin.handleEvent(event)
        plugin.notifyListeners.assert_not_called()

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handleEvent_emits_all_event_types(self, mock_sleep):
        self.sf.fetchUrl.return_value = {
            'code': 200,
            'content': '{"results": [ {"host": "host1", "domain": "domain1", "ip": "1.2.3.4", "ipv6": "::1"} ]}'
        }
        event = SpiderFootEvent('DOMAIN_NAME', 'alltypes.com', 'test', None)
        self.plugin.handleEvent(event)
        types = [call_args[0][0].eventType for call_args in self.plugin.notifyListeners.call_args_list]
        self.assertIn('INTERNET_NAME', types)
        self.assertIn('DOMAIN_NAME', types)
        self.assertIn('IP_ADDRESS', types)
        self.assertIn('IPV6_ADDRESS', types)
        self.assertIn('RAW_RIR_DATA', types)

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handleEvent_handles_empty_and_null_results(self, mock_sleep):
        self.sf.fetchUrl.return_value = {'code': 200, 'content': '{"results": null}'}
        event = SpiderFootEvent('DOMAIN_NAME', 'nullresults.com', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_called_once()  # Only RAW_RIR_DATA
        self.sf.fetchUrl.return_value = {'code': 200, 'content': '{"results": []}'}
        event = SpiderFootEvent('DOMAIN_NAME', 'emptyresults.com', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_called()  # Only RAW_RIR_DATA
