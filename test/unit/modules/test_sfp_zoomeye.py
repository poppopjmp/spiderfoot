# filepath: spiderfoot/test/unit/modules/test_sfp_zoomeye.py
from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot.event import SpiderFootEvent
from modules.sfp_zoomeye import sfp_zoomeye
import unittest
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion
import json
import requests


class TestModuleZoomeye(SpiderFootTestBase):
    """Test Zoomeye module."""

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        self.sf = MagicMock()
        
        # Import and fix the module if needed
        import modules.sfp_zoomeye as zoomeye_module
        if not hasattr(zoomeye_module, 'sfp_zoomeye'):
            # Find the actual class in the module
            for attr_name in dir(zoomeye_module):
                attr = getattr(zoomeye_module, attr_name)
                if (isinstance(attr, type) and 
                    hasattr(attr, '__bases__') and
                    any('SpiderFootPlugin' in str(base) for base in attr.__bases__)):
                    setattr(zoomeye_module, 'sfp_zoomeye', attr)
                    if not hasattr(attr, '__name__'):
                        setattr(attr, '__name__', 'sfp_zoomeye')
                    break
        
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()

        # Create module wrapper class dynamically
        module_attributes = {
            'descr': "Description for sfp_zoomeye",
            # Add module-specific options
        }

        self.module_class = self.create_module_wrapper(
            sfp_zoomeye,
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

    def test_opts(self):
        """Test the module options."""
        module = self.module_class()
        self.assertTrue(set(module.optdescs.keys()).issubset(set(module.opts.keys())))

    def test_setup(self):
        """
        Test setup(self, sfc, userOpts=dict())
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_zoomeye()
        module.setup(sf, dict())

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)

    @patch('modules.sfp_zoomeye.requests.get')
    def test_query_handles_rate_limit(self, mock_get):
        module = self.module_class()
        module.setup(self.sf, {'api_key': 'DUMMY', 'delay': 0, 'max_pages': 1})
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = 'Rate limit'
        mock_get.return_value = mock_response
        result = module.query('example.com', 'web')
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    @patch('modules.sfp_zoomeye.requests.get')
    def test_query_handles_malformed_json(self, mock_get):
        module = self.module_class()
        module.setup(self.sf, {'api_key': 'DUMMY', 'delay': 0, 'max_pages': 1})
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError('Expecting value', '', 0)
        mock_get.return_value = mock_response
        result = module.query('example.com', 'web')
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    @patch('modules.sfp_zoomeye.requests.get')
    def test_query_handles_http_error(self, mock_get):
        module = self.module_class()
        module.setup(self.sf, {'api_key': 'DUMMY', 'delay': 0, 'max_pages': 1})
        mock_get.side_effect = requests.exceptions.RequestException('HTTP error')
        result = module.query('example.com', 'web')
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def test_handleEvent_partial_and_duplicate(self):
        sf = MagicMock()
        module = sfp_zoomeye()
        opts = dict(api_key='DUMMY_KEY', _fetchtimeout=15)
        module.setup(sf, opts)
        event = SpiderFootEvent('DOMAIN_NAME', 'example.com', 'test', None)
        # Simulate partial and duplicate data
        mock_response = [
            {'matches': [
                {'site': 'site1.com'},
                {'site': 'site1.com'},
                {'ip': '1.2.3.4'},
                {'domain': 'domain1.com'}
            ]}
        ]
        events = []
        module.notifyListeners = lambda e: events.append(e)
        with unittest.mock.patch.object(module, 'query', return_value=mock_response):
            module.handleEvent(event)
        types = [e.eventType for e in events]
        # Only one INTERNET_NAME for 'site1.com' should be emitted
        self.assertEqual(types.count('INTERNET_NAME'), 1)
        # For DOMAIN_NAME event, only INTERNET_NAME is emitted (not IP_ADDRESS or DOMAIN_NAME)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
