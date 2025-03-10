import pytest
import unittest

from modules.sfp__stor_stdout import sfp__stor_stdout
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleStor_stdout(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp__stor_stdout()
        self.assertEqual(len(module.opts), 12)

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp__stor_stdout()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp__stor_stdout()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp__stor_stdout()
        self.assertIsInstance(module.producedEvents(), list)
