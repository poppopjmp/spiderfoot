import unittest
from spiderfoot import SpiderFootEvent
from modules.sfp_whatsapp import sfp_whatsapp

class TestSfpWhatsApp(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_whatsapp()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('api_key', self.plugin.opts)
        self.assertIn('phone_numbers', self.plugin.opts)
        self.assertIn('max_messages', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('WHATSAPP_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
