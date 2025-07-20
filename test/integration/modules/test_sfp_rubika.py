import unittest
from test.unit.utils.test_module_base import TestModuleBase
from modules.sfp_rubika import sfp_rubika
from spiderfoot import SpiderFootEvent

class TestSfpRubikaIntegration(TestModuleBase):
    def setUp(self):
        self.plugin = sfp_rubika()
        self.plugin.setup(None, {
            'channel_ids': 'testchannel',
            'max_messages': 1
        })

    def test_produced_event_type(self):
        self.assertIn('RUBIKA_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
