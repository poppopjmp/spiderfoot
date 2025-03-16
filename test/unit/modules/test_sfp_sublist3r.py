import pytest

"""
Test module for sfp_sublist3r.
This module contains unit tests for the Sublist3R SpiderFoot plugin.
"""
from modules.sfp_sublist3r import sfp_sublist3r
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModuleSublist3r(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_sublist3r()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_sublist3r()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_sublist3r()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_sublist3r()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_sublist3r()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  tearDown(self):
        """Clean up after each test."""
        super().tearDown()
