import unittest
from modules.sfp_dideo import sfp_dideo
from spiderfoot import SpiderFootEvent

class TestSfpDideoIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_dideo()
        self.plugin.setup(None, {
            'keywords': 'test',
            'max_videos': 1
        })

    def test_produced_event_type(self):
        self.assertIn('DIDEO_VIDEO', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
