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
            "search_patterns": r"AKIA[0-9A-Z]{16}",
            "max_results": 2
        }
        self.sf_instance = self.scanner

    @patch("requests.get")
    def test_handle_event(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"items": [{"html_url": "https://github.com/test/leak"}]}
        )
        self.module.setup(self.sf_instance, self.default_opts)
        self.module.notifyListeners = MagicMock()
        event = SpiderFootEvent("DOMAIN_NAME", "example.com", "tester", None)
        self.module.handleEvent(event)
        self.module.notifyListeners.assert_called_once()
        evt = self.module.notifyListeners.call_args[0][0]
        self.assertEqual(evt.eventType, "API_KEY_LEAK")
        self.assertIn("github.com/test/leak", evt.data)
