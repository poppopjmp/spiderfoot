import unittest
from modules.sfp_douyin import sfp_douyin
from spiderfoot import SpiderFootEvent

class TestSfpDouyinIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_douyin()
        self.plugin.setup(None, {
            'usernames': 'testuser',
            'max_videos': 1
        })

    def test_produced_event_type(self):
        self.assertIn('DOUYIN_VIDEO', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
