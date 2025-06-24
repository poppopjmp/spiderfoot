import unittest
from unittest.mock import patch, MagicMock
from spiderfoot import SpiderFootEvent
from modules.sfp_discord import sfp_discord

class TestSfpDiscord(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_discord()
        opts = {
            'bot_token': 'dummy',
            'channel_ids': '1234567890,9876543210',
            'max_messages': 2
        }
        self.plugin.setup(None, opts)
        self.plugin.notifyListeners = MagicMock()

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('bot_token', self.plugin.opts)
        self.assertIn('channel_ids', self.plugin.opts)
        self.assertIn('max_messages', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('DISCORD_MESSAGE', self.plugin.producedEvents())

    @patch('modules.sfp_discord.requests.get')
    def test_handle_event_emits_events(self, mock_get):
        # Mock Discord API response with 2 messages for each channel
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {"id": "1", "content": "msg1", "author": {"username": "user1"}, "timestamp": "2024-01-01T00:00:00.000Z"},
            {"id": "2", "content": "msg2", "author": {"username": "user2"}, "timestamp": "2024-01-02T00:00:00.000Z"}
        ]
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        # 2 channels x 2 messages = 4 events
        self.assertEqual(self.plugin.notifyListeners.call_count, 4)
        args, _ = self.plugin.notifyListeners.call_args
        evt = args[0]
        self.assertEqual(evt.eventType, 'DISCORD_MESSAGE')
        self.assertIn('content', evt.data)
        self.assertIn('author', evt.data)

    @patch('modules.sfp_discord.requests.get')
    def test_handle_event_no_messages(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = []
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    @patch('modules.sfp_discord.requests.get')
    def test_handle_event_invalid_token(self, mock_get):
        mock_get.return_value.status_code = 401
        mock_get.return_value.text = 'Unauthorized'
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    @patch('modules.sfp_discord.requests.get')
    def test_handle_event_forbidden(self, mock_get):
        mock_get.return_value.status_code = 403
        mock_get.return_value.text = 'Forbidden'
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    @patch('modules.sfp_discord.requests.get')
    def test_handle_event_api_error(self, mock_get):
        mock_get.return_value.status_code = 500
        mock_get.return_value.text = 'Internal Server Error'
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()
