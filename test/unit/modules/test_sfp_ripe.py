import pytest

"""
Test module for sfp_ripe.
This module contains unit tests for the Ripe SpiderFoot plugin.
"""
from modules.sfp_ripe import sfp_ripe
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModuleRipe(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_ripe()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_ripe()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_ripe()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_ripe()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_ripe()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  tearDown(self):
        """Clean up after each test."""
        super().tearDown()
