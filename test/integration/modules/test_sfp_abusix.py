import unittest
from unittest.mock import patch
import requests
import time

from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_abusix import sfp_abusix
from sflib import SpiderFoot


class BaseTestModuleIntegration(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 15,
            '_useragent': 'SpiderFoot',
            '_internettlds': 'com,net,org,info,biz,us,uk',
            '_genericusers': 'admin,administrator,webmaster,hostmaster,postmaster,root,abuse',
        }
        self.sf = SpiderFoot(self.default_options)
        self.module = self.module_class()
        opts = dict(self.default_options)
        opts['api_key'] = 'DUMMY_KEY'
        self.module.setup(self.sf, opts)
        self.module.__name__ = "sfp_abusix"

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

    def create_event(self, target_value, target_type, event_type, event_data=None):
        if not event_data:
            event_data = 'dummy_data'
        target = SpiderFootTarget(target_value, target_type)
        evt = SpiderFootEvent(event_type, event_data, 'testModule', None)
        return target, evt


class TestModuleIntegrationAbusix(BaseTestModuleIntegration):

    module_class = sfp_abusix

    @patch('modules.sfp_abusix.requests.get')
    def test_handleEvent_malicious_ip(self, mock_get):
        import unittest.mock as mock_mod
        # Patch resolveHost to simulate a blacklist hit
        with mock_mod.patch.object(self.sf, 'resolveHost', return_value=['127.0.0.2']):
            target_value = '1.2.3.4'
            target_type = 'IP_ADDRESS'
            target, evt = self.create_event(target_value, target_type, 'IP_ADDRESS', '1.2.3.4')
            self.module.setTarget(target)
            events = []
            def collect_event(evt):
                events.append(evt)
            with mock_mod.patch.object(self.module, 'notifyListeners', side_effect=collect_event):
                self.module.handleEvent(evt)
            self.assertTrue(any(e.eventType == 'MALICIOUS_IPADDR' for e in events))
            self.assertTrue(any(e.eventType == 'BLACKLISTED_IPADDR' for e in events))
            malicious_ip_event = next((e for e in events if e.eventType == 'MALICIOUS_IPADDR'), None)
            self.assertIsNotNone(malicious_ip_event)
            self.assertIn('Abusix Mail Intelligence', malicious_ip_event.data)
            blacklist_event = next((e for e in events if e.eventType == 'BLACKLISTED_IPADDR'), None)
            self.assertIsNotNone(blacklist_event)
            self.assertIn('Abusix Mail Intelligence', blacklist_event.data)
