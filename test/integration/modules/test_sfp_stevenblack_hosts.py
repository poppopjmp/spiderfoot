import pytest
import unittest

from modules.sfp_stevenblack_hosts import sfp_stevenblack_hosts
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationStevenblackHosts(unittest.TestCase):

    def test_handleEvent_event_data_affiliate_internet_name_matching_ad_server_should_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_stevenblack_hosts()
        module.setup(sf, dict())
        module.__name__ = "sfp_stevenblack_hosts"

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        module.opts['_fetchtimeout'] = 15
        module.optdescs['_fetchtimeout'] = ''
        module.opts['_useragent'] = ''
        module.optdescs['_useragent'] = ''

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'AFFILIATE_INTERNET_NAME'
        event_data = 'ads.google.com'
        event_module = 'example module'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)
        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)
        # Assert that a MALICIOUS_AFFILIATE_INTERNET_NAME event was produced with correct data
        self.assertTrue(any(e.eventType == 'MALICIOUS_AFFILIATE_INTERNET_NAME' for e in events))
        blocked_event = next((e for e in events if e.eventType == 'MALICIOUS_AFFILIATE_INTERNET_NAME'), None)
        self.assertIsNotNone(blocked_event)
        self.assertIn('Steven Black Hosts Blocklist', blocked_event.data)

    def test_handleEvent_event_data_affiliate_internet_name_not_matching_ad_server_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_stevenblack_hosts()
        module.setup(sf, dict())
        module.__name__ = "sfp_stevenblack_hosts"

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        module.opts['_fetchtimeout'] = 15
        module.optdescs['_fetchtimeout'] = ''
        module.opts['_useragent'] = ''
        module.optdescs['_useragent'] = ''

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'AFFILIATE_INTERNET_NAME'
        event_data = 'no.ads.safe.local'
        event_module = 'example module'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)
        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)
        # Assert that no MALICIOUS_AFFILIATE_INTERNET_NAME event was produced
        self.assertFalse(any(e.eventType == 'MALICIOUS_AFFILIATE_INTERNET_NAME' for e in events))
