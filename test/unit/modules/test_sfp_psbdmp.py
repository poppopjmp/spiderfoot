import pytest

"""
Test module for sfp_psbdmp.
This module contains unit tests for the Psbdmp SpiderFoot plugin.
"""
from modules.sfp_psbdmp import sfp_psbdmp
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModulePsbdmp(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_psbdmp()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_psbdmp()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_psbdmp()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_psbdmp()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_psbdmp()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  tearDown(self):
        """Clean up after each test."""
        super().tearDown()
