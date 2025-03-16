import pytest

"""
Test module for sfp_yandexdns.
This module contains unit tests for the Yandexdns SpiderFoot plugin.
"""
from modules.sfp_yandexdns import sfp_yandexdns
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModuleYandexdns(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_yandexdns()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_yandexdns()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_yandexdns()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_yandexdns()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Initialize module
        self.module = sfp_yandexdns()
        # Register event emitters if they exist
        self.register_event_emitter(self.module)
    def  tearDown(self):
        """Clean up after each test."""
        super().tearDown()
