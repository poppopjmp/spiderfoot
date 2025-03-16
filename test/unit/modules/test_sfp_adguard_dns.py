import pytest

"""
Test module for sfp_adguard_dns.
This module contains unit tests for the AdguardDns SpiderFoot plugin.
"""
from modules.sfp_adguard_dns import sfp_adguard_dns
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModuleAdGuardDns(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_adguard_dns()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_adguard_dns()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_adguard_dns()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_adguard_dns()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_adguard_dns()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  tearDown(self):
        """Clean up after each test."""
        super().tearDown()
