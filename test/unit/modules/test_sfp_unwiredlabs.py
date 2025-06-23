import unittest
from modules.sfp_unwiredlabs import sfp_unwiredlabs
from spiderfoot import SpiderFootEvent

class TestSfpUnwiredLabs(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_unwiredlabs()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('api_key', self.plugin.opts)
        self.assertIn('search_type', self.plugin.opts)
        self.assertIn('search_value', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('UNWIREDLABS_GEOINFO', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
