import pytest
import unittest

from modules.sfp__stor_stdout import sfp__stor_stdout
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class BaseTestModuleIntegration(unittest.TestCase):

    def setup_module(self, module_class):
        sf = SpiderFoot(self.default_options)
        module = module_class()
        module.setup(sf, dict())
        return module

    def create_event(self, target_value, target_type, event_type, event_data):
        target = SpiderFootTarget(target_value, target_type)
        evt = SpiderFootEvent(event_type, event_data, '', '')
        return target, evt



class TestModuleIntegration_stor_stdout(BaseTestModuleIntegration):

    @unittest.skip("todo")
    def test_handleEvent(self):
        module = self.setup_module(sfp__stor_stdout)

        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        event_type = 'ROOT'
        event_data = 'example data'
        target, evt = self.create_event(
            target_value, target_type, event_type, event_data)

        module.setTarget(target)
        result = module.handleEvent(evt)

        self.assertIsNone(result)
