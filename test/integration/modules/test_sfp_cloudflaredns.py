import unittest
from unittest.mock import patch

from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_cloudflaredns import sfp_cloudflaredns
from sflib import SpiderFoot


class TestModuleIntegrationCloudflaredns(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_useragent': 'SpiderFootTestAgent',
            '_socks1type': '',
            '_socks1addr': '',
            '_socks1port': '',
            '_socks1user': '',
            '_socks1pwd': '',
            '__logging': False,
        }
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_cloudflaredns()
        self.module.setup(self.sf, self.default_options)
        self.module.__name__ = self.module.__class__.__name__

    def test_handleEvent_safe_domain(self):
        """Test handleEvent() with a safe domain."""
        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent(
            'INTERNET_NAME', 'cloudflare.com', self.module.__name__, None)
        events = []
        import unittest.mock as mock_mod
        # Patch queryFamilyDNS and queryMalwareDNS to return safe IPs (not blocked)
        with mock_mod.patch.object(self.module, 'queryFamilyDNS', return_value=['1.1.1.1']), \
             mock_mod.patch.object(self.module, 'queryMalwareDNS', return_value=['1.1.1.1']), \
             mock_mod.patch.object(self.sf, 'normalizeDNS', side_effect=lambda x: x), \
             mock_mod.patch.object(self.module, 'notifyListeners', side_effect=events.append):
            self.module.handleEvent(evt)

        # Check that no BLACKLISTED_INTERNET_NAME event was produced
        self.assertFalse(
            any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))

    def test_handleEvent_blocked_domain(self):
        """Test handleEvent() with a blocked domain."""
        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent(
            'INTERNET_NAME', 'pornhub.com', self.module.__name__, None)
        events = []
        import unittest.mock as mock_mod
        # Patch queryFamilyDNS to return ['0.0.0.0'] (blocked), queryMalwareDNS to return safe IP
        with mock_mod.patch.object(self.module, 'queryFamilyDNS', return_value=['0.0.0.0']), \
             mock_mod.patch.object(self.module, 'queryMalwareDNS', return_value=['1.1.1.1']), \
             mock_mod.patch.object(self.sf, 'normalizeDNS', side_effect=lambda x: x), \
             mock_mod.patch.object(self.module, 'notifyListeners', side_effect=events.append):
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
