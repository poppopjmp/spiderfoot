import unittest
from unittest.mock import patch
from modules.sfp_recordedfuture import sfp_recordedfuture
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleRecordedFuture(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFoot',
            '_dnsserver': '8.8.8.8',
            '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
            '_internettlds_cache': 72
        }
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_recordedfuture()
        self.module.setup(self.sf, dict())
        self.module.opts.update(self.default_options)
        self.module.__name__ = "sfp_recordedfuture"

    @patch("modules.sfp_recordedfuture.sfp_recordedfuture.notifyListeners")
    @patch("sflib.SpiderFoot.fetchUrl")
    def test_handleEvent(self, mock_fetchUrl, mock_notifyListeners):
        self.module.opts['api_key'] = 'test_api_key'
        # Mock RecordedFuture API response (correct key: 'data')
        mock_fetchUrl.return_value = {
            'code': '200',
            'content': '{"data": [{"id": "CVE-2025-0001", "description": "Test vuln."}]}'
        }
        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.sf.target = target

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'test_module'
        source_event = SpiderFootEvent(event_type, event_data, event_module, None)

        self.module.handleEvent(source_event)

        calls = [call[0][0].eventType for call in mock_notifyListeners.call_args_list]
        assert 'VULNERABILITY_DISCLOSURE' in calls
        self.assertTrue(self.module.results)

    @patch("sflib.SpiderFoot.fetchUrl")
    def test_query(self, mock_fetchUrl):
        self.module.opts['api_key'] = 'test_api_key'
        self.module.opts.update(self.default_options)
        mock_fetchUrl.return_value = {
            'code': '200',
            'content': '{"data": [{"id": "CVE-2025-0001", "description": "Test vuln."}]}'
        }
        result = self.module.query('example.com')
        self.assertIsNotNone(result)

    def test_producedEvents(self):
        self.assertEqual(self.module.producedEvents(), ['VULNERABILITY_DISCLOSURE'])

    def test_watchedEvents(self):
        self.assertEqual(self.module.watchedEvents(), ['DOMAIN_NAME', 'INTERNET_NAME', 'IP_ADDRESS'])


if __name__ == '__main__':
    unittest.main()
