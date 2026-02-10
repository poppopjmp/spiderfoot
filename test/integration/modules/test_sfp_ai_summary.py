from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
from modules.sfp_ai_summary import sfp_ai_summary
from spiderfoot import SpiderFootEvent
from test.unit.utils.test_module_base import TestModuleBase

class IntegrationTestAISummary(TestModuleBase):

    def setUp(self):
        """Enhanced setUp with ThreadReaper module tracking."""
        super().setUp()
        # ThreadReaper infrastructure is automatically initialized
        
    def tearDown(self):
        """Enhanced tearDown with ThreadReaper cleanup."""
        # ThreadReaper infrastructure automatically cleans up
        super().tearDown()
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
