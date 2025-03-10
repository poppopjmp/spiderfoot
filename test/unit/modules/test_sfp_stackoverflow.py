import pytest
import unittest

from modules.sfp_stackoverflow import sfp_stackoverflow
from sflib import SpiderFoot
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

@pytest.mark.usefixtures
class TestModuleStackoverflow(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_stackoverflow()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_stackoverflow()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_stackoverflow()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_stackoverflow()
        self.assertIsInstance(module.producedEvents(), list)
