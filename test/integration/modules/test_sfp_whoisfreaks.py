import unittest
from modules.sfp_whoisfreaks import sfp_whoisfreaks
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent

class TestModuleIntegrationWhoisfreaks(SpiderFootModuleTestCase):

    def setUp(self):
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_whoisfreaks()
        self.module.setup(self.sf, dict())

    def test_handleEvent(self):
        event = SpiderFootEvent("EMAILADDR", "test@example.com", "testModule", None)
        self.module.handleEvent(event)
        self.assertFalse(self.module.errorState)

    def test_query(self):
        result = self.module.query("test@example.com", "email")
        self.assertIsNotNone(result)

    def test_setup(self):
        userOpts = {"api_key": "test_api_key"}
        self.module.setup(self.sf, userOpts)
        self.assertEqual(self.module.opts["api_key"], "test_api_key")

    def test_watchedEvents(self):
        self.assertEqual(self.module.watchedEvents(), ["COMPANY_NAME", "HUMAN_NAME", "EMAILADDR", "EMAILADDR_GENERIC"])

    def test_producedEvents(self):
        self.assertEqual(self.module.producedEvents(), ["AFFILIATE_INTERNET_NAME", "AFFILIATE_DOMAIN_NAME"])
