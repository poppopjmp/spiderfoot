import pytest
import unittest

from modules.sfp_whois import sfp_whois
from sflib import SpiderFoot


@pytest.mark.usefixtures
class TestModuleWhois(unittest.TestCase):

    @property
    def watchedEvents(self):
        return ["DOMAIN_NAME", "DOMAIN_NAME_PARENT", "AFFILIATE_DOMAIN_NAME"]

    @property
    def producedEvents(self):
        return ["DOMAIN_WHOIS", "AFFILIATE_DOMAIN_WHOIS", "RAW_DATA"]

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
        module = sfp_whois()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_whois()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_whois()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_whois()
        self.assertIsInstance(module.producedEvents(), list)
