import unittest
from modules.sfp_bluesky import sfp_bluesky
from spiderfoot import SpiderFootEvent

class TestSfpBlueskyIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_bluesky()
        self.plugin.setup(None, {})

    def test_produced_event_type(self):
        self.assertIn('BLUESKY_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
