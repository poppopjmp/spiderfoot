import unittest
from unittest.mock import patch, MagicMock
from modules.sfp_telegram import sfp_telegram
from spiderfoot import SpiderFootEvent
from test.unit.utils.test_base import SpiderFootTestBase

class IntegrationTestTelegramPlugin(SpiderFootTestBase):
    def setUp(self):
        super().setUp()
        self.sf_instance = self.scanner  # Fix: provide sf_instance for module.setup

    @patch("modules.sfp_telegram.TelegramClient")
    def test_integration_event_emission(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_entity = MagicMock()
        mock_msg = MagicMock(id=1, sender_id=100, text="Integration test message")
        mock_client.get_entity.return_value = mock_entity
        mock_client.get_messages.return_value = [mock_msg]
        module = sfp_telegram()
        opts = {
            "api_id": "12345",
            "api_hash": "fakehash",
            "channels": "@integrationchannel",
            "poll_interval": 1,
            "max_messages": 1
        }
        module.setup(self.sf_instance, opts)
        module.notifyListeners = MagicMock()
        with patch.object(module, "_stop_event", wraps=module._stop_event) as mock_stop_event:
            mock_stop_event.is_set.side_effect = [False, True]
            module._client = mock_client
            module._poll_channels(["@integrationchannel"], 0, 1)
        module.notifyListeners.assert_called_once()
        evt = module.notifyListeners.call_args[0][0]
        self.assertIsInstance(evt, SpiderFootEvent)
        self.assertEqual(evt.eventType, "TELEGRAM_MESSAGE")

if __name__ == "__main__":
    unittest.main()
