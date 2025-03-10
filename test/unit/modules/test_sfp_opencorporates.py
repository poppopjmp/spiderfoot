import pytest
import unittest

from modules.sfp_opencorporates import sfp_opencorporates
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleOpencorporates(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_opencorporates()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_opencorporates()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_opencorporates()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_opencorporates()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_api_key_should_set_errorState(self):
        """
        Test handleEvent when no API key is provided
        """
        sf = SpiderFoot(self.default_options)

        module = sfp_opencorporates()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'INTERNET_NAME'  # Using a valid target type instead of COMPANY_NAME
        module_result = None

        event = SpiderFootEvent(target_type, target_value, module_result, source_event)
        module.handleEvent(event)

        self.assertTrue(module.errorState)
