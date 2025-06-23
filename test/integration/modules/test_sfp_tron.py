import unittest
from modules.sfp_tron import sfp_tron
from spiderfoot import SpiderFootEvent

class TestSfpTronIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_tron()
        self.plugin.setup(None, {})

    def test_produced_event_type(self):
        self.assertIn('TRON_ADDRESS', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
