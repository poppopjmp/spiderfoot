import unittest
from unittest.mock import patch, MagicMock
from modules.sfp_ai_summary import sfp_ai_summary
from spiderfoot import SpiderFootEvent
from test.unit.utils.test_base import SpiderFootTestBase

class TestAIsummary(SpiderFootTestBase):
    def setUp(self):
        super().setUp()
        self.module = sfp_ai_summary()
        self.default_opts = {
            "api_key": "testkey",
            "model": "gpt-3.5-turbo",
            "summary_frequency": "on_finish",
            "max_events": 5
        }
        self.sf_instance = self.scanner

    @patch("openai.ChatCompletion.create")
    def test_summarize_events(self, mock_create):
        mock_create.return_value = MagicMock(choices=[MagicMock(message={"content": "Summary text."})])
        self.module.setup(self.sf_instance, self.default_opts)
        for i in range(3):
            event = SpiderFootEvent("TEST_EVENT", f"data {i}", "tester", None)
            self.module.handleEvent(event)
        self.module.notifyListeners = MagicMock()
        self.module.scanFinished()
        self.module.notifyListeners.assert_called_once()
        evt = self.module.notifyListeners.call_args[0][0]
        self.assertEqual(evt.eventType, "THREAT_INTEL_SUMMARY")
        self.assertIn("Summary text", evt.data)
