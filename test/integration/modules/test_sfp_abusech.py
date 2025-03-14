import unittest
from unittest.mock import patch
import requests
import time

from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_abusech import sfp_abusech
from sflib import SpiderFoot


class BaseTestModuleIntegration(unittest.TestCase):

    def setUp(self):
        self.sf = SpiderFoot(self.default_options)
        self.module = self.module_class()
        self.module.setup(self.sf, dict())

    def requests_get_with_retries(self, url, timeout, retries=3, backoff_factor=0.3):
        for i in range(retries):
            try:
                response = requests.get(url, timeout=timeout)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if i < retries - 1:
                    time.sleep(backoff_factor * (2 ** i))
                else:
                    raise e

    def create_event(self, target_value, target_type, event_type, event_data):
        target = SpiderFootTarget(target_value, target_type)
        evt = SpiderFootEvent(event_type, event_data, '', '')
        return target, evt


class TestModuleIntegrationAbusech(BaseTestModuleIntegration):

    module_class = sfp_abusech

    @patch('modules.sfp_abusech.requests.get')
    def test_handleEvent_malicious_ip(self, mock_get):
        """Test handleEvent(mock_get) with a malicious IP address.

        Args:
            mock_get: Mock for requests.get
        """
        mock_get.side_effect = lambda url, timeout: self.requests_get_with_retries(
            url, timeout)

        target_value = '1.2.3.4'
        target_type = 'IP_ADDRESS'
        target, evt = self.create_event(target_value, target_type, 'ROOT', '')

        self.module.setTarget(target)
        self.module.handleEvent(evt)

        events = self.sf.getEvents()
        self.assertTrue(any(e.eventType == 'MALICIOUS_IPADDR' for e in events))
        malicious_ip_event = next(
            (e for e in events if e.eventType == 'MALICIOUS_IPADDR'), None)
        self.assertIsNotNone(malicious_ip_event)
        self.assertEqual(malicious_ip_event.data,
                         "1.2.3.4 (Malware: Example Malware)")

    @patch('modules.sfp_abusech.requests.get')
    def test_handleEvent_benign_ip(self, mock_get):
        """Test handleEvent(mock_get) with a benign IP address.

        Args:
            mock_get: Mock for requests.get
        """
        mock_get.side_effect = lambda url, timeout: self.requests_get_with_retries(
            url, timeout)

        target_value = '192.168.1.1'  # Example benign IP
        target_type = 'IP_ADDRESS'
        target, evt = self.create_event(target_value, target_type, 'ROOT', '')

        self.module.setTarget(target)
        self.module.handleEvent(evt)

        # Check that no MALICIOUS_IPADDR event was produced
        events = self.sf.getEvents()
        self.assertFalse(
            any(e.eventType == 'MALICIOUS_IPADDR' for e in events))

    @patch('modules.sfp_abusech.requests.get')
    def test_handleEvent_api_error(self, mock_get):
        """Test handleEvent(mock_get) when the API request returns an error.

        Args:
            mock_get: Mock for requests.get
        """
        mock_get.side_effect = lambda url, timeout: self.requests_get_with_retries(
            url, timeout)

        target_value = '1.2.3.4'
        target_type = 'IP_ADDRESS'
        target, evt = self.create_event(target_value, target_type, 'ROOT', '')

        self.module.setTarget(target)
        self.module.handleEvent(evt)

        # Check that no MALICIOUS_IPADDR event was produced
        events = self.sf.getEvents()
        self.assertFalse(
            any(e.eventType == 'MALICIOUS_IPADDR' for e in events))

        # Optionally, check if an error message was logged (using self.sf.debug())

    def test_handleEvent_invalid_target(self):
        """Test handleEvent() with an invalid target type."""
        target_value = 'example.com'
        target_type = 'INTERNET_NAME'  # Invalid target type for this module
        target, evt = self.create_event(target_value, target_type, 'ROOT', '')

        self.module.setTarget(target)
        self.module.handleEvent(evt)

        # Check that no events were produced
        events = self.sf.getEvents()
        self.assertEqual(len(events), 0)
