import unittest
from modules.sfp_rocketchat import sfp_rocketchat
from spiderfoot import SpiderFootEvent

class TestSfpRocketChatIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_rocketchat()
        self.plugin.setup(None, {})

    def test_produced_event_type(self):
        self.assertIn('ROCKETCHAT_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
