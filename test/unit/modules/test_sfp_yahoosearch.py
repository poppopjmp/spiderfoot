import pytest
import unittest

from modules.sfp_yahoosearch import sfp_yahoosearch
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleYahoosearch(SpiderFootModuleTestCase, unittest.TestCase):

    @property
    def watchedEvents(self):
        return ["DOMAIN_NAME"]

    @property
    def producedEvents(self):
        return ["LINKED_URL_INTERNAL", "SEARCH_ENGINE_WEB_CONTENT"]

    @property
    def opts(self):
        return {
            # Add any necessary options here
        }
    
    def setUp(self):
        self.default_options = {
            # Add default options required by tests
        }

    def test_opts(self):
        module = sfp_yahoosearch()
        self.assertEqual(len(module.opts), 2)
        self.assertTrue('maxresults' in module.opts)
        self.assertTrue('fetchlinks' in module.opts)

    def test_setup(self):
        sf = unittest.mock.MagicMock()
        module = sfp_yahoosearch()
        module.setup(sf)
        self.assertEqual(module.__dataSource__, "Yahoo")

    def test_watchedEvents_should_return_list(self):
        module = sfp_yahoosearch()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_yahoosearch()
        self.assertIsInstance(module.producedEvents(), list)
