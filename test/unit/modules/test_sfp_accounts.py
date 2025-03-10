import pytest
import unittest

from modules.sfp_accounts import sfp_accounts
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleAccounts(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_accounts()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_accounts()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_accounts()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_accounts()
        self.assertIsInstance(module.producedEvents(), list)
    
    def test_handleEvent_username_event_data_should_return_social_media_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_accounts()
        module.setup(sf, dict())
        
        # Override check_service to always return True for testing
        module.check_service = lambda site, username: True

        target_value = 'example'
        target_type = 'USERNAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            expected = 'SOCIAL_MEDIA'
            if str(event.eventType) != expected:
                raise Exception(f"{event.eventType} != {expected}")
            raise Exception("OK")

        module.notifyListeners = new_notifyListeners.__get__(module, sfp_accounts)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'USERNAME'
        event_data = 'example'
        event_module = 'sfp_example'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        with self.assertRaises(Exception) as cm:
            module.handleEvent(evt)

        self.assertEqual("OK", str(cm.exception))
