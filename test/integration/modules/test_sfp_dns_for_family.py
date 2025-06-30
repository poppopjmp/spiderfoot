import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_dns_for_family import sfp_dns_for_family
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationDnsForFamily(unittest.TestCase):

    def setUp(self):
        self.default_options = {"_useragent": "SpiderFootTestAgent"}
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_dns_for_family()
        self.module.setup(self.sf, self.default_options)
        self.module.__name__ = self.module.__class__.__name__

    @patch('dns.resolver.Resolver.resolve')
    def test_handleEvent_event_data_safe_internet_name_not_blocked_should_not_return_event(self, mock_resolve):
        # Simulate DNS response not matching the block IP
        mock_resolve.return_value = [MagicMock(__str__=lambda self: '1.2.3.4')]
        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)
        evt = SpiderFootEvent('INTERNET_NAME', 'dns_for_family.com', self.module.__name__, None)
        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(self.module, 'notifyListeners', side_effect=events.append):
            self.module.handleEvent(evt)
        self.assertFalse(any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))

    @patch('dns.resolver.Resolver.resolve')
    def test_handleEvent_event_data_adult_internet_name_blocked_should_return_event(self, mock_resolve):
        # Simulate DNS response matching the block IP
        mock_resolve.return_value = [MagicMock(__str__=lambda self: '159.69.10.249')]
        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)
        evt = SpiderFootEvent('INTERNET_NAME', 'pornhub.com', self.module.__name__, None)
        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(self.module, 'notifyListeners', side_effect=events.append):
            self.module.handleEvent(evt)
        self.assertTrue(any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))
        blocked_event = next((e for e in events if e.eventType == 'BLACKLISTED_INTERNET_NAME'), None)
        self.assertIsNotNone(blocked_event)
        self.assertEqual(blocked_event.data, 'DNS for Family [pornhub.com]')
