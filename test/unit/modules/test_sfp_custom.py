import pytest
import unittest

from modules.sfp_custom import sfp_custom
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleCustom(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_custom()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_custom()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_custom()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_custom()
        self.assertIsInstance(module.producedEvents(), list)
