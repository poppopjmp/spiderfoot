import unittest
from unittest.mock import patch

from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_cloudflaredns import sfp_cloudflaredns
from sflib import SpiderFoot


class TestModuleIntegrationCloudflaredns(unittest.TestCase):

    def setUp(self):
        self.default_options = {"_useragent": "SpiderFootTestAgent"}
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_cloudflaredns()
        self.module.setup(self.sf, self.default_options)
        self.module.__name__ = self.module.__class__.__name__

    @patch('modules.sfp_cloudflaredns.socket.getaddrinfo')
    def test_handleEvent_safe_domain(self, mock_getaddrinfo):
        """Test handleEvent() with a safe domain.

        Args:
            mock_getaddrinfo (MagicMock): Mock for requests.getaddrinfo.
        """
        # Mock the DNS response for a safe domain
        # Simulate a normal IP address response
        mock_getaddrinfo.return_value = [(2, 1, 6, '', ('1.1.1.1', 53))]

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent(
            'INTERNET_NAME', 'cloudflare.com', self.module.__name__, None)
        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(self.module, 'notifyListeners', side_effect=events.append):
            self.module.handleEvent(evt)

        # Check that no BLACKLISTED_INTERNET_NAME event was produced
        self.assertFalse(
            any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))

    @patch('modules.sfp_cloudflaredns.socket.getaddrinfo')
    def test_handleEvent_blocked_domain(self, mock_getaddrinfo):
        """Test handleEvent() with a blocked domain.

        Args:
            mock_getaddrinfo (MagicMock): Mock for requests.getaddrinfo.
        """
        # Mock the DNS response for a blocked domain (adult category)
        # Simulate a blocked IP response
        mock_getaddrinfo.return_value = [(2, 1, 6, '', ('1.1.1.2', 53))]

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent(
            'INTERNET_NAME', 'pornhub.com', self.module.__name__, None)
        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(self.module, 'notifyListeners', side_effect=events.append):
            self.module.handleEvent(evt)

        # Check that a BLACKLISTED_INTERNET_NAME event was produced
        self.assertTrue(
            any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))

        # Check the data in the event
        blocked_event = next(
            (e for e in events if e.eventType == 'BLACKLISTED_INTERNET_NAME'), None)
        self.assertIsNotNone(blocked_event)
        self.assertEqual(blocked_event.data,
                         'CloudFlare - Family [pornhub.com]')
