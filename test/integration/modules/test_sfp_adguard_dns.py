import pytest
import unittest

from modules.sfp_adguard_dns import sfp_adguard_dns
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleIntegrationAdGuardDns(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 15,
            '_useragent': 'SpiderFoot',
            '_internettlds': 'com,net,org,info,biz,us,uk',
            '_genericusers': 'admin,administrator,webmaster,hostmaster,postmaster,root,abuse',
            '_socks1type': '',
            '_socks1addr': '',
            '_socks1port': '',
            '_socks1user': '',
            '_socks1pwd': '',
            '__logging': False,
        }

    def test_handleEvent_event_data_adult_internet_name_blocked_should_return_event(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_adguard_dns()
        module.setup(sf, dict(self.default_options))
        module.__name__ = "sfp_adguard_dns"
        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        event_type = 'ROOT'
        event_data = 'example data'
        event_module = 'testModule'
        source_event = None
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        event_type = 'INTERNET_NAME'
        event_data = 'pornhub.com'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        events = []
        import unittest.mock as mock_mod
        # Patch queryFamilyDNS and queryDefaultDNS to simulate a block (AdGuard returns a blocking IP)
        with mock_mod.patch.object(module, 'queryFamilyDNS', return_value=['94.140.14.35']), \
             mock_mod.patch.object(module, 'queryDefaultDNS', return_value=['94.140.14.35']), \
             mock_mod.patch.object(sf, 'normalizeDNS', side_effect=lambda x: x):
            def collect_event(event):
                events.append(event)
            with mock_mod.patch.object(module, 'notifyListeners', side_effect=collect_event):
                module.handleEvent(evt)
        self.assertTrue(any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))
        self.assertTrue(any('AdGuard - Family Filter' in e.data or 'AdGuard - Default Filter' in e.data for e in events))

    def test_handleEvent_event_data_safe_internet_name_not_blocked_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_adguard_dns()
        module.setup(sf, dict(self.default_options))
        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        import unittest.mock as mock_mod
        # Patch resolveHost to simulate a safe IP
        with mock_mod.patch.object(sf, 'resolveHost', return_value=['8.8.8.8']):
            events = []
            with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
                module.handleEvent(SpiderFootEvent('INTERNET_NAME', 'example.com', 'testModule', None))
            self.assertFalse(any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))
