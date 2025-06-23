import unittest
from modules.sfp_arbitrum import sfp_arbitrum
from spiderfoot import SpiderFootEvent

class TestSfpArbitrumIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_arbitrum()
        self.plugin.setup(None, {})

    def test_produced_event_type(self):
        self.assertIn('ARBITRUM_ADDRESS', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
