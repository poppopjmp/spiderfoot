import unittest
from unittest.mock import patch, MagicMock
from modules.sfp_ai_summary import sfp_ai_summary
from spiderfoot import SpiderFootEvent
from test.unit.utils.test_base import SpiderFootTestBase

class IntegrationTestAISummary(SpiderFootTestBase):
    @patch("openai.ChatCompletion.create")
    def test_integration_summary(self, mock_create):
        mock_create.return_value = MagicMock(choices=[MagicMock(message={"content": "Integration summary."})])
        module = sfp_ai_summary()
        opts = {
            "api_key": "testkey",
            "model": "gpt-3.5-turbo",
            "summary_frequency": "on_finish",
            "max_events": 5
        }
        module.setup(self.scanner, opts)
        module.notifyListeners = MagicMock()
        for i in range(2):
            event = SpiderFootEvent("INTEGRATION_EVENT", f"info {i}", "integration", None)
            module.handleEvent(event)
        module.scanFinished()
        module.notifyListeners.assert_called_once()
        evt = module.notifyListeners.call_args[0][0]
        self.assertEqual(evt.eventType, "THREAT_INTEL_SUMMARY")
        self.assertIn("Integration summary", evt.data)

if __name__ == "__main__":
    unittest.main()
