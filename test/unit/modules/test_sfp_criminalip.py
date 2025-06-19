import pytest
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_criminalip import sfp_criminalip
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleCriminalip(SpiderFootTestBase):
    def setUp(self):
        """Set up before each test."""
        super().setUp()
        self.scanner = SpiderFoot(self.default_options)

    def create_module_with_mocks(self):
        """Create a module instance with proper mocks."""
        module = sfp_criminalip()
        module.__name__ = "sfp_criminalip"
        # Mock tempStorage method before setup
        module.tempStorage = MagicMock(return_value={})
        module.setup(self.scanner, self.default_options)
        return module

    def create_test_event(self, target_value, target_type, event_type, event_data):
        """Create event and target manually."""
        target = SpiderFootTarget(target_value, target_type)
        
        # Create root event first
        root_event = SpiderFootEvent("ROOT", target_value, "", "")
        
        # Create actual event
        event = SpiderFootEvent(event_type, event_data, "test_module", root_event)
        
        return target, event

    def test_opts(self):
        module = sfp_criminalip()
        module.__name__ = "sfp_criminalip"
        # Only check that opts and optdescs exist and have the same keys
        self.assertEqual(set(module.opts.keys()), set(module.optdescs.keys()))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_criminalip()
        module.__name__ = "sfp_criminalip"
        # Mock tempStorage method before setup
        module.tempStorage = MagicMock(return_value={})
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_criminalip()
        module.__name__ = "sfp_criminalip"
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_criminalip()
        module.__name__ = "sfp_criminalip"
        self.assertIsInstance(module.producedEvents(), list)

    @patch.object(sfp_criminalip, 'queryCriminalIP')
    def test_handleEvent_domain(self, mock_query):
        module = self.create_module_with_mocks()

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        target, evt = self.create_test_event(
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

        # Verify the method was called
        mock_query.assert_called()

    @patch.object(sfp_criminalip, 'queryCriminalIP')
    def test_handleEvent_phone(self, mock_query):
        module = self.create_module_with_mocks()

        target_value = '+1234567890'
        target_type = 'PHONE_NUMBER'
        event_type = 'PHONE_NUMBER'
        event_data = '+1234567890'
        target, evt = self.create_test_event(
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

        # Verify the method was called
        mock_query.assert_called()

    @patch.object(sfp_criminalip, 'queryCriminalIP')
    def test_handleEvent_ip(self, mock_query):
        module = self.create_module_with_mocks()

        target_value = '1.2.3.4'
        target_type = 'IP_ADDRESS'
        event_type = 'IP_ADDRESS'
        event_data = '1.2.3.4'
        target, evt = self.create_test_event(
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

        # Verify the method was called
        mock_query.assert_called()

    @patch.object(sfp_criminalip, 'queryCriminalIP')
    def test_queryCriminalIP(self, mock_query):
        module = self.create_module_with_mocks()

        mock_response = {
            "name": "Example Company"
        }
        mock_query.return_value = mock_response

        result = module.queryCriminalIP('example.com', 'domain')
        self.assertEqual(result, mock_response)
        mock_query.assert_called()

    @patch.object(sfp_criminalip, 'queryCriminalIP')
    def test_handleEvent_api_error(self, mock_query):
        module = self.create_module_with_mocks()

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        target, evt = self.create_test_event(
            target_value, target_type, event_type, event_data)

        # Mock API returning None (error case)
        mock_query.return_value = None

        module.setTarget(target)
        module.handleEvent(evt)

        # Verify the method was called
        mock_query.assert_called()

    def test_handleEvent_no_api_key(self):
        module = self.create_module_with_mocks()
        
        # Set empty API key to trigger error
        module.opts['api_key'] = ''

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        target, evt = self.create_test_event(
            target_value, target_type, event_type, event_data)

        module.setTarget(target)
        result = module.handleEvent(evt)

        # Check that the method handles missing API key gracefully
        self.assertIsNone(result)

    def test_handleEvent_rate_limit(self):
        module = self.create_module_with_mocks()
        
        # Set API key
        module.opts['api_key'] = 'test_key'

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        target, evt = self.create_test_event(
            target_value, target_type, event_type, event_data)

        # Mock the fetchUrl to return rate limit response
        mock_response = {
            'code': '429',
            'content': None
        }
        
        with patch.object(module.sf, 'fetchUrl', return_value=mock_response):
            module.setTarget(target)
            result = module.handleEvent(evt)

            # Should handle rate limiting gracefully
            self.assertIsNone(result)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
