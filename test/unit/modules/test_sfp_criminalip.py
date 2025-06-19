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
        # Add API key to options for testing
        options = self.default_options.copy()
        options['api_key'] = 'test_api_key'
        module.setup(self.scanner, options)
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
        # Check that all optdescs keys exist in opts
        for key in module.optdescs.keys():
            self.assertIn(key, module.opts)

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

    def test_handleEvent_domain(self):
        with patch.object(sfp_criminalip, 'queryCriminalIP') as mock_query:
            module = self.create_module_with_mocks()
            # Mock the notifyListeners method to avoid plugin framework issues
            module.notifyListeners = MagicMock()

            target_value = 'example.com'
            target_type = 'INTERNET_NAME'
            event_type = 'DOMAIN_NAME'  # Changed from INTERNET_NAME to DOMAIN_NAME
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
            mock_query.assert_called_with('example.com', 'domain')

    def test_handleEvent_phone(self):
        with patch.object(sfp_criminalip, 'queryCriminalIP') as mock_query:
            module = self.create_module_with_mocks()
            # Mock the notifyListeners method to avoid plugin framework issues
            module.notifyListeners = MagicMock()

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
            mock_query.assert_called_with('+1234567890', 'phone')

    def test_handleEvent_ip(self):
        with patch.object(sfp_criminalip, 'queryCriminalIP') as mock_query:
            module = self.create_module_with_mocks()
            # Mock the notifyListeners method to avoid plugin framework issues
            module.notifyListeners = MagicMock()

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
            mock_query.assert_called_with('1.2.3.4', 'ip')

    def test_queryCriminalIP(self):
        with patch.object(self.scanner, 'fetchUrl') as mock_fetch:
            module = self.create_module_with_mocks()

            # Mock API response
            mock_response = {
                'code': '200',
                'content': '{"name": "Example Company"}'
            }
            mock_fetch.return_value = mock_response

            result = module.queryCriminalIP('example.com', 'domain')
            expected = {"name": "Example Company"}
            self.assertEqual(result, expected)

    def test_handleEvent_api_error(self):
        with patch.object(sfp_criminalip, 'queryCriminalIP') as mock_query:
            module = self.create_module_with_mocks()
            # Mock the notifyListeners method to avoid plugin framework issues
            module.notifyListeners = MagicMock()

            target_value = 'example.com'
            target_type = 'INTERNET_NAME'
            event_type = 'DOMAIN_NAME'  # Changed from INTERNET_NAME to DOMAIN_NAME
            event_data = 'example.com'
            target, evt = self.create_test_event(
                target_value, target_type, event_type, event_data)

            # Mock API returning None (error case)
            mock_query.return_value = None

            module.setTarget(target)
            module.handleEvent(evt)
            # Verify the method was called
            mock_query.assert_called_with('example.com', 'domain')

    def test_handleEvent_no_api_key(self):
        module = self.create_module_with_mocks()
        
        # Set empty API key to trigger error
        module.opts['api_key'] = ''

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        event_type = 'INTERNET_NAME'
        event_data = 'example.com'
        target, evt = self.create_test_event(
            target_value, target_type, event_type, event_data)

        module.setTarget(target)
        result = module.handleEvent(evt)        # Check that the method handles missing API key gracefully
        self.assertIsNone(result)

    def test_handleEvent_rate_limit(self):
        module = self.create_module_with_mocks()
        
        # Set API key
        module.opts['api_key'] = 'test_key'

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        event_type = 'INTERNET_NAME'
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
