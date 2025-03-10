import pytest
import unittest

from modules.sfp_dnssublist import sfp_dnssublist
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleDnssublist(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_dnssublist()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_dnssublist()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_dnssublist()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_dnssublist()
        self.assertIsInstance(module.producedEvents(), list)
        
    def test_handleEvent_domain_name_event_should_return_domain_names(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_dnssublist()
        module.setup(sf, dict())
        
        # Override internal methods to control test
        module.sublistFind = lambda domain, keyword: ["test." + domain]

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            expected = 'INTERNET_NAME'
            if str(event.eventType) != expected:
                raise Exception(f"{event.eventType} != {expected}")

            expected = 'test.example.com'
            if str(event.data) != expected:
                raise Exception(f"{event.data} != {expected}")

            raise Exception("OK")

        module.notifyListeners = new_notifyListeners.__get__(module, sfp_dnssublist)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'example module'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        with self.assertRaises(Exception) as cm:
            module.handleEvent(evt)

        self.assertEqual("OK", str(cm.exception))
