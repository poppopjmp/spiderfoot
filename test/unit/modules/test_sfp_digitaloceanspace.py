import pytest

"""
Test module for sfp_digitaloceanspace.
This module contains unit tests for the Digitaloceanspace SpiderFoot plugin.
"""
from modules.sfp_digitaloceanspace import sfp_digitaloceanspace
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModuleDigitaloceanspace(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_digitaloceanspace()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_digitaloceanspace()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_digitaloceanspace()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_digitaloceanspace()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_digitaloceanspace()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  tearDown(self):
        """Clean up after each test."""
        super().tearDown()
