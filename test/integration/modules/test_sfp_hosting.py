from __future__ import annotations

import pytest
import unittest
from test.unit.utils.test_module_base import TestModuleBase

from modules.sfp_hosting import sfp_hosting
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationHosting(TestModuleBase):


    def setUp(self):
        """Enhanced setUp with ThreadReaper module tracking."""
        super().setUp()
        # ThreadReaper infrastructure is automatically initialized
        
    def tearDown(self):
        """Enhanced tearDown with ThreadReaper cleanup."""
        # ThreadReaper infrastructure automatically cleans up
        super().tearDown()
    @unittest.skip("todo")
    def test_handleEvent_event_data_ip_address_hosted_should_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_hosting()
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            expected = 'PROVIDER_HOSTING'
            if str(event.eventType) != expected:
                raise Exception(f"{event.eventType} != {expected}")

            expected = "Amazon AWS: http://www.amazon.com/aws/"
            if str(event.data) != expected:
                raise Exception(f"{event.data} != {expected}")

            raise Exception("OK")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_hosting)

        event_type = 'ROOT'
        event_data = '3.1.1.1'
        event_module = ''
        source_event = ''

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        with self.assertRaises(Exception) as cm:
            module.handleEvent(evt)

        self.assertEqual("OK", str(cm.exception))

    @unittest.skip("todo")
    def test_handleEvent_event_data_ip_address_not_hosted_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_hosting()
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            raise Exception(f"Raised event {event.eventType}: {event.data}")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_hosting)

        event_type = 'ROOT'
        event_data = '127.0.0.1'
        event_module = ''
        source_event = ''

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)
        result = module.handleEvent(evt)

        self.assertIsNone(result)
