import pytest
import unittest

from modules.sfp_fofa import sfp_fofa
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


@pytest.mark.usefixtures
class TestModuleIntegrationFofa(unittest.TestCase):

    def test_setup(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_fofa()
        module.setup(sf, dict())

        self.assertIsNotNone(module.sf)
        self.assertIsNotNone(module.results)
        self.assertFalse(module.errorState)

    def test_watchedEvents(self):
        module = sfp_fofa()
        self.assertEqual(module.watchedEvents(), ["DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"])

    def test_producedEvents(self):
        module = sfp_fofa()
        self.assertEqual(module.producedEvents(), ["INTERNET_NAME", "DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS", "RAW_RIR_DATA"])

    @unittest.skip("todo")
    def test_handleEvent(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_fofa()
        module.setup(sf, dict())

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

    @unittest.skip("todo")
    def test_query(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_fofa()
        module.setup(sf, dict())

        query = 'example query'
        result = module.query(query)

        self.assertIsNotNone(result)
