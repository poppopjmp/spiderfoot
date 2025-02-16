import pytest
import unittest

from modules.sfp_rocketreach import sfp_rocketreach
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


@pytest.mark.usefixtures
class TestModuleIntegrationRocketReach(unittest.TestCase):

    def test_handleEvent(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_rocketreach()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'EMAILADDR'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'EMAILADDR'
        event_data = 'example@example.com'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)

    def test_handleEvent_phone_number(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_rocketreach()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'PHONE_NUMBER'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'PHONE_NUMBER'
        event_data = '+1234567890'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)

    def test_handleEvent_social_media(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_rocketreach()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'SOCIAL_MEDIA'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'SOCIAL_MEDIA'
        event_data = 'https://twitter.com/example'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)
