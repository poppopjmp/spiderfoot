# filepath: spiderfoot/test/unit/modules/test_sfp_bambenek.py
from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_bambenek import sfp_bambenek
import unittest
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion

"""
Test module for sfp_bambenek.
This module contains unit tests for the Bambenek SpiderFoot plugin.
"""

class TestModuleBambenek(SpiderFootTestBase):
    """Test Bambenek module."""

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_bambenek()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  tearDown(self):
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
