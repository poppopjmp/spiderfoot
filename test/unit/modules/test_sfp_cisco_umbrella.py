# filepath: spiderfoot/test/unit/modules/test_sfp_cisco_umbrella.py
from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
import unittest
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion

# Import fix before importing the module
from spiderfoot.helpers import fix_module_for_tests
fix_module_for_tests('sfp_cisco_umbrella')

from modules.sfp_cisco_umbrella import sfp_cisco_umbrella


class TestModuleCiscoUmbrella(SpiderFootTestBase):
    """Test Cisco Umbrella module."""

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
            'descr': "Description for sfp_cisco_umbrella",
            # Add module-specific options

        }

        self.module_class = self.create_module_wrapper(
            sfp_cisco_umbrella,
            module_attributes=module_attributes
        )
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)
        # Register mocks for cleanup during tearDown
        self.register_mock(self.mock_logger)        # Register patchers for cleanup during tearDown
        if 'patcher1' in locals():
            self.register_patcher(patcher1)

    def test_opts(self):
        """Test the module options."""
        module = self.module_class()
        self.assertEqual(set(module.opts.keys()), set(module.optdescs.keys()))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_cisco_umbrella()
        module.__name__ = "sfp_cisco_umbrella"
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        """Test the watchedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
