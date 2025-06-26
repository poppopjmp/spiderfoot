import pytest
import unittest

from modules.sfp_dnsresolve import sfp_dnsresolve
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget

import unittest.mock as mock_mod


class TestModuleIntegrationDnsResolve(unittest.TestCase):
    default_options = {
        '_internettlds': ['com', 'net', 'org'],
        'validatereverse': True,
        'skipcommononwildcard': True,
        'netblocklookup': True,
        'maxnetblock': 24,
        'maxv6netblock': 120,
    }

    def test_enrichTarget_should_return_SpiderFootTarget(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_dnsresolve()
        module.setup(sf, dict())
        module.__name__ = "sfp_dnsresolve"

        target_value = '127.0.0.1'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)

        result = module.enrichTarget(target)
        self.assertIsInstance(result, SpiderFootTarget)
        self.assertEqual(result.targetType, target_type)
        self.assertEqual(result.targetValue, target_value)

    def test_resolveTargets_should_return_list(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_dnsresolve()
        module.setup(sf, dict())
        module.__name__ = "sfp_dnsresolve"

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        invalid_types = [None, "", list(), dict()]
        for invalid_type in invalid_types:
            with self.subTest(invalid_type=invalid_type):
                resolve_targets = module.resolveTargets(invalid_type, False)
                self.assertIsInstance(resolve_targets, list)

        target = SpiderFootTarget("van1shland.io", "INTERNET_NAME")
        resolve_targets = module.resolveTargets(target, False)
        self.assertIsInstance(resolve_targets, list)
        self.assertIn('van1shland.io', resolve_targets)

        target = SpiderFootTarget("127.0.0.1", "IP_ADDRESS")
        resolve_targets = module.resolveTargets(target, False)
        self.assertIsInstance(resolve_targets, list)
        self.assertIn('127.0.0.1', resolve_targets)

        target = SpiderFootTarget("::1", "IPV6_ADDRESS")
        resolve_targets = module.resolveTargets(target, False)
        self.assertIsInstance(resolve_targets, list)
        self.assertIn('::1', resolve_targets)

        target = SpiderFootTarget("127.0.0.1/32", "NETBLOCK_OWNER")
        resolve_targets = module.resolveTargets(target, False)
        self.assertIsInstance(resolve_targets, list)
        self.assertIn('127.0.0.1', resolve_targets)

    # note: test fails on MacOSX on CI
    def test_handleEvent_event_data_ip_address_should_return_internet_name_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_dnsresolve()
        module.setup(sf, dict(self.default_options))
        module.__name__ = "sfp_dnsresolve"

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'IP_ADDRESS'
        event_data = '1.1.1.1'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        events = []
        with mock_mod.patch.object(sf, 'resolveIP', return_value=['one.one.one.one']):
            with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
                module.handleEvent(evt)

        self.assertTrue(any(e.eventType == 'INTERNET_NAME' and e.data == 'one.one.one.one' for e in events))

    # note: test fails on MacOSX on CI
    def test_handleEvent_event_data_ipv6_address_should_return_internet_name_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_dnsresolve()
        module.setup(sf, dict(self.default_options))
        module.__name__ = "sfp_dnsresolve"

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'IPV6_ADDRESS'
        event_data = '2606:4700:4700::1111'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        events = []
        with mock_mod.patch.object(sf, 'resolveIP', return_value=['one.one.one.one']):
            with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
                module.handleEvent(evt)

        self.assertTrue(any(e.eventType == 'INTERNET_NAME' and e.data == 'one.one.one.one' for e in events))

    # note: test fails on MacOSX on CI
    def test_handleEvent_event_data_affiliate_ip_address_should_return_affiliate_internet_name_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_dnsresolve()
        module.setup(sf, dict(self.default_options))
        module.__name__ = "sfp_dnsresolve"

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'AFFILIATE_IPADDR'
        event_data = '1.1.1.1'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        events = []
        with mock_mod.patch.object(sf, 'resolveIP', return_value=['one.one.one.one']):
            with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
                module.handleEvent(evt)

        self.assertTrue(any(e.eventType == 'AFFILIATE_INTERNET_NAME' and e.data == 'one.one.one.one' for e in events))

    def test_handleEvent_event_data_raw_rir_data_containing_subdomain_should_return_internet_name_event(self):
        """Test handleEvent(self, event)"""
        sf = SpiderFoot(self.default_options)

        module = sfp_dnsresolve()
        module.setup(sf, dict(self.default_options))
        module.__name__ = "sfp_dnsresolve"

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'RAW_RIR_DATA'
        event_data = 'example data www.van1shland.io example data'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        events = []
        with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
            with mock_mod.patch.object(sf, 'resolveHost', return_value=['www.van1shland.io']):
                module.handleEvent(evt)
        self.assertTrue(any(e.eventType == 'INTERNET_NAME' and e.data == 'www.van1shland.io' for e in events))
