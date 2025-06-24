import unittest
from modules.sfp_4chan import sfp_4chan
from spiderfoot import SpiderFootEvent

class TestSfp4chanIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_4chan()
        self.plugin.setup(None, {
            'boards': 'pol',
            'max_threads': 1
        })

    def test_produced_event_type(self):
        self.assertIn('FOURCHAN_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
