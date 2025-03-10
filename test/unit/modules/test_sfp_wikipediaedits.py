import pytest
import unittest

from modules.sfp_wikipediaedits import sfp_wikipediaedits
from sflib import SpiderFoot


@pytest.mark.usefixtures
class TestModulewikipediaedits(unittest.TestCase):

    @property
    def watchedEvents(self):
        return ["IP_ADDRESS", "USERNAME"]

    @property
    def producedEvents(self):
        return ["WIKIPEDIA_PAGE_EDIT"]

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
        module = sfp_wikipediaedits()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_wikipediaedits()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_wikipediaedits()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_wikipediaedits()
        self.assertIsInstance(module.producedEvents(), list)
