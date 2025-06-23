import unittest
from modules.sfp_matrix import sfp_matrix
from spiderfoot import SpiderFootEvent

class TestSfpMatrix(unittest.TestCase):
    def setUp(self):
        self.valid_opts = {"access_token": "token", "room_id": "!room:id", "max_messages": 10, "output_format": "summary"}
        self.plugin = sfp_matrix()
        self.plugin.setup(None, self.valid_opts)

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)

    def test_opts(self):
        for opt in [
            'access_token', 'homeserver', 'room_id', 'event_types', 'since', 'max_messages', 'output_format']:
            self.assertIn(opt, self.plugin.opts)

    def test_opts_defaults(self):
        plugin = sfp_matrix()
        plugin.setup(None, self.valid_opts)
        self.assertEqual(plugin.opts['homeserver'], 'https://matrix.org')
        self.assertEqual(plugin.opts['event_types'], 'message,join,leave')
        self.assertEqual(plugin.opts['output_format'], 'summary')

    def test_produced_events(self):
        self.assertIn('MATRIX_MESSAGE', self.plugin.producedEvents())

    def test_option_validation(self):
        with self.assertRaises(ValueError):
            self.plugin.setup(None, {"access_token": "", "room_id": "!room:id", "max_messages": 10, "output_format": "summary"})
        with self.assertRaises(ValueError):
            self.plugin.setup(None, {"access_token": "token", "room_id": "", "max_messages": 10, "output_format": "summary"})
        with self.assertRaises(ValueError):
            self.plugin.setup(None, {"access_token": "token", "room_id": "!room:id", "max_messages": 0, "output_format": "summary"})
        with self.assertRaises(ValueError):
            self.plugin.setup(None, {"access_token": "token", "room_id": "!room:id", "max_messages": 10, "output_format": "invalid"})

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
