import pytest
import unittest

from modules.sfp_email import sfp_email
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleEmail(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_email()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_email()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_email()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_email()
        self.assertIsInstance(module.producedEvents(), list)

    @unittest.skip("todo")
    @safe_recursion(max_depth=5)
    def test_handleEvent_event_data_target_web_content_containing_email_address_should_return_event(selfdepth=0):
        sf = SpiderFoot(self.default_options)

        module = sfp_email()
        module.setup(sf, dict())

        target_value = 'van1shland.io'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            expected = 'EMAILADDR'
            if str(event.eventType) != expected:
                raise Exception(f"{event.eventType} != {expected}")

            expected = 'firstname.lastname@van1shland.io'
            if str(event.data) != expected:
                raise Exception(f"{event.data} != {expected}")

            raise Exception("OK")

        module.notifyListeners = new_notifyListeners.__get__(module, sfp_email)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        event_type = 'TARGET_WEB_CONTENT'
        event_data = '<p>sample data firstname.lastname@van1shland.io sample data.</p>'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        with self.assertRaises(Exception) as cm:
            module.handleEvent(evt)

        self.assertEqual("OK", str(cm.exception))

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
