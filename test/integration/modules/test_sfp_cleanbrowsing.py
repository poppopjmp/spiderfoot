import pytest
import unittest

from modules.sfp_cleanbrowsing import sfp_cleanbrowsing
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationcleanbrowsing(unittest.TestCase):

    def test_handleEvent_event_data_adult_internet_name_blocked_should_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_cleanbrowsing()
        module.setup(sf, dict())
        module.__name__ = "sfp_cleanbrowsing"

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'INTERNET_NAME'
        event_data = 'pornhub.com'
        event_module = 'example module'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)

        # Assert that a BLACKLISTED_INTERNET_NAME event was produced with correct data
        self.assertTrue(any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))
        blocked_event = next((e for e in events if e.eventType == 'BLACKLISTED_INTERNET_NAME'), None)
        self.assertIsNotNone(blocked_event)
        self.assertEqual(blocked_event.data, 'CleanBrowsing DNS - Adult [pornhub.com]')

    def test_handleEvent_event_data_safe_internet_name_not_blocked_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_cleanbrowsing()
        module.setup(sf, dict())
        module.__name__ = "sfp_cleanbrowsing"

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'INTERNET_NAME'
        event_data = 'spiderfoot.net'
        event_module = 'example module'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)
        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)
        # Assert that no BLACKLISTED_INTERNET_NAME event was produced
        self.assertFalse(any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events))
