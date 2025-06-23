import unittest
from spiderfoot import SpiderFootEvent
from modules.sfp_reddit import sfp_reddit

class TestSfpReddit(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_reddit()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('client_id', self.plugin.opts)
        self.assertIn('client_secret', self.plugin.opts)
        self.assertIn('subreddits', self.plugin.opts)
        self.assertIn('max_posts', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('REDDIT_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
