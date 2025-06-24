import unittest
from unittest.mock import patch, MagicMock
from spiderfoot import SpiderFootEvent
from modules.sfp_4chan import sfp_4chan

class TestSfp4chan(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_4chan()
        self.plugin.setup(MagicMock(), {'boards': 'testboard', 'max_threads': 1})
        self.event = SpiderFootEvent('ROOT', 'test', 'test', None)

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('boards', self.plugin.opts)
        self.assertIn('max_threads', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('FOURCHAN_POST', self.plugin.producedEvents())

    @patch('modules.sfp_4chan.requests.get')
    def test_handle_event_emits_event(self, mock_get):
        # Mock catalog response
        mock_catalog = MagicMock()
        mock_catalog.status_code = 200
        mock_catalog.json.return_value = [{
            'threads': [{'no': 12345}]
        }]
        # Mock thread response
        mock_thread = MagicMock()
        mock_thread.status_code = 200
        mock_thread.json.return_value = {
            'posts': [{
                'no': 1,
                'sub': 'Test Subject',
                'com': 'Test Comment',
                'name': 'Anon',
                'time': 1234567890
            }]
        }
        mock_get.side_effect = [mock_catalog, mock_thread]
        self.plugin.notifyListeners = MagicMock()
        self.plugin.handleEvent(self.event)
        self.plugin.notifyListeners.assert_called()
        args, _ = self.plugin.notifyListeners.call_args
        event = args[0]
        self.assertEqual(event.eventType, 'FOURCHAN_POST')
        self.assertIn('Test Subject', event.data)
        self.assertIn('Test Comment', event.data)

    @patch('modules.sfp_4chan.requests.get')
    def test_handle_event_network_error(self, mock_get):
        mock_get.side_effect = Exception('Network error')
        self.plugin.sf.error = MagicMock()
        self.plugin.handleEvent(self.event)
        self.plugin.sf.error.assert_called()

    @patch('modules.sfp_4chan.requests.get')
    def test_handle_event_duplicate_post(self, mock_get):
        # Mock catalog and thread with same post twice
        mock_catalog = MagicMock()
        mock_catalog.status_code = 200
        mock_catalog.json.return_value = [{
            'threads': [{'no': 12345}]
        }]
        mock_thread = MagicMock()
        mock_thread.status_code = 200
        mock_thread.json.return_value = {
            'posts': [{
                'no': 1,
                'sub': 'Test Subject',
                'com': 'Test Comment',
                'name': 'Anon',
                'time': 1234567890
            }, {
                'no': 1,
                'sub': 'Test Subject',
                'com': 'Test Comment',
                'name': 'Anon',
                'time': 1234567890
            }]
        }
        mock_get.side_effect = [mock_catalog, mock_thread]
        self.plugin.notifyListeners = MagicMock()
        self.plugin.handleEvent(self.event)
        # Only one event should be emitted for the duplicate post
        self.assertEqual(self.plugin.notifyListeners.call_count, 1)
