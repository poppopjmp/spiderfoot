import unittest
from modules.sfp_bnb import sfp_bnb
from spiderfoot import SpiderFootEvent

class TestSfpBNB(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_bnb()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        for opt in [
            'api_key', 'addresses', 'max_transactions',
            'start_block', 'end_block', 'min_value', 'event_types', 'output_format']:
            self.assertIn(opt, self.plugin.opts)

    def test_opts_defaults(self):
        self.assertEqual(self.plugin.opts['start_block'], 0)
        self.assertEqual(self.plugin.opts['end_block'], 0)
        self.assertEqual(self.plugin.opts['min_value'], 0.0)
        self.assertEqual(self.plugin.opts['event_types'], 'transfer,contract')
        self.assertEqual(self.plugin.opts['output_format'], 'summary')

    def test_produced_events(self):
        self.assertIn('BNB_ADDRESS', self.plugin.producedEvents())
        self.assertIn('BNB_TX', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))
