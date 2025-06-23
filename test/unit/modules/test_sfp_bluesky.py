import unittest
from modules.sfp_bluesky import sfp_bluesky
from spiderfoot import SpiderFootEvent

class TestSfpBluesky(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_bluesky()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('access_token', self.plugin.opts)
        self.assertIn('username', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('BLUESKY_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
