import pytest
import unittest

from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_fofa import sfp_fofa
from modules.sfp_netlas import sfp_netlas
from modules.sfp_rocketreach import sfp_rocketreach
from modules.sfp_zoomeye import sfp_zoomeye


@pytest.mark.usefixtures
class TestModuleIntegration(unittest.TestCase):

    def setUp(self):
        self.sf = SpiderFoot(self.default_options)

    def test_handleEvent(self):
        for module_name in dir(modules):
            if module_name.startswith('sfp_'):
                module = getattr(modules, module_name)()
                module.setup(self.sf, dict())

                target_value = 'example target value'
                target_type = 'IP_ADDRESS'
                target = SpiderFootTarget(target_value, target_type)
                module.setTarget(target)

                event_type = 'ROOT'
                event_data = 'example data'
                event_module = ''
                source_event = ''
                evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

                result = module.handleEvent(evt)

                self.assertIsNone(result)
