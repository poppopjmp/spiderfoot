import pytest
import unittest

from modules.sfp_talosintel import sfp_talosintel
from sflib import SpiderFoot
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleTalosintel(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_talosintel()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_talosintel()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_talosintel()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_talosintel()
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
