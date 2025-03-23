import unittest
from unittest.mock import patch

from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_c99 import sfp_c99
from sflib import SpiderFoot


class TestModuleIntegrationC99(unittest.TestCase):

    def setUp(self):
        # Assuming default_options is defined
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_c99()
        self.module.setup(self.sf, dict())

    @patch('modules.sfp_c99.requests.get')  # Mock the requests.get function
    def test_handleEvent_malicious_ip(self, mock_get):
        # Mock the API response for a malicious IP
        mock_response_data = {
            "1.2.3.4": {
                "detected": True,
                "badips": 10,
                "blacklists": ["bl1", "bl2"],
            }
        }
        mock_get.return_value.json.return_value = mock_response_data

        target_value = '1.2.3.4'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent('ROOT', '', '', '')
        self.module.handleEvent(evt)

        # Check if the module produced the expected events
        events = self.sf.getEvents()
        self.assertTrue(any(e.eventType == 'MALICIOUS_IPADDR' for e in events))
        self.assertTrue(any(e.eventType == 'RAW_RIR_DATA' for e in events))

        # Check the data in the events
        malicious_ip_event = next(
            (e for e in events if e.eventType == 'MALICIOUS_IPADDR'), None)
        self.assertIsNotNone(malicious_ip_event)
        # Adjust assertion based on how sfp_c99 formats the event data
        self.assertIn("1.2.3.4", malicious_ip_event.data)

        raw_data_event = next(
            (e for e in events if e.eventType == 'RAW_RIR_DATA'), None)
        self.assertIsNotNone(raw_data_event)
        self.assertEqual(raw_data_event.data, str(mock_response_data))
