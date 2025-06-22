import unittest
from unittest.mock import patch

from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_accounts import sfp_accounts
from sflib import SpiderFoot


class TestModuleIntegrationAccounts(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 15,
            '_useragent': 'SpiderFoot',
            '_internettlds': 'com,net,org,info,biz,us,uk',
            '_genericusers': 'admin,administrator,webmaster,hostmaster,postmaster,root,abuse',
        }
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_accounts()
        self.module.setup(self.sf, dict(self.default_options))
        self.module.__name__ = "sfp_accounts"

    def test_handleEvent_with_accounts(self):
        import unittest.mock as mock_mod
        # Patch checkSites to simulate finding an account
        with mock_mod.patch.object(self.module, 'checkSites', return_value=["Twitter (Category: Social)\n<SFURL>https://twitter.com/johndoe</SFURL>"]):
            target_value = 'johndoe'
            target_type = 'USERNAME'
            target = SpiderFootTarget(target_value, target_type)
            self.module.setTarget(target)
            evt = SpiderFootEvent('USERNAME', 'johndoe', 'testModule', None)
            events = []
            def collect_event(evt):
                events.append(evt)
            with mock_mod.patch.object(self.module, 'notifyListeners', side_effect=collect_event):
                self.module.handleEvent(evt)
            self.assertTrue(any(e.eventType == 'ACCOUNT_EXTERNAL_OWNED' for e in events))
            account_event = next((e for e in events if e.eventType == 'ACCOUNT_EXTERNAL_OWNED'), None)
            self.assertIsNotNone(account_event)
            self.assertIn('Twitter', account_event.data)
