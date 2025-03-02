import unittest
from unittest.mock import patch
import requests
import time

from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_abuseipdb import sfp_abuseipdb
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


class TestModuleIntegrationAbuseIPDB(BaseTestModuleIntegration):

    module_class = sfp_abuseipdb

    @patch('modules.sfp_abuseipdb.requests.get')
    def test_handleEvent_malicious_ip(self, mock_get):
        """
        Test handleEvent(mock_get) with a malicious IP address.
        Args:
            mock_get: Mock for requests.get
        """
        mock_response_data = {
            "data": {
                "ipAddress": "1.2.3.4",
                "abuseConfidenceScore": 90,
                "countryCode": "US",
                "usageType": "Data Center",
                "isp": "Example ISP",
                "domain": "example.com",
                "hostnames": ["host1.example.com", "host2.example.com"],
                "totalReports": 5,
                "lastReportedAt": "2023-10-26T12:00:00Z",
            }
        }
        mock_get.side_effect = lambda url, timeout: self.requests_get_with_retries(url, timeout)

        target_value = '1.2.3.4'
        target_type = 'IP_ADDRESS'
        target, evt = self.create_event(target_value, target_type, 'ROOT', '')

        self.module.setTarget(target)
        self.module.handleEvent(evt)

        events = self.sf.getEvents()
        self.assertTrue(any(e.eventType == 'MALICIOUS_IPADDR' for e in events))
        self.assertTrue(any(e.eventType == 'RAW_RIR_DATA' for e in events))

        malicious_ip_event = next((e for e in events if e.eventType == 'MALICIOUS_IPADDR'), None)
        self.assertIsNotNone(malicious_ip_event)
        self.assertEqual(malicious_ip_event.data, "1.2.3.4 (Confidence: 90%)")

        raw_data_event = next((e for e in events if e.eventType == 'RAW_RIR_DATA'), None)
        self.assertIsNotNone(raw_data_event)
        self.assertEqual(raw_data_event.data, str(mock_response_data))
