import unittest
from modules.sfp_openwifimap import sfp_openwifimap
from spiderfoot import SpiderFootEvent

class TestSfpOpenWifiMapIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_openwifimap()
        self.plugin.setup(None, {'search_term': 'test'})

    def test_produced_event_type(self):
        self.assertIn('OPENWIFIMAP_HOTSPOT', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
