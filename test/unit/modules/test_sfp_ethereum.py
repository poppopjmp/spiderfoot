import unittest
from modules.sfp_ethereum import sfp_ethereum


class TestSfpEthereum(unittest.TestCase):
    def setUp(self):
        self.valid_opts = {"api_key": "key", "addresses": "0x123", "max_transactions": 10, "output_format": "summary"}
        self.plugin = sfp_ethereum()
        self.plugin.setup(None, self.valid_opts)

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)

    def test_opts(self):
        for opt in [
            'api_key', 'addresses', 'max_transactions',
            'start_block', 'end_block', 'min_value', 'event_types', 'output_format']:
            self.assertIn(opt, self.plugin.opts)

    def test_opts_defaults(self):
        plugin = sfp_ethereum()
        plugin.setup(None, {"api_key": "key", "addresses": "0x123", "max_transactions": 10, "output_format": "summary"})
        self.assertEqual(plugin.opts['start_block'], 0)
        self.assertEqual(plugin.opts['end_block'], 0)
        self.assertEqual(plugin.opts['min_value'], 0.0)
        self.assertEqual(plugin.opts['event_types'], 'transfer,contract')
        self.assertEqual(plugin.opts['output_format'], 'summary')

    def test_produced_events(self):
        self.assertIn('ETHEREUM_ADDRESS', self.plugin.producedEvents())
        self.assertIn('ETHEREUM_TX', self.plugin.producedEvents())

    def test_option_validation(self):
        with self.assertRaises(ValueError):
            self.plugin.setup(None, {"api_key": "", "addresses": "0x123", "max_transactions": 10, "output_format": "summary"})
        with self.assertRaises(ValueError):
            self.plugin.setup(None, {"api_key": "key", "addresses": "", "max_transactions": 10, "output_format": "summary"})
        with self.assertRaises(ValueError):
            self.plugin.setup(None, {"api_key": "key", "addresses": "0x123", "max_transactions": 0, "output_format": "summary"})
        with self.assertRaises(ValueError):
            self.plugin.setup(None, {"api_key": "key", "addresses": "0x123", "max_transactions": 10, "output_format": "invalid"})

    def test_handle_event_stub(self):
        from spiderfoot import SpiderFootEvent
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
