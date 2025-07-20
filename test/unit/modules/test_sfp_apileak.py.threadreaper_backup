import unittest
from unittest.mock import patch, MagicMock
from modules.sfp_apileak import sfp_apileak
from spiderfoot import SpiderFootEvent
from test.unit.utils.test_base import SpiderFootTestBase

class TestAPILLeak(SpiderFootTestBase):
    def setUp(self):
        super().setUp()
        self.module = sfp_apileak()
        self.default_opts = {
            "github_token": "testtoken",
            "search_patterns": r"AKIA[0-9A-Z]{16},AIza[0-9A-Za-z-_]{35}",
            "max_results": 2,
            "fetch_file_content": True
        }
        self.sf_instance = self.scanner

    @patch("requests.get")
    def test_handle_event_api_key_leak(self, mock_get):
        def get_side_effect(url, headers=None, timeout=None):
            if url.startswith("https://api.github.com/search/code"):
                return MagicMock(
                    status_code=200,
                    json=lambda: {"items": [{"html_url": "https://github.com/test/leak", "url": "https://api.github.com/repos/test/leak/contents/file.txt"}]}
                )
            if url.startswith("https://api.github.com/repos/test/leak/contents/file.txt"):
                return MagicMock(
                    status_code=200,
                    json=lambda: {"content": "QUtJQVRFU1RBS0VZMTIzNDU2Nzg5MDEyMzQ1Ng=="}  # base64 for AKIATESTKEY1234567890123456
                )
            return MagicMock(status_code=404, json=lambda: {})
        mock_get.side_effect = get_side_effect
        self.module.setup(self.sf_instance, self.default_opts)
        self.module.notifyListeners = MagicMock()
        event = SpiderFootEvent("DOMAIN_NAME", "example.com", "tester", None)
        self.module.handleEvent(event)
        calls = [c[0][0].eventType for c in self.module.notifyListeners.call_args_list]
        self.assertIn("API_KEY_LEAK", calls)
        self.assertIn("CREDENTIAL_LEAK", calls)

    @patch("requests.get")
    def test_handle_event_no_token(self, mock_get):
        self.module.setup(self.sf_instance, {"github_token": ""})
        self.module.notifyListeners = MagicMock()
        event = SpiderFootEvent("DOMAIN_NAME", "example.com", "tester", None)
        self.module.handleEvent(event)
        self.module.notifyListeners.assert_not_called()

    @patch("requests.get")
    def test_handle_event_no_leaks(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"items": []})
        self.module.setup(self.sf_instance, self.default_opts)
        self.module.notifyListeners = MagicMock()
        event = SpiderFootEvent("DOMAIN_NAME", "example.com", "tester", None)
        self.module.handleEvent(event)
        self.module.notifyListeners.assert_not_called()

    @patch("requests.get")
    def test_handle_event_rate_limit(self, mock_get):
        mock_get.return_value = MagicMock(status_code=403, json=lambda: {})
        self.module.setup(self.sf_instance, self.default_opts)
        self.module.notifyListeners = MagicMock()
        event = SpiderFootEvent("DOMAIN_NAME", "example.com", "tester", None)
        self.module.handleEvent(event)
        self.module.notifyListeners.assert_not_called()
