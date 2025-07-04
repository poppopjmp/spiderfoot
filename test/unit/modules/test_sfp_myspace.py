import pytest
import unittest

from modules.sfp_myspace import sfp_myspace
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleMyspace(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_myspace()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_myspace()
        module.setup(sf, dict())
        self.assertTrue(hasattr(module, 'opts'))

    def test_watchedEvents_should_return_list(self):
        module = sfp_myspace()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        """
        Test producedEvents(self)
        """
        module = sfp_myspace()
        produced_events = module.producedEvents()
        self.assertIsInstance(produced_events, list)
        self.assertGreater(len(produced_events), 0)

    @safe_recursion(max_depth=5)
    def test_handleEvent_event_data_social_media_not_myspace_profile_should_not_return_event(self, depth=0):
        sf = SpiderFoot(self.default_options)

        module = sfp_myspace()
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            raise Exception(f"Raised event {event.eventType}: {event.data}")

        module.notifyListeners = new_notifyListeners.__get__(
            module, sfp_myspace)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'SOCIAL_MEDIA'
        event_data = 'Not MySpace: example_username'
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
        """Clean up after each test."""
        super().tearDown()
