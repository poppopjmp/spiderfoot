# filepath: spiderfoot/test/unit/modules/test_sfp_threatjammer.py
from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_threatjammer import sfp_threatjammer
import unittest
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion

"""
Test module for sfp_threatjammer.
This module contains unit tests for the Threatjammer SpiderFoot plugin.
"""

class TestModuleThreatjammer(SpiderFootTestBase):
    """Test Threatjammer module."""

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_threatjammer()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  test_opts(self):
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

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
