import unittest
from spiderfoot import SpiderFootEvent
from modules.sfp_dideo import sfp_dideo

class TestSfpDideo(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_dideo()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('keywords', self.plugin.opts)
        self.assertIn('max_videos', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('DIDEO_VIDEO', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
