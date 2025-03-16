import pytest

"""
Test module for sfp_junkfiles.
This module contains unit tests for the Junkfiles SpiderFoot plugin.
"""
from modules.sfp_junkfiles import sfp_junkfiles
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModuleJunkfiles(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_junkfiles()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_junkfiles()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_junkfiles()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_junkfiles()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_junkfiles()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  tearDown(self):
        """Clean up after each test."""
        super().tearDown()
