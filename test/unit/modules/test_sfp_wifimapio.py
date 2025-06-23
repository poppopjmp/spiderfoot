import unittest
from modules.sfp_wifimapio import sfp_wifimapio
from spiderfoot import SpiderFootEvent

class TestSfpWifiMapIo(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_wifimapio()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('search_term', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('WIFIMAPIO_HOTSPOT', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
