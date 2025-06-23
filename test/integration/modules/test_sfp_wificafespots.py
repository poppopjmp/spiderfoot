import unittest
from modules.sfp_wificafespots import sfp_wificafespots
from spiderfoot import SpiderFootEvent

class TestSfpWifiCafeSpotsIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_wificafespots()
        self.plugin.setup(None, {})

    def test_produced_event_type(self):
        self.assertIn('WIFICAFESPOTS_HOTSPOT', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
