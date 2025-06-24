# filepath: spiderfoot/test/unit/modules/test_sfp_fofa.py
from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_fofa import sfp_fofa
import unittest
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleFofa(SpiderFootTestBase):
    """Test Fofa module."""

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()

        # Create module wrapper class dynamically
        module_attributes = {
            'descr': "Description for sfp_fofa",
            # Add module-specific options

        }

        self.module_class = self.create_module_wrapper(
            sfp_fofa,
            module_attributes=module_attributes
        )
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)
        # Register mocks for cleanup during tearDown
        self.register_mock(self.mock_logger)
        # Register patchers for cleanup during tearDown
        if 'patcher1' in locals():
            self.register_patcher(patcher1)

        self.sf = MagicMock()
        self.plugin = sfp_fofa()
        self.plugin.setup(self.sf, {'api_email': 'test@example.com', 'api_key': 'key', 'max_age_days': 30})
        self.plugin.notifyListeners = MagicMock()

    def test_opts(self):
        """Test the module options."""
        module = self.module_class()
        self.assertEqual(len(self.plugin.opts), len(self.plugin.optdescs))

    def test_setup(self):
        """
        Test setup(self, sfc, userOpts=dict())
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_fofa()
        module.setup(sf, dict())
        self.assertTrue(hasattr(module, 'opts'))

    def test_watchedEvents_should_return_list(self):
        """Test the watchedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_emits_events(self, mock_sleep):
        # Mock fetchUrl to return a valid Fofa response
        self.sf.fetchUrl.return_value = {
            'code': 200,
            'content': '{"results": [ {"host": "host1", "domain": "domain1", "ip": "1.2.3.4", "ipv6": "::1"}, {"host": "host2", "domain": "domain2", "ip": "1.2.3.5", "ipv6": "::2"} ]}'
        }
        event = SpiderFootEvent('DOMAIN_NAME', 'example.com', 'test', None)
        self.plugin.handleEvent(event)
        # 1 RAW_RIR_DATA + 2*4 unique events = 9
        self.assertEqual(self.plugin.notifyListeners.call_count, 9)
        # Check deduplication: duplicate values should not emit twice
        self.plugin.notifyListeners.reset_mock()
        self.plugin.handleEvent(event)  # Should skip as already checked
        self.plugin.notifyListeners.assert_not_called()

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_no_results(self, mock_sleep):
        self.sf.fetchUrl.return_value = {'code': 200, 'content': '{"results": []}'}
        event = SpiderFootEvent('DOMAIN_NAME', 'noresults.com', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_called_once()  # Only RAW_RIR_DATA

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_api_error(self, mock_sleep):
        self.sf.fetchUrl.return_value = {'code': 500, 'errmsg': 'API error', 'content': '{}'}
        event = SpiderFootEvent('DOMAIN_NAME', 'error.com', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_invalid_key(self, mock_sleep):
        plugin = sfp_fofa()
        plugin.setup(self.sf, {'api_email': '', 'api_key': '', 'max_age_days': 30})
        plugin.notifyListeners = MagicMock()
        event = SpiderFootEvent('DOMAIN_NAME', 'badkey.com', 'test', None)
        plugin.handleEvent(event)
        plugin.notifyListeners.assert_not_called()

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_malformed_json(self, mock_sleep):
        self.sf.fetchUrl.return_value = {'code': 200, 'content': '{notjson'}
        event = SpiderFootEvent('DOMAIN_NAME', 'badjson.com', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_partial_results(self, mock_sleep):
        # Only some fields present in results
        self.sf.fetchUrl.return_value = {
            'code': 200,
            'content': '{"results": [ {"host": "host1"}, {"ip": "1.2.3.4"}, {"domain": "domain1"}, {"ipv6": "::1"} ]}'
        }
        event = SpiderFootEvent('DOMAIN_NAME', 'partial.com', 'test', None)
        self.plugin.handleEvent(event)
        # 1 RAW_RIR_DATA + 4 unique events
        self.assertEqual(self.plugin.notifyListeners.call_count, 5)

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_duplicate_values(self, mock_sleep):
        # Duplicate values in results should not emit twice
        self.sf.fetchUrl.return_value = {
            'code': 200,
            'content': '{"results": [ {"host": "host1"}, {"host": "host1"} ]}'
        }
        event = SpiderFootEvent('DOMAIN_NAME', 'dupe.com', 'test', None)
        self.plugin.handleEvent(event)
        # 1 RAW_RIR_DATA + 1 unique event
        self.assertEqual(self.plugin.notifyListeners.call_count, 2)

    @patch('modules.sfp_fofa.time.sleep', return_value=None)
    def test_handle_event_rate_limit(self, mock_sleep):
        self.sf.fetchUrl.return_value = {'code': 429, 'errmsg': 'Rate limit', 'content': '{}'}
        event = SpiderFootEvent('DOMAIN_NAME', 'ratelimit.com', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
