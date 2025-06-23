import unittest
from spiderfoot import SpiderFootEvent
from modules.sfp_xiaohongshu import sfp_xiaohongshu

class TestSfpXiaohongshu(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_xiaohongshu()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('usernames', self.plugin.opts)
        self.assertIn('max_posts', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('XIAOHONGSHU_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
