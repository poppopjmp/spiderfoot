import unittest
from modules.sfp_whatsapp import sfp_whatsapp
from spiderfoot import SpiderFootEvent

class TestSfpWhatsAppIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_whatsapp()
        self.plugin.setup(None, {
            'api_key': 'dummy',
            'phone_numbers': '1234567890',
            'max_messages': 1
        })

    def test_produced_event_type(self):
        self.assertIn('WHATSAPP_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))
