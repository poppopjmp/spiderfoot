import unittest
from unittest.mock import patch, MagicMock
from modules.sfp_telegram import sfp_telegram
from spiderfoot import SpiderFootEvent
from test.unit.utils.test_base import SpiderFootTestBase

class TestModuleTelegram(SpiderFootTestBase):
    def setUp(self):
        super().setUp()
        self.module = sfp_telegram()
        self.default_opts = {
            "api_id": "12345",
            "api_hash": "fakehash",
            "channels": "@testchannel",
            "poll_interval": 1,
            "max_messages": 2
        }
        self.sf_instance = self.scanner  # Fix: provide sf_instance for module.setup

    @patch("modules.sfp_telegram.TelegramClient")
    def test_start_and_poll(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_entity = MagicMock()
        # Message 1: should be filtered out by keyword
        mock_msg1 = MagicMock(id=1, sender_id=100, text="Hello", sender=MagicMock(username="user1"))
        # Message 2: should pass keyword filter and be tagged as high severity
        mock_msg2 = MagicMock(id=2, sender_id=101, text="Phishing alert!", sender=MagicMock(username="user2"))
        mock_client.get_entity.return_value = mock_entity
        mock_client.get_messages.return_value = [mock_msg1, mock_msg2]
        opts = self.default_opts.copy()
        opts["filter_keywords"] = "phishing"
        opts["severity_keywords"] = "phishing:high,scam:medium"
        self.module.setup(self.sf_instance, opts)
        self.module.notifyListeners = MagicMock()
        with patch.object(self.module, "_stop_event", wraps=self.module._stop_event) as mock_stop_event:
            mock_stop_event.is_set.side_effect = [False, True]
            self.module._client = mock_client
            self.module._poll_channels(["@testchannel"], 0, 2)
        # Only the second message should emit an event
        self.assertEqual(self.module.notifyListeners.call_count, 1)
        evt = self.module.notifyListeners.call_args[0][0]
        self.assertIsInstance(evt, SpiderFootEvent)
        self.assertEqual(evt.eventType, "TELEGRAM_MESSAGE")
        self.assertIn("Phishing alert!", evt.data)
        self.assertIn("Severity: high", evt.data)
        self.assertIn("user2", evt.data)

    def test_deduplication(self):
        # Test that duplicate message IDs are not emitted twice
        mock_client = MagicMock()
        mock_entity = MagicMock()
        mock_msg = MagicMock(id=1, sender_id=100, text="Test", sender=MagicMock(username="user1"))
        mock_client.get_entity.return_value = mock_entity
        mock_client.get_messages.return_value = [mock_msg]
        self.module.setup(self.sf_instance, self.default_opts)
        self.module.notifyListeners = MagicMock()
        with patch.object(self.module, "_stop_event", wraps=self.module._stop_event) as mock_stop_event:
            mock_stop_event.is_set.side_effect = [False, True]
            self.module._client = mock_client
            self.module._poll_channels(["@testchannel"], 0, 2)
        # First poll emits
        self.assertEqual(self.module.notifyListeners.call_count, 1)
        # Second poll with same message should not emit
        self.module.notifyListeners.reset_mock()
        with patch.object(self.module, "_stop_event", wraps=self.module._stop_event) as mock_stop_event:
            mock_stop_event.is_set.side_effect = [False, True]
            self.module._poll_channels(["@testchannel"], 0, 2)
        self.assertEqual(self.module.notifyListeners.call_count, 0)

    def test_setup_missing_opts(self):
        self.module.setup(self.sf_instance, {})
        self.assertTrue(self.module.errorState)

    @patch("modules.sfp_telegram.TelegramClient", None)
    def test_setup_no_telethon(self):
        self.module.setup(self.sf_instance, self.default_opts)
        self.assertTrue(self.module.errorState)

    @patch("modules.sfp_telegram.TelegramClient")
    def test_finish(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        self.module._client = mock_client
        self.module._thread = MagicMock(is_alive=MagicMock(return_value=False))
        self.module.finish()
        mock_client.disconnect.assert_called_once()

if __name__ == "__main__":
    unittest.main()
