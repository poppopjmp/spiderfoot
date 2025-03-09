import pytest
import unittest

from modules.sfp__stor_db import sfp__stor_db
from sflib import SpiderFoot
from test.unit.modules.test_module_base import SpiderFootModuleTestCase
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class BaseTestModuleIntegration(SpiderFootModuleTestCase):

    def setup_module(self, module_class):
        sf = SpiderFoot(self.default_options)
        module = module_class()
        module.setup(sf, dict())
        return module

    def create_event(self, target_value, target_type, event_type, event_data):
        target = SpiderFootTarget(target_value, target_type)
        evt = SpiderFootEvent(event_type, event_data, '', '')
        return target, evt


@pytest.mark.usefixtures
class TestModuleIntegration_stor_db(BaseTestModuleIntegration):

    @unittest.skip("todo")
    def test_handleEvent(self):
        module = self.setup_module(sfp__stor_db)

        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        event_type = 'ROOT'
        event_data = 'example data'
        target, evt = self.create_event(target_value, target_type, event_type, event_data)

        module.setTarget(target)
        result = module.handleEvent(evt)

        self.assertIsNone(result)
