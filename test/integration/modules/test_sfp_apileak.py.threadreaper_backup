import unittest
from unittest.mock import patch, MagicMock
from modules.sfp_apileak import sfp_apileak
from spiderfoot import SpiderFootEvent
from test.unit.utils.test_base import SpiderFootTestBase

class IntegrationTestAPILLeak(SpiderFootTestBase):
    @patch("requests.get")
    def test_integration_leak(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"items": [{"html_url": "https://github.com/test/integrationleak"}]}
        )
        module = sfp_apileak()
        opts = {
            "github_token": "testtoken",
            "search_patterns": r"AKIA[0-9A-Z]{16}",
            "max_results": 2
        }
        module.setup(self.scanner, opts)
        module.notifyListeners = MagicMock()
        event = SpiderFootEvent("DOMAIN_NAME", "integration.com", "integration", None)
        module.handleEvent(event)
        module.notifyListeners.assert_called_once()
        evt = module.notifyListeners.call_args[0][0]
        self.assertEqual(evt.eventType, "API_KEY_LEAK")
        self.assertIn("github.com/test/integrationleak", evt.data)

if __name__ == "__main__":
    unittest.main()
