import unittest
from modules.sfp_wechat import sfp_wechat
from spiderfoot import SpiderFootEvent

class TestSfpWeChatIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_wechat()
        self.plugin.setup(None, {
            'api_key': 'dummy',
            'user_ids': 'testuser',
            'max_messages': 1
        })

    def test_produced_event_type(self):
        self.assertIn('WECHAT_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
