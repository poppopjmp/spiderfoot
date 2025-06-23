import unittest
from modules.sfp_mattermost import sfp_mattermost
from spiderfoot import SpiderFootEvent

class TestSfpMattermostIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_mattermost()
        self.plugin.setup(None, {})

    def test_produced_event_type(self):
        self.assertIn('MATTERMOST_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
