import pytest
import unittest

from modules.sfp_github import sfp_github
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleGithub(SpiderFootTestBase):
    def test_opts(self):
        module = sfp_github()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_github()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_github()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_github()
        self.assertIsInstance(module.producedEvents(), list)

    @safe_recursion(max_depth=5)
    def test_handleEvent_event_data_social_media_not_github_profile_should_not_return_event(self):
        """
        Test handleEvent(self, event) with event data that is not a GitHub profile should not return event
        """
        sf = SpiderFoot(self.default_options)

        module = sfp_github()
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            raise Exception(f"Raised event {event.eventType}: {event.data}")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_github)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'SOCIAL_MEDIA'
        event_data = 'Not GitHub: example_username'
        event_module = 'example module'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)
        result = module.handleEvent(evt)

        self.assertIsNone(result)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
