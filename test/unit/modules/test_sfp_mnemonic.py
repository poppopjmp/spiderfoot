import pytest

"""
Test module for sfp_mnemonic.
This module contains unit tests for the Mnemonic SpiderFoot plugin.
"""
from modules.sfp_mnemonic import sfp_mnemonic
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModuleMnemonic(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_mnemonic()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_mnemonic()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_mnemonic()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_mnemonic()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_mnemonic()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  tearDown(self):
        """Clean up after each test."""
        super().tearDown()
