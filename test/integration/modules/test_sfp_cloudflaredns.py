import unittest
from unittest.mock import patch

from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_cloudflaredns import sfp_cloudflaredns
from sflib import SpiderFoot


class TestModuleIntegrationCloudflaredns(unittest.TestCase):

    def setUp(self):
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_cloudflaredns()
        self.module.setup(self.sf, dict())

    @patch('modules.sfp_cloudflaredns.socket.getaddrinfo')
    def test_handleEvent_safe_domain(self, mock_getaddrinfo):
        """
        Test handleEvent() with a safe domain.
        Args:
        mock_getaddrinfo: Mock for requests.get
        """
        # Mock the DNS response for a safe domain
        mock_getaddrinfo.return_value = [(2, 1, 6, '', ('1.1.1.1', 53))]  # Simulate a normal IP address response

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent('INTERNET_NAME', 'cloudflare.com', 'example module', None)
        self.module.handleEvent(evt)

        # Check that no BLACKLISTED_INTERNET_NAME event was produced
        events = self.sf.getEvents()
        self.assertFalse(any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))

    @patch('modules.sfp_cloudflaredns.socket.getaddrinfo')
    def test_handleEvent_blocked_domain(self, mock_getaddrinfo):
        """
        Test handleEvent() with a blocked domain.
        Args:
        mock_getaddrinfo: Mock for mock_getaddrinfo
        """
        # Mock the DNS response for a blocked domain (adult category)
        mock_getaddrinfo.return_value = [(2, 1, 6, '', ('1.1.1.2', 53))]  # Simulate a blocked IP response

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent('INTERNET_NAME', 'pornhub.com', 'example module', None)
        self.module.handleEvent(evt)

        # Check that a BLACKLISTED_INTERNET_NAME event was produced
        events = self.sf.getEvents()
        self.assertTrue(any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))

        # Check the data in the event
        blocked_event = next((e for e in events if e.eventType == 'BLACKLISTED_INTERNET_NAME'), None)
        self.assertIsNotNone(blocked_event)
        self.assertEqual(blocked_event.data, 'CloudFlare - Family [pornhub.com]')
