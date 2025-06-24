import unittest
from modules.sfp_discord import sfp_discord
from spiderfoot import SpiderFootEvent

class TestSfpDiscordIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_discord()
        self.plugin.setup(None, {
            'bot_token': 'dummy',
            'channel_ids': '1234567890',
            'max_messages': 1
        })

    def test_produced_event_type(self):
        self.assertIn('DISCORD_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
