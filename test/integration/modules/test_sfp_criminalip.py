import pytest
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_criminalip import sfp_criminalip
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


@pytest.mark.usefixtures
class TestModuleIntegrationCriminalip(BaseTestModuleIntegration):

    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_handleEvent_domain(self, mock_query):
        module = self.setup_module(sfp_criminalip)

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        event_type = 'ROOT'
        event_data = 'example.com'
        target, evt = self.create_event(
            target_value, target_type, event_type, event_data)

        mock_response = {
            "name": "Example Company",
            "linkedin_url": "https://linkedin.com/company/example",
            "locality": "Example City",
            "country": "Example Country"
        }
        mock_query.return_value = mock_response

        module.setTarget(target)
        module.handleEvent(evt)

        events = module.sf.getEvents()
        self.assertTrue(any(e.eventType == 'COMPANY_NAME' for e in events))
        self.assertTrue(any(e.eventType == 'SOCIAL_MEDIA' for e in events))
        self.assertTrue(any(e.eventType == 'GEOINFO' for e in events))

    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_handleEvent_phone(self, mock_query):
        module = self.setup_module(sfp_criminalip)

        target_value = '+1234567890'
        target_type = 'PHONE_NUMBER'
        event_type = 'ROOT'
        event_data = '+1234567890'
        target, evt = self.create_event(
            target_value, target_type, event_type, event_data)

        mock_response = {
            "valid": True,
            "carrier": "Example Carrier",
            "location": "Example Location",
            "country": {"name": "Example Country"}
        }
        mock_query.return_value = mock_response

        module.setTarget(target)
        module.handleEvent(evt)

        events = module.sf.getEvents()
        self.assertTrue(any(e.eventType == 'PROVIDER_TELCO' for e in events))
        self.assertTrue(any(e.eventType == 'GEOINFO' for e in events))

    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_handleEvent_ip(self, mock_query):
        module = self.setup_module(sfp_criminalip)

        target_value = '1.2.3.4'
        target_type = 'IP_ADDRESS'
        event_type = 'ROOT'
        event_data = '1.2.3.4'
        target, evt = self.create_event(
            target_value, target_type, event_type, event_data)

        mock_response = {
            "city": "Example City",
            "region": "Example Region",
            "postal_code": "12345",
            "country": "Example Country",
            "continent": "Example Continent",
            "latitude": "12.3456",
            "longitude": "78.9012"
        }
        mock_query.return_value = mock_response

        module.setTarget(target)
        module.handleEvent(evt)

        events = module.sf.getEvents()
        self.assertTrue(any(e.eventType == 'GEOINFO' for e in events))
        self.assertTrue(any(e.eventType == 'PHYSICAL_COORDINATES' for e in events))

    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_queryCriminalIP(self, mock_query):
        module = self.setup_module(sfp_criminalip)

        mock_response = {
            "code": "200",
            "content": '{"name": "Example Company"}'
        }
        mock_query.return_value = mock_response

        result = module.queryCriminalIP('example.com', 'domain')
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'Example Company')

    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_handleEvent_api_error(self, mock_query):
        module = self.setup_module(sfp_criminalip)

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        event_type = 'ROOT'
        event_data = 'example.com'
        target, evt = self.create_event(
            target_value, target_type, event_type, event_data)

        mock_response = {
            "code": "500",
            "content": None
        }
        mock_query.return_value = mock_response

        module.setTarget(target)
        module.handleEvent(evt)

        self.assertTrue(module.errorState)

    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_handleEvent_rate_limit(self, mock_query):
        module = self.setup_module(sfp_criminalip)

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        event_type = 'ROOT'
        event_data = 'example.com'
        target, evt = self.create_event(
            target_value, target_type, event_type, event_data)

        mock_response = {
            "code": "429",
            "content": None
        }
        mock_query.return_value = mock_response

        module.setTarget(target)
        module.handleEvent(evt)

        self.assertFalse(module.errorState)
