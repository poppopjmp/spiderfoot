import pytest
import unittest

from modules.sfp_h1nobbdde import sfp_h1nobbdde
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleH1nobbdde(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_h1nobbdde()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_h1nobbdde()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_h1nobbdde()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_h1nobbdde()
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
