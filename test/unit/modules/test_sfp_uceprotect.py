import pytest

"""
Test module for sfp_uceprotect.
This module contains unit tests for the Uceprotect SpiderFoot plugin.
"""
from modules.sfp_uceprotect import sfp_uceprotect
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModuleUceprotect(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_uceprotect()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_uceprotect()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_uceprotect()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_uceprotect()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_uceprotect()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  tearDown(self):
        """Clean up after each test."""
        super().tearDown()
