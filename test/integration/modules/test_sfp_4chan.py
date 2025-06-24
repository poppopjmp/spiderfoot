import unittest
from unittest.mock import patch, MagicMock
from modules.sfp_4chan import sfp_4chan
from spiderfoot import SpiderFootEvent

class TestSfp4chanIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_4chan()
        self.plugin.setup(MagicMock(), {
            'boards': 'testboard',
            'max_threads': 1
        })
        self.event = SpiderFootEvent('ROOT', 'integration', 'integration', None)

    @patch('modules.sfp_4chan.requests.get')
    def test_integration_event_emission(self, mock_get):
        # Simulate catalog and thread API responses
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
                'sub': 'Integration Subject',
                'com': 'Integration Comment',
                'name': 'IntegrationUser',
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
        self.assertIn('Integration Subject', event.data)
        self.assertIn('Integration Comment', event.data)

    @patch('modules.sfp_4chan.requests.get')
    def test_integration_network_error(self, mock_get):
        mock_get.side_effect = Exception('Network error')
        self.plugin.sf.error = MagicMock()
        self.plugin.handleEvent(self.event)
        self.plugin.sf.error.assert_called()
