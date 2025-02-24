import unittest
from unittest.mock import patch

from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_abusech import sfp_abusech
from sflib import SpiderFoot


class TestModuleIntegrationAbusech(unittest.TestCase):

    def setUp(self):
        self.sf = SpiderFoot(self.default_options) 
        self.module = sfp_abusech()
        self.module.setup(self.sf, dict())

    @patch('modules.sfp_abusech.requests.get')
    def test_handleEvent_malicious_ip(self, mock_get):
        """
        Test handleEvent(mock_get) with a malicious IP address.
        """
        mock_response_data = {
            "ip": "1.2.3.4",
            "malware": "Example Malware",
            "firstseen": "2023-01-01",
        }
        mock_get.return_value.json.return_value = mock_response_data

        target_value = '1.2.3.4'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent('ROOT', '', '', '')
        self.module.handleEvent(evt)

        events = self.sf.getEvents()
        self.assertTrue(any(e.eventType == 'MALICIOUS_IPADDR' for e in events))
        malicious_ip_event = next((e for e in events if e.eventType == 'MALICIOUS_IPADDR'), None)
        self.assertIsNotNone(malicious_ip_event)
        self.assertEqual(malicious_ip_event.data, "1.2.3.4 (Malware: Example Malware)")

    @patch('modules.sfp_abusech.requests.get')
    def test_handleEvent_benign_ip(self, mock_get):
        """
        Test handleEvent(mock_get) with a benign IP address.
        """
        mock_get.return_value.json.return_value = None  # No data for benign IP

        target_value = '192.168.1.1'  # Example benign IP
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent('ROOT', '', '', '')
        self.module.handleEvent(evt)

        # Check that no MALICIOUS_IPADDR event was produced
        events = self.sf.getEvents()
        self.assertFalse(any(e.eventType == 'MALICIOUS_IPADDR' for e in events))

    @patch('modules.sfp_abusech.requests.get')
    def test_handleEvent_api_error(self, mock_get):
        """
        Test handleEvent(mock_get) when the API request returns an error.
        """
        mock_get.return_value.status_code = 500  # Simulate an API error

        target_value = '1.2.3.4'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent('ROOT', '', '', '')
        self.module.handleEvent(evt)

        # Check that no MALICIOUS_IPADDR event was produced
        events = self.sf.getEvents()
        self.assertFalse(any(e.eventType == 'MALICIOUS_IPADDR' for e in events))

        # Optionally, check if an error message was logged (using self.sf.debug())

    def test_handleEvent_invalid_target(self):
        """
        Test handleEvent() with an invalid target type.
        """
        target_value = 'example.com'
        target_type = 'INTERNET_NAME'  # Invalid target type for this module
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent('ROOT', '', '', '')
        self.module.handleEvent(evt)

        # Check that no events were produced
        events = self.sf.getEvents()
        self.assertEqual(len(events), 0)
