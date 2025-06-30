import pytest
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_tool_wappalyzer import sfp_tool_wappalyzer
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleWappalyzer(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_tool_wappalyzer()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_wappalyzer()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_wappalyzer()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_wappalyzer()
        self.assertIsInstance(module.producedEvents(), list)

    @safe_recursion(max_depth=5)
    def test_handleEvent_no_tool_path_configured_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_tool_wappalyzer()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()


class TestModuleWappalyzerAPI(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({})
        self.module = sfp_tool_wappalyzer()
        self.target_value = 'example.com'
        self.target_type = 'INTERNET_NAME'
        self.target = SpiderFootTarget(self.target_value, self.target_type)
        self.event = SpiderFootEvent('INTERNET_NAME', self.target_value, 'sfp_tool_wappalyzer', None)
        self.module.setTarget(self.target)

    @patch('modules.sfp_tool_wappalyzer.requests.get')
    @patch('modules.sfp_tool_wappalyzer.sfp_tool_wappalyzer.notifyListeners')
    def test_handleEvent_success(self, mock_notify, mock_get):
        opts = {
            'wappalyzer_api_key': 'FAKEKEY',
            'wappalyzer_api_url': 'https://api.wappalyzer.com/v2/lookup/'
        }
        self.module.setup(self.sf, opts)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{
            'technologies': [
                {'name': 'Apache', 'categories': [{'name': 'Web servers'}]},
                {'name': 'Linux', 'categories': [{'name': 'Operating systems'}]},
                {'name': 'jQuery', 'categories': [{'name': 'JavaScript frameworks'}]}
            ]
        }]
        mock_get.return_value = mock_resp
        self.module.handleEvent(self.event)
        self.assertTrue(mock_notify.called)
        calls = [call[0][0].eventType for call in mock_notify.call_args_list]
        self.assertIn('WEBSERVER_TECHNOLOGY', calls)
        self.assertIn('OPERATING_SYSTEM', calls)
        self.assertIn('SOFTWARE_USED', calls)

    @patch('modules.sfp_tool_wappalyzer.requests.get')
    def test_handleEvent_api_error(self, mock_get):
        opts = {
            'wappalyzer_api_key': 'FAKEKEY',
            'wappalyzer_api_url': 'https://api.wappalyzer.com/v2/lookup/'
        }
        self.module.setup(self.sf, opts)
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = 'Forbidden'
        mock_get.return_value = mock_resp
        self.module.handleEvent(self.event)
        self.assertTrue(self.module.errorState or not self.module.results[self.target_value])

    def test_handleEvent_no_api_key(self):
        opts = {'wappalyzer_api_key': ''}
        self.module.setup(self.sf, opts)
        self.module.handleEvent(self.event)
        self.assertTrue(self.module.errorState)

    @patch('modules.sfp_tool_wappalyzer.requests.get')
    def test_handleEvent_no_technologies(self, mock_get):
        opts = {
            'wappalyzer_api_key': 'FAKEKEY',
            'wappalyzer_api_url': 'https://api.wappalyzer.com/v2/lookup/'
        }
        self.module.setup(self.sf, opts)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{}]
        mock_get.return_value = mock_resp
        self.module.handleEvent(self.event)
        self.assertFalse(self.module.errorState)

# End of API unit tests
