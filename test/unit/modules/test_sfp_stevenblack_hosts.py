import pytest
import unittest

from modules.sfp_stevenblack_hosts import sfp_stevenblack_hosts
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleStevenblackHosts(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_stevenblack_hosts()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_stevenblack_hosts()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_stevenblack_hosts()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_stevenblack_hosts()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
