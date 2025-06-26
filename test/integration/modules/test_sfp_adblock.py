import pytest
import unittest

from modules.sfp_adblock import sfp_adblock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleIntegrationAdblock(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 15,
            '_useragent': 'SpiderFoot',
            '_internettlds': 'com,net,org,info,biz,us,uk',
            '_genericusers': 'admin,administrator,webmaster,hostmaster,postmaster,root,abuse',
            '_socks1type': '',
            '_socks2addr': '',
            '_socks3port': '',
            '_socks4user': '',
            '_socks5pwd': '',
        }

    def test_handleEvent_event_data_provider_javascript_url_matching_ad_filter_should_return_event(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_adblock()
        module.setup(sf, dict(self.default_options))
        module.__name__ = "sfp_adblock"
        # Patch rules to always block the test URL
        import unittest.mock as mock_mod
        mock_rules = mock_mod.Mock()
        mock_rules.should_block.return_value = True
        module.rules = mock_rules
        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        event_type = 'ROOT'
        event_data = 'example data'
        event_module = 'testModule'
        source_event = None
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        event_type = 'PROVIDER_JAVASCRIPT'
        event_data = 'https://example.local/lib/ad.js'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        events = []
        import unittest.mock as mock_mod
        def collect_event(event):
            events.append(event)
        with mock_mod.patch.object(module, 'notifyListeners', side_effect=collect_event):
            module.handleEvent(evt)
        self.assertTrue(any(e.eventType == 'URL_ADBLOCKED_EXTERNAL' for e in events))
        self.assertTrue(any(e.data == 'https://example.local/lib/ad.js' for e in events))

    def test_handleEvent_event_data_external_url_matching_ad_filter_should_return_event(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_adblock()
        module.setup(sf, dict(self.default_options))
        module.__name__ = "sfp_adblock"
        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        event_type = 'ROOT'
        event_data = 'example data'
        event_module = 'testModule'
        source_event = None
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        event_type = 'LINKED_URL_EXTERNAL'
        event_data = 'https://example.local/lib/ad.js'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        events = []
        import unittest.mock as mock_mod
        mock_rules = mock_mod.Mock()
        mock_rules.should_block.return_value = True
        module.rules = mock_rules
        def collect_event(event):
            events.append(event)
        with mock_mod.patch.object(module, 'notifyListeners', side_effect=collect_event):
            module.handleEvent(evt)
        self.assertTrue(any(e.eventType == 'URL_ADBLOCKED_EXTERNAL' for e in events))
        self.assertTrue(any(e.data == 'https://example.local/lib/ad.js' for e in events))

    def test_handleEvent_event_data_external_url_not_matching_ad_filter_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_adblock()
        module.setup(sf, dict(self.default_options))

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        import unittest.mock as mock_mod
        mock_rules = mock_mod.Mock()
        mock_rules.should_block.return_value = False
        module.rules = mock_rules

        def new_notifyListeners(self, event):
            raise Exception(f"Raised event {event.eventType}: {event.data}")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_adblock)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'LINKED_URL_EXTERNAL'
        event_data = 'https://example.local/lib/example.js'
        event_module = 'example module'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)
        result = module.handleEvent(evt)

        self.assertIsNone(result)
