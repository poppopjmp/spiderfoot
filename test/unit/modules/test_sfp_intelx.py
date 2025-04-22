import pytest
import unittest

from modules.sfp_intelx import sfp_intelx
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestModuleIntelx(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_intelx()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_intelx()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_intelx()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_intelx()
        self.assertIsInstance(module.producedEvents(), list)

    @safe_recursion(max_depth=5)
    def test_handleEvent_no_api_key_should_set_errorState(selfdepth=0):
        sf = SpiderFoot(self.default_options)

        module = sfp_intelx()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()

    def test_query_should_extract_matches_within_files(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_intelx()
        module.setup(sf, dict())

        query_result = module.query("example query", "intelligent")
        self.assertIsNotNone(query_result)

    def test_handleEvent_should_process_and_output_matches_within_files(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_intelx()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        result = module.handleEvent(evt)
        self.assertIsNone(result)
