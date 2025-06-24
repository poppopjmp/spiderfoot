# filepath: spiderfoot/test/unit/modules/test_sfp_rocketreach.py
from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_rocketreach import sfp_rocketreach
import unittest
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion
from spiderfoot.target import SpiderFootTarget


class TestModuleRocketreach(SpiderFootTestBase):
    """Test Rocketreach module."""

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        self.sf = SpiderFoot(self.default_options)
        # Patch getTarget to return a real SpiderFootTarget with valid type
        self.sf.getTarget = lambda value, type_: SpiderFootTarget(value, "INTERNET_NAME" if type_ == "DOMAIN_NAME" else type_)
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()

        # Create module wrapper class dynamically
        module_attributes = {
            'descr': "Description for sfp_rocketreach",
            # Add module-specific options

        }

        self.module_class = self.create_module_wrapper(
            sfp_rocketreach,
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
        module = sfp_rocketreach()
        module.setup(sf, dict())
        self.assertIsNotNone(module.opts)
        self.assertTrue(hasattr(module, 'opts'))
        self.assertIsInstance(module.opts, dict)

    def test_watchedEvents_should_return_list(self):
        """Test the watchedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)

    @patch('modules.sfp_rocketreach.sfp_rocketreach.query')
    def test_handleEvent_emits_events(self, mock_query):
        module = sfp_rocketreach()
        module.setup(self.sf, {'api_key': 'DUMMY', '_fetchtimeout': 1})
        module.setTarget(self.sf.getTarget('example.com', 'DOMAIN_NAME'))
        event = SpiderFootEvent('DOMAIN_NAME', 'example.com', 'test', None)
        mock_query.return_value = {
            'results': [{
                'email': 'a@example.com',
                'emails': [{'email': 'b@example.com'}],
                'name': 'John Doe',
                'phone': '123',
                'phones': [{'number': '456'}],
                'linkedin_url': 'https://linkedin.com/in/test',
                'twitter_url': 'https://twitter.com/test',
                'facebook_url': 'https://facebook.com/test',
                'github_url': 'https://github.com/test',
            }]
        }
        events = []
        module.notifyListeners = lambda evt: events.append(evt)
        module.handleEvent(event)
        types = [e.eventType for e in events]
        self.assertIn('EMAILADDR', types)
        self.assertIn('PERSON_NAME', types)
        self.assertIn('PHONE_NUMBER', types)
        self.assertIn('SOCIAL_MEDIA', types)
        self.assertIn('RAW_RIR_DATA', types)
        # Deduplication: running again should not emit more events
        events2 = []
        module.notifyListeners = lambda evt: events2.append(evt)
        module.handleEvent(event)
        self.assertEqual(len(events2), 0)

    def test_handleEvent_no_api_key_sets_errorState(self):
        module = sfp_rocketreach()
        module.setup(self.sf, {'api_key': '', '_fetchtimeout': 1})
        module.setTarget(self.sf.getTarget('example.com', 'DOMAIN_NAME'))
        event = SpiderFootEvent('DOMAIN_NAME', 'example.com', 'test', None)
        module.handleEvent(event)
        self.assertTrue(module.errorState)

    @patch('modules.sfp_rocketreach.sfp_rocketreach.query')
    def test_handleEvent_invalid_response(self, mock_query):
        module = sfp_rocketreach()
        module.setup(self.sf, {'api_key': 'DUMMY', '_fetchtimeout': 1})
        module.setTarget(self.sf.getTarget('example.com', 'DOMAIN_NAME'))
        event = SpiderFootEvent('DOMAIN_NAME', 'example.com', 'test', None)
        mock_query.return_value = None
        module.notifyListeners = lambda evt: self.fail('Should not emit event')
        module.handleEvent(event)
        mock_query.return_value = {}
        module.handleEvent(event)
        mock_query.return_value = {'notresults': []}
        module.handleEvent(event)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
