import pytest
import unittest

from modules.sfp_circllu import sfp_circllu
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleCircllu(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_circllu()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_circllu()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_circllu()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_circllu()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_api_key_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_circllu()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def test_parseApiResponse_should_handle_json_data(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_circllu()
        module.setup(sf, dict())

        api_response = {
            'code': 200,
            'content': '{"success":true,"result":{"domains":["example.com"]}}'
        }

        result = module.parseApiResponse(api_response)
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        self.assertIn("domains", result.get("result", {}))

    def test_parseApiResponse_should_handle_errors(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_circllu()
        module.setup(sf, dict())

        # Test with invalid JSON
        api_response = {
            'code': 200,
            'content': 'not json'
        }

        result = module.parseApiResponse(api_response)
        self.assertIsNone(result)

        # Test with error code
        api_response = {
            'code': 401,
            'content': '{"success":false,"error":"Invalid API key"}'
        }

        result = module.parseApiResponse(api_response)
        self.assertIsNone(result)
        self.assertTrue(module.errorState)
