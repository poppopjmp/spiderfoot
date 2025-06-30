import unittest
from unittest.mock import patch
from modules.sfp_luminar import sfp_luminar
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleLuminar(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFoot',
            '_dnsserver': '8.8.8.8',
            '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
            '_internettlds_cache': 72
        }
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_luminar()
        self.module.setup(self.sf, dict())
        # Ensure all required options are present in module.opts
        self.module.opts.update(self.default_options)
        self.module.__name__ = "sfp_luminar"

    @patch("modules.sfp_luminar.sfp_luminar.notifyListeners")
    @patch("sflib.SpiderFoot.fetchUrl")
    def test_handleEvent(self, mock_fetchUrl, mock_notifyListeners):
        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.sf.target = target

        event_type = 'INTERNET_NAME'
        event_data = 'example.com'
        event_module = 'test_module'
        source_event = SpiderFootEvent(event_type, event_data, event_module, None)

        self.module.opts['api_key'] = 'test_api_key'
        # Mock Luminar API response
        mock_fetchUrl.return_value = {
            'code': '200',
            'content': '{"data": [{"id": "threat-1", "description": "Test threat description."}]}'
        }

        self.module.handleEvent(source_event)

        # Assert that notifyListeners was called with a THREAT_INTELLIGENCE event
        calls = [call[0][0].eventType for call in mock_notifyListeners.call_args_list]
        assert 'THREAT_INTELLIGENCE' in calls
        self.assertTrue(self.module.results)

    @patch("sflib.SpiderFoot.fetchUrl")
    def test_query(self, mock_fetchUrl):
        self.module.opts['api_key'] = 'test_api_key'
        self.module.opts.update(self.default_options)
        mock_fetchUrl.return_value = {
            'code': '200',
            'content': '{"data": [{"id": "threat-1", "description": "Test threat description."}]}'
        }
        result = self.module.query('example.com')
        self.assertIsNotNone(result)

    def test_producedEvents(self):
        self.assertEqual(self.module.producedEvents(), ['THREAT_INTELLIGENCE'])

    def test_watchedEvents(self):
        self.assertEqual(self.module.watchedEvents(), ['DOMAIN_NAME', 'INTERNET_NAME', 'IP_ADDRESS'])


if __name__ == '__main__':
    unittest.main()
