import pytest
import unittest

from modules.sfp_comodo import sfp_comodo
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationcomodo(unittest.TestCase):

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

    def test_handleEvent_event_data_safe_internet_name_not_blocked_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_comodo()
        module.setup(sf, dict(self.default_options))
        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        import unittest.mock as mock_mod
        events = []
        # Patch resolveHost to simulate a safe IP, and query to return True (not blocked)
        with mock_mod.patch.object(sf, 'resolveHost', return_value=['8.8.8.8']), \
             mock_mod.patch.object(module, 'query', return_value=True), \
             mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
            event_type = 'ROOT'
            event_data = 'example data'
            event_module = ''
            source_event = ''
            evt = SpiderFootEvent(event_type, event_data,
                                  event_module, source_event)
            event_type = 'INTERNET_NAME'
            event_data = 'comodo.com'
            event_module = 'example module'
            source_event = evt
            evt = SpiderFootEvent(event_type, event_data,
                                  event_module, source_event)
            result = module.handleEvent(evt)
        self.assertFalse(any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))
        self.assertIsNone(result)

    def test_handleEvent_event_data_blocked_should_return_event(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_comodo()
        module.setup(sf, dict(self.default_options))
        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        import unittest.mock as mock_mod
        events = []
        # Patch resolveHost to simulate a safe IP, and query to return False (blocked)
        with mock_mod.patch.object(sf, 'resolveHost', return_value=['8.8.8.8']), \
             mock_mod.patch.object(module, 'query', return_value=False), \
             mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
            event_type = 'ROOT'
            event_data = 'example data'
            event_module = ''
            source_event = ''
            evt = SpiderFootEvent(event_type, event_data,
                                  event_module, source_event)
            event_type = 'INTERNET_NAME'
            event_data = 'malicious.com'
            event_module = 'example module'
            source_event = evt
            evt = SpiderFootEvent(event_type, event_data,
                                  event_module, source_event)
            result = module.handleEvent(evt)
        self.assertTrue(any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))
        self.assertTrue(any(e.eventType == 'MALICIOUS_INTERNET_NAME' for e in events))
        self.assertIsNone(result)
