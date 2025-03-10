import unittest
from unittest.mock import patch, MagicMock
import sys
from sflib import SpiderFoot
from modules.sfp_sorbs import sfp_sorbs
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestModuleSorbs(SpiderFootModuleTestCase):
    """Test SORBS module."""

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
        self.module_class = self.create_module_wrapper(
            sfp_sorbs,
            module_attributes={
                '_databases': {
                    "ABUSE": "Determined to be an open abuse relay.",
                    "DUINV": "Dynamic IP that has a hostname in a domain that doesn't exist.",
                },
                'descr': "SORBS - Database of past and present spam sources.",
                'cohostcount': 0
            }
        )

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
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        """Test the watchedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)
