import pytest
import unittest

from modules.sfp_slideshare import sfp_slideshare
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


@pytest.mark.usefixtures
class TestModuleSlideshare(unittest.TestCase):

    def test_opts(self):
        module = sfp_slideshare()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_slideshare()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_slideshare()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_slideshare()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_event_data_social_media_not_slideshare_profile_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_slideshare()
        module.setup(sf, dict())

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            raise Exception(f"Raised event {event.eventType}: {event.data}")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_slideshare)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'SOCIAL_MEDIA'
        event_data = 'Not SlideShare: example_username'
        event_module = 'example module'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)
        result = module.handleEvent(evt)

        self.assertIsNone(result)
