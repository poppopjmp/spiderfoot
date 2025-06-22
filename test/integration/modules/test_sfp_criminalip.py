import pytest
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_criminalip import sfp_criminalip
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class BaseTestModuleIntegration(unittest.TestCase):
    
    default_options = {"_useragent": "SpiderFootTestAgent", "api_key": "DUMMYKEY"}

    def setup_module(self, module_class, user_opts=None):
        opts = self.default_options.copy()
        if user_opts:
            opts.update(user_opts)
        sf = SpiderFoot(opts)
        module = module_class()
        module.setup(sf, opts)  # Pass opts as userOpts, which always contains api_key
        module.__name__ = module.__class__.__name__
        return module

    def create_event(self, target_value, target_type, event_type, event_data, module_name=None):
        target = SpiderFootTarget(target_value, target_type)
        if module_name is None:
            module_name = ''
        evt = SpiderFootEvent(event_type, event_data, module_name, None)
        return target, evt



class TestModuleIntegrationCriminalip(BaseTestModuleIntegration):
    
    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_handleEvent_domain(self, mock_query):
        module = self.setup_module(sfp_criminalip, {"api_key": "DUMMYKEY", "_useragent": "SpiderFootTestAgent"})

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        event_type = 'DOMAIN_NAME'  # Use watched event type
        event_data = 'example.com'
        target, evt = self.create_event(target_value, target_type, event_type, event_data, module.__name__)

        mock_response = {
            "name": "Example Company",
            "linkedin_url": "https://linkedin.com/company/example",
            "locality": "Example City",
            "country": "Example Country"
        }
        mock_query.return_value = mock_response

        module.setTarget(target)
        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)

        self.assertTrue(any(e.eventType == 'COMPANY_NAME' for e in events))
        self.assertTrue(any(e.eventType == 'SOCIAL_MEDIA' for e in events))
        self.assertTrue(any(e.eventType == 'GEOINFO' for e in events))

    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_handleEvent_phone(self, mock_query):
        module = self.setup_module(sfp_criminalip, {"api_key": "DUMMYKEY", "_useragent": "SpiderFootTestAgent"})

        target_value = '+1234567890'
        target_type = 'PHONE_NUMBER'
        event_type = 'PHONE_NUMBER'  # Use watched event type
        event_data = '+1234567890'
        target, evt = self.create_event(target_value, target_type, event_type, event_data, module.__name__)

        mock_response = {
            "valid": True,
            "carrier": "Example Carrier",
            "location": "Example Location",
            "country": {"name": "Example Country"}
        }
        mock_query.return_value = mock_response

        module.setTarget(target)
        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)

        self.assertTrue(any(e.eventType == 'PROVIDER_TELCO' for e in events))
        self.assertTrue(any(e.eventType == 'GEOINFO' for e in events))

    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_handleEvent_ip(self, mock_query):
        module = self.setup_module(sfp_criminalip, {"api_key": "DUMMYKEY", "_useragent": "SpiderFootTestAgent"})

        target_value = '1.2.3.4'
        target_type = 'IP_ADDRESS'
        event_type = 'IP_ADDRESS'  # Use watched event type
        event_data = '1.2.3.4'
        target, evt = self.create_event(target_value, target_type, event_type, event_data, module.__name__)

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
        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)

        self.assertTrue(any(e.eventType == 'GEOINFO' for e in events))
        self.assertTrue(any(e.eventType == 'PHYSICAL_COORDINATES' for e in events))

    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_queryCriminalIP(self, mock_query):
        module = self.setup_module(sfp_criminalip, {"api_key": "DUMMYKEY", "_useragent": "SpiderFootTestAgent"})

        mock_response = {
            "name": "Example Company"
        }
        mock_query.return_value = mock_response

        result = module.queryCriminalIP('example.com', 'domain')
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'Example Company')

    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_handleEvent_api_error(self, mock_query):
        module = self.setup_module(sfp_criminalip, {"api_key": "DUMMYKEY", "_useragent": "SpiderFootTestAgent"})

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        event_type = 'DOMAIN_NAME'  # Use watched event type
        event_data = 'example.com'
        target, evt = self.create_event(target_value, target_type, event_type, event_data, module.__name__)

        mock_response = None  # Simulate failed API call
        mock_query.return_value = mock_response

        module.setTarget(target)
        module.handleEvent(evt)

        self.assertFalse(module.errorState)

    @patch('modules.sfp_criminalip.sfp_criminalip.queryCriminalIP')
    def test_handleEvent_rate_limit(self, mock_query):
        module = self.setup_module(sfp_criminalip, {"api_key": "DUMMYKEY", "_useragent": "SpiderFootTestAgent"})

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        event_type = 'DOMAIN_NAME'  # Use watched event type
        event_data = 'example.com'
        target, evt = self.create_event(target_value, target_type, event_type, event_data, module.__name__)

        mock_response = {
            "code": "429",
            "content": None
        }
        mock_query.return_value = mock_response

        module.setTarget(target)
        module.handleEvent(evt)

        self.assertFalse(module.errorState)
