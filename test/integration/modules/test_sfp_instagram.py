import unittest
from modules.sfp_instagram import sfp_instagram
from spiderfoot import SpiderFootEvent

class TestSfpInstagramIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_instagram()
        self.plugin.setup(None, {
            'access_token': 'dummy',
            'usernames': 'testuser',
            'max_items': 1
        })

    def test_produced_event_type(self):
        self.assertIn('INSTAGRAM_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
