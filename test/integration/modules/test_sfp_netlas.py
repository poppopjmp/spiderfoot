import unittest
from unittest.mock import patch
from modules.sfp_netlas import sfp_netlas
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleIntegrationNetlas(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_debug': False,
            '_useragent': 'SpiderFoot',
            '_dnsserver': '',
            '_fetchtimeout': 5,
            '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
            '_internettlds_cache': 72,
            '_genericusers': '',
            '_socks1type': '',
            '_socks2addr': '',
            '_socks3port': '',
            '_socks4user': '',
            '_socks5pwd': '',
        }
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_netlas()
        self.module.setup(self.sf, dict())
        self.module.opts.update(self.default_options)
        self.module.__name__ = "sfp_netlas"

    def test_setup(self):
        module = sfp_netlas()
        module.setup(self.sf, dict())
        self.assertIsInstance(module, sfp_netlas)

    def test_watchedEvents(self):
        module = sfp_netlas()
        module.setup(self.sf, dict())
        self.assertEqual(module.watchedEvents(), [
                         "DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"])

    @patch("modules.sfp_netlas.sfp_netlas.notifyListeners")
    @patch("sflib.SpiderFoot.fetchUrl")
    def test_handleEvent(self, mock_fetchUrl, mock_notifyListeners):
        self.module.opts['api_key'] = 'test_api_key'
        # Mock Netlas API response
        mock_fetchUrl.return_value = {
            'code': '200',
            'content': '{"geoinfo": "Test Geo", "latitude": 1.23, "longitude": 4.56}'
        }
        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'test_module'
        source_event = SpiderFootEvent(event_type, event_data, event_module, None)

        self.module.handleEvent(source_event)

        calls = [call[0][0].eventType for call in mock_notifyListeners.call_args_list]
        assert 'RAW_RIR_DATA' in calls
        assert 'GEOINFO' in calls
        self.assertTrue(self.module.results)
