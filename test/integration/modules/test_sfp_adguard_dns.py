import pytest
import unittest

from modules.sfp_adguard_dns import sfp_adguard_dns
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleIntegrationAdGuardDns(unittest.TestCase):

    def test_handleEvent_event_data_adult_internet_name_blocked_should_return_event(self):
        self.default_options = {
            '_fetchtimeout': 15,
            '_useragent': 'SpiderFoot',
            '_internettlds': 'com,net,org,info,biz,us,uk',
            '_genericusers': 'admin,administrator,webmaster,hostmaster,postmaster,root,abuse',
        }
        sf = SpiderFoot(self.default_options)
        module = sfp_adguard_dns()
        module.setup(sf, dict(self.default_options))
        module.__name__ = "sfp_adguard_dns"
        target_value = 'spiderfoot.net'
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
        # Patch resolveHost to simulate a block (AdGuard returns a blocking IP)
        with mock_mod.patch.object(sf, 'resolveHost', return_value=['176.103.130.132']):
            def collect_event(event):
                events.append(event)
            with mock_mod.patch.object(module, 'notifyListeners', side_effect=collect_event):
                module.handleEvent(evt)
        self.assertTrue(any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))
        self.assertTrue(any('AdGuard - Family Filter' in e.data for e in events))

    def test_handleEvent_event_data_safe_internet_name_not_blocked_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_adguard_dns()
        module.setup(sf, dict())

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            raise Exception(f"Raised event {event.eventType}: {event.data}")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_adguard_dns)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'INTERNET_NAME'
        event_data = 'spiderfoot.net'
        event_module = 'example module'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)
        result = module.handleEvent(evt)

        self.assertIsNone(result)
