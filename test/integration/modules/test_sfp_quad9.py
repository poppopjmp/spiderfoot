import pytest
import unittest

from modules.sfp_quad9 import sfp_quad9
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationQuad9(unittest.TestCase):

    def test_handleEvent_event_data_safe_internet_name_not_blocked_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_quad9()
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            raise Exception(f"Raised event {event.eventType}: {event.data}")

        module.notifyListeners = new_notifyListeners.__get__(module, sfp_quad9)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'INTERNET_NAME'
        event_data = 'quad9.net'
        event_module = 'example module'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)
        result = module.handleEvent(evt)

        self.assertIsNone(result)
