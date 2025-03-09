import pytest
import unittest

from modules.sfp_h1nobbdde import sfp_h1nobbdde
from sflib import SpiderFoot
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleH1nobbdde(SpiderFootModuleTestCase):

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
