import pytest
import unittest

from modules.sfp_phone import sfp_phone
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModulePhone(SpiderFootTestBase):

    def setUp(self):
        super().setUp()

    def test_opts(self):
        module = sfp_phone()
        module.__name__ = "sfp_phone"
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_phone()
        module.__name__ = "sfp_phone"
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_phone()
        module.__name__ = "sfp_phone"
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_phone()
        module.__name__ = "sfp_phone"
        self.assertIsInstance(module.producedEvents(), list)

    @safe_recursion(max_depth=5)
    def test_handleEvent_domain_whois_event_data_containing_phone_string_should_create_phone_number_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_phone()
        module.__name__ = "sfp_phone"
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            expected = 'PHONE_NUMBER'
            if str(event.eventType) != expected:
                raise Exception(f"{event.eventType} != {expected}")

            expected = "+12025550111"
            if str(event.data) != expected:
                raise Exception(f"{event.data} != {expected}")

            raise Exception("OK")

        module.notifyListeners = new_notifyListeners.__get__(module, sfp_phone)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'DOMAIN_WHOIS'
        event_data = 'example data +1 202 555 0111 example data'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        with self.assertRaises(Exception) as cm:
            module.handleEvent(evt)

        self.assertEqual("OK", str(cm.exception))

    @safe_recursion(max_depth=5)
    def test_handleEvent_domain_whois_event_data_not_containing_phone_string_should_not_create_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_phone()
        module.__name__ = "sfp_phone"
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            raise Exception(f"Raised event {event.eventType}: {event.data}")

        module.notifyListeners = new_notifyListeners.__get__(module, sfp_phone)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'DOMAIN_WHOIS'
        event_data = 'example data'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)

    @safe_recursion(max_depth=5)
    def test_handleEvent_phone_number_event_data_containing_phone_string_should_return_provider_telco_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_phone()
        module.__name__ = "sfp_phone"
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            expected = 'PROVIDER_TELCO'
            if str(event.eventType) != expected:
                raise Exception(f"{event.eventType} != {expected}")

            expected = "Swisscom"
            if str(event.data) != expected:
                raise Exception(f"{event.data} != {expected}")

            raise Exception("OK")

        module.notifyListeners = new_notifyListeners.__get__(module, sfp_phone)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'PHONE_NUMBER'
        event_data = '+41798765432'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        with self.assertRaises(Exception) as cm:
            module.handleEvent(evt)

        self.assertEqual("OK", str(cm.exception))


if __name__ == '__main__':
    unittest.main()
