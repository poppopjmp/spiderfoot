import unittest
from modules.sfp_xiaohongshu import sfp_xiaohongshu
from spiderfoot import SpiderFootEvent

class TestSfpXiaohongshuIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_xiaohongshu()
        self.plugin.setup(None, {
            'usernames': 'testuser',
            'max_posts': 1
        })

    def test_produced_event_type(self):
        self.assertIn('XIAOHONGSHU_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
