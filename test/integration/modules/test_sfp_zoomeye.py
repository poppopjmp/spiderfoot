import pytest
import unittest

from modules.sfp_zoomeye import sfp_zoomeye
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


@pytest.mark.usefixtures
class TestModuleIntegrationZoomEye(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 15,
            '_useragent': 'SpiderFoot',
            '_internettlds': 'com,net,org,info,biz,us,uk',
            '_genericusers': 'admin,administrator,webmaster,hostmaster,postmaster,root,abuse',
        }

    def test_setup(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_zoomeye()
        module.setup(sf, dict())

        self.assertIsInstance(module, sfp_zoomeye)

    def test_watchedEvents(self):
        module = sfp_zoomeye()
        self.assertEqual(module.watchedEvents(), ["DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"])

    def test_producedEvents(self):
        module = sfp_zoomeye()
        self.assertEqual(module.producedEvents(), ["INTERNET_NAME", "DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS", "RAW_RIR_DATA"])

    def test_handleEvent(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_zoomeye()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)

    def test_query(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_zoomeye()
        module.setup(sf, dict())

        result = module.query('example.com', 'web')

        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
