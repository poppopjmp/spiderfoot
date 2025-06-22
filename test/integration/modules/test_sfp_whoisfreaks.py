import unittest
from modules.sfp_whoisfreaks import sfp_whoisfreaks
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent


class TestModuleIntegrationWhoisfreaks(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 30,
            'api_key': 'DUMMY_KEY',
            '_socks1type': '',
            '_socks1addr': '',
            '_socks1port': '',
            '_socks1user': '',
            '_socks1pass': ''
        }
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_whoisfreaks()
        self.module.setup(self.sf, self.default_options)

    def test_handleEvent(self):
        import unittest.mock as mock
        mock_response = {'code': '200', 'content': '{}', 'result': 'mocked'}
        event = SpiderFootEvent(
            "EMAILADDR", "test@example.com", "testModule", None)
        with mock.patch.object(self.sf, 'fetchUrl', return_value=mock_response):
            self.module.handleEvent(event)
            self.assertFalse(self.module.errorState)

    def test_query(self):
        import unittest.mock as mock
        mock_response = {'code': '200', 'content': '{}', 'result': 'mocked'}
        with mock.patch.object(self.sf, 'fetchUrl', return_value=mock_response):
            result = self.module.query("test@example.com", "email")
            self.assertIsNotNone(result)

    def test_setup(self):
        userOpts = {"api_key": "test_api_key"}
        self.module.setup(self.sf, userOpts)
        self.assertEqual(self.module.opts["api_key"], "test_api_key")

    def test_watchedEvents(self):
        self.assertEqual(self.module.watchedEvents(), [
                         "COMPANY_NAME", "HUMAN_NAME", "EMAILADDR", "EMAILADDR_GENERIC"])

    def test_producedEvents(self):
        self.assertEqual(self.module.producedEvents(), [
                         "AFFILIATE_INTERNET_NAME", "AFFILIATE_DOMAIN_NAME"])
