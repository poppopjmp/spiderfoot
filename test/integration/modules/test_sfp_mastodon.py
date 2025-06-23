import unittest
from modules.sfp_mastodon import sfp_mastodon
from spiderfoot import SpiderFootEvent

class TestSfpMastodonIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_mastodon()
        self.plugin.setup(None, {})

    def test_produced_event_type(self):
        self.assertIn('MASTODON_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
