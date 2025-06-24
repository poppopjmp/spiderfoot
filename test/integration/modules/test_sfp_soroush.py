import unittest
from modules.sfp_soroush import sfp_soroush
from spiderfoot import SpiderFootEvent

class TestSfpSoroushIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_soroush()
        self.plugin.setup(None, {
            'channel_ids': 'testchannel',
            'max_messages': 1
        })

    def test_produced_event_type(self):
        self.assertIn('SOROUSH_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
