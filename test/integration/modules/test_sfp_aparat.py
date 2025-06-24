import unittest
from modules.sfp_aparat import sfp_aparat
from spiderfoot import SpiderFootEvent

class TestSfpAparatIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_aparat()
        self.plugin.setup(None, {
            'usernames': 'testuser',
            'max_videos': 1
        })

    def test_produced_event_type(self):
        self.assertIn('APARAT_VIDEO', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
