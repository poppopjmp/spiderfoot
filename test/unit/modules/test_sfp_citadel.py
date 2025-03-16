import pytest

"""
Test module for sfp_citadel.
This module contains unit tests for the Citadel SpiderFoot plugin.
"""
from modules.sfp_citadel import sfp_citadel
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModulecitadel(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_citadel()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_citadel()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_citadel()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_citadel()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_citadel()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  tearDown(self):
        """Clean up after each test."""
        super().tearDown()
