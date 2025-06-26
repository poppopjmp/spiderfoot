import unittest
from unittest.mock import patch, MagicMock
from modules.sfp_arbitrum import sfp_arbitrum
from spiderfoot import SpiderFootEvent

class TestSfpArbitrum(unittest.TestCase):
    def setUp(self):
        # Provide minimal valid options to pass validation
        self.valid_opts = {"api_key": "key", "addresses": "0x123", "max_transactions": 10, "output_format": "summary"}
        self.plugin = sfp_arbitrum()
        self.plugin.setup(None, self.valid_opts)

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)

    def test_opts(self):
        for opt in [
            'api_key', 'addresses', 'max_transactions',
            'start_block', 'end_block', 'min_value', 'event_types', 'output_format']:
            self.assertIn(opt, self.plugin.opts)

    def test_opts_defaults(self):
        plugin = sfp_arbitrum()
        plugin.setup(None, self.valid_opts)
        self.assertEqual(plugin.opts['start_block'], 0)
        self.assertEqual(plugin.opts['end_block'], 0)
        self.assertEqual(plugin.opts['min_value'], 0.0)
        self.assertEqual(plugin.opts['event_types'], 'transfer,contract')
        self.assertEqual(plugin.opts['output_format'], 'summary')

    def test_produced_events(self):
        self.assertIn('ARBITRUM_ADDRESS', self.plugin.producedEvents())
        self.assertIn('ARBITRUM_TX', self.plugin.producedEvents())

    def test_option_validation(self):
        with self.assertRaises(ValueError):
            self.plugin.setup(None, {"api_key": "", "addresses": "0x123", "max_transactions": 10, "output_format": "summary"})
        with self.assertRaises(ValueError):
            self.plugin.setup(None, {"api_key": "key", "addresses": "0x123", "max_transactions": 0, "output_format": "summary"})
        with self.assertRaises(ValueError):
            self.plugin.setup(None, {"api_key": "key", "addresses": "0x123", "max_transactions": 10, "output_format": "invalid"})

    @patch("requests.get")
    def test_handle_event_emits_events(self, mock_get):
        # Simulate Arbiscan API response with two transactions
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "status": "1",
                "result": [
                    {"from": "0xabc", "to": "0xdef", "value": str(int(1e18)), "hash": "0xhash1", "blockNumber": "100", "input": "0x"},
                    {"from": "0xghi", "to": "0xjkl", "value": str(int(2e18)), "hash": "0xhash2", "blockNumber": "101", "input": "0x"}
                ]
            }
        )
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        events = []
        self.plugin.notifyListeners = lambda evt: events.append(evt)
        self.plugin.handleEvent(event)
        tx_events = [e for e in events if e.eventType == 'ARBITRUM_TX']
        addr_events = [e for e in events if e.eventType == 'ARBITRUM_ADDRESS']
        self.assertEqual(len(tx_events), 2)
        self.assertEqual(len(addr_events), 1)
        self.assertIn('0x123', addr_events[0].data)
        self.assertIn('From: 0xabc', tx_events[0].data)
        self.assertIn('From: 0xghi', tx_events[1].data)

    @patch("requests.get")
    def test_handle_event_no_transactions(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"status": "0", "result": []})
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        events = []
        self.plugin.notifyListeners = lambda evt: events.append(evt)
        self.plugin.handleEvent(event)
        self.assertEqual(len(events), 0)

    @patch("requests.get")
    def test_handle_event_api_error(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500, json=lambda: {})
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        events = []
        self.plugin.notifyListeners = lambda evt: events.append(evt)
        self.plugin.handleEvent(event)
        self.assertEqual(len(events), 0)
