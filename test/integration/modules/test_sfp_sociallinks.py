import pytest
import unittest

from modules.sfp_sociallinks import sfp_sociallinks
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


@pytest.mark.usefixtures
class TestModuleIntegrationsociallinks(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 15,
            '_useragent': 'SpiderFoot',
            '_genericusers': 'admin,administrator,webmaster,hostmaster,postmaster,root,abuse',
            '_internettlds': 'com,net,org'
        }

    def test_handleEvent(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_sociallinks()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'EMAILADDR'
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
