import unittest
from modules.sfp_mattermost import sfp_mattermost
from spiderfoot import SpiderFootEvent

class TestSfpMattermost(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_mattermost()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('access_token', self.plugin.opts)
        self.assertIn('server_url', self.plugin.opts)
        self.assertIn('channel_id', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('MATTERMOST_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
