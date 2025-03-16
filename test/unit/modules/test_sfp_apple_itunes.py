"""Test module for sfp_apple_itunes.

This module contains unit tests for the Apple iTunes SpiderFoot plugin.
"""
import pytest

from modules.sfp_apple_itunes import sfp_apple_itunes
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModuleAppleItunes(SpiderFootTestBase):

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize default options
        self.default_options = self.default_options or {}
        # Initialize module
        self.module = sfp_apple_itunes()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)

    def test_opts(self):
        module = sfp_apple_itunes()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_apple_itunes()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_apple_itunes()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_apple_itunes()
        self.assertIsInstance(module.producedEvents(), list)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
