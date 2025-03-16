# filepath: spiderfoot/test/unit/modules/test_sfp_bambenek.py
from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_bambenek import sfp_bambenek
import unittest
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleBambenek(SpiderFootTestBase):
    """Test Bambenek module."""

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
            'descr': "Description for sfp_bambenek",
            # Add module-specific options
        }

        self.module_class = self.create_module_wrapper(
            sfp_bambenek,
            module_attributes=module_attributes
        )

        # Register mocks to be reset during tearDown
        self.register_mock(self.log_mock)
        
        # Register patchers for cleanup during tearDown
        self.register_patcher(patcher1)
        
        # Backup original methods before monkey patching
        self._original_logging_getLogger = logging.getLogger if hasattr(logging, 'getLogger') else None
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)
        # Register monkey patches for automatic restoration


    def tearDown(self):
        """Clean up after each test."""
        # Restore original methods after monkey patching
        if hasattr(self, '_original_logging_getLogger') and self._original_logging_getLogger is not None:
            logging.getLogger = self._original_logging_getLogger
        elif hasattr(logging, 'getLogger'):
            delattr(logging, 'getLogger')
            
        super().tearDown()

    def test_opts(self):
        """Test the module options."""
        module = self.module_class()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = self.module_class()
        module.setup(sf, self.default_options)
        self.assertIsNotNone(module.options)
        self.assertTrue('_debug' in module.options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        """Test the watchedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)
