import unittest
from modules.sfp_wifimapio import sfp_wifimapio
from spiderfoot import SpiderFootEvent

class TestSfpWifiMapIoIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_wifimapio()
        self.plugin.setup(None, {})

    def test_produced_event_type(self):
        self.assertIn('WIFIMAPIO_HOTSPOT', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
