import pytest
import unittest

from modules.sfp_tool_trufflehog import sfp_tool_trufflehog
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleToolTrufflehog(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_tool_trufflehog()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_trufflehog()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_trufflehog()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_trufflehog()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_tool_path_configured_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_trufflehog()
        module.setup(sf, dict())
        
        target_value = 'example target value'
        target_type = 'PUBLIC_CODE_REPO'  # This should be a type the module is watching
        event_type = 'ROOT'
        event_data = 'example data'
        
        event_data = f"{target_type}: {target_value}"
        event_type = 'ROOT'
        
        event = SpiderFootEvent(event_type, event_data, None, '')
        result = module.handleEvent(event)
        
        assert module.errorState
        assert not result
