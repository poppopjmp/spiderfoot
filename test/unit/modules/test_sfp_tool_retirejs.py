import pytest
import unittest

from modules.sfp_tool_retirejs import sfp_tool_retirejs
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleToolRetirejs(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_tool_retirejs()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_retirejs()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_retirejs()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_retirejs()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_tool_path_configured_should_set_errorState(self):
        """
        Test handleEvent when no tool path is configured
        """
        sf = SpiderFoot(self.default_options)

        # Create an event for an accepted target type (changing URL to INTERNET_NAME)
        # RetireJS only accepts certain target types which don't include 'URL'
        event_type = "ROOT"
        event_data = "example.com"
        event_module = ""
        source_event = ""
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        # Configure module with no path to RetireJS
        module = sfp_tool_retirejs()
        module.setup(sf, dict())

        result = module.handleEvent(evt)

        assert result is None
        assert module.errorState is True
