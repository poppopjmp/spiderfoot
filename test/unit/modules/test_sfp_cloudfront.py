# filepath: spiderfoot/test/unit/modules/test_sfp_cloudfront.py
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_cloudfront import sfp_cloudfront
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleCloudfront(SpiderFootTestBase):
    """Test Cloudfront module."""

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        self.scanner = SpiderFoot(self.default_options)

    def test_opts(self):
        """Test the module options."""
        module = sfp_cloudfront()
        module.__name__ = "sfp_cloudfront"
        
        # Test that opts and optdescs are dictionaries
        self.assertIsInstance(module.opts, dict)
        self.assertIsInstance(module.optdescs, dict)
        
        # Test that all keys in optdescs exist in opts
        # (opts may have more keys due to inheritance from base class)
        for key in module.optdescs.keys():
            self.assertIn(key, module.opts, f"Option '{key}' found in optdescs but not in opts")

    def test_setup(self):
        """
        Test setup(self, sfc, userOpts=dict())
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_cloudfront()
        module.__name__ = "sfp_cloudfront"
        # Mock tempStorage method
        module.tempStorage = MagicMock(return_value={})
        module.setup(sf, dict())
        
        # Test that the module was set up correctly
        self.assertEqual(module.sf, sf)
        self.assertIsNotNone(module.results)

    def test_watchedEvents_should_return_list(self):
        """Test the watchedEvents function returns a list."""
        module = sfp_cloudfront()
        module.__name__ = "sfp_cloudfront"
        result = module.watchedEvents()
        self.assertIsInstance(result, list)
        expected_events = ["DOMAIN_NAME", "INTERNET_NAME", "AFFILIATE_INTERNET_NAME"]
        self.assertEqual(result, expected_events)

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = sfp_cloudfront()
        module.__name__ = "sfp_cloudfront"
        result = module.producedEvents()
        self.assertIsInstance(result, list)
        expected_events = [
            "CLOUD_PROVIDER",
            "CLOUD_INSTANCE_TYPE", 
            "WEBSERVER_BANNER",
            "RAW_DNS_RECORDS"
        ]
        self.assertEqual(result, expected_events)

    @patch('dns.resolver.resolve')
    def test_queryDns_cloudfront_found(self, mock_resolve):
        """Test queryDns when CloudFront CNAME is found."""
        module = sfp_cloudfront()
        module.__name__ = "sfp_cloudfront"
        module.tempStorage = MagicMock(return_value={})
        module.setup(self.scanner, {})
        
        # Mock DNS response with CloudFront domain
        mock_answer = MagicMock()
        mock_answer.__str__ = lambda x: "d123456.cloudfront.net."
        mock_resolve.return_value = [mock_answer]
        
        result = module.queryDns("example.com")
        self.assertEqual(result, "d123456.cloudfront.net")

    @patch('dns.resolver.resolve')
    def test_queryDns_no_cloudfront(self, mock_resolve):
        """Test queryDns when no CloudFront CNAME is found."""
        module = sfp_cloudfront()
        module.__name__ = "sfp_cloudfront"
        module.tempStorage = MagicMock(return_value={})
        module.setup(self.scanner, {})
        
        # Mock DNS response without CloudFront domain
        mock_answer = MagicMock()
        mock_answer.__str__ = lambda x: "example.cdn.com."
        mock_resolve.return_value = [mock_answer]
        
        result = module.queryDns("example.com")
        self.assertIsNone(result)

    def test_checkHeaders_cloudfront_found(self):
        """Test checkHeaders when CloudFront headers are found."""
        module = sfp_cloudfront()
        module.__name__ = "sfp_cloudfront"
        module.tempStorage = MagicMock(return_value={})
        module.setup(self.scanner, self.default_options)
        
        # Mock HTTP response with CloudFront headers
        mock_response = {
            'headers': {
                'X-Amz-Cf-Id': 'cloudfront-request-id-123',
                'Via': '1.1 cloudfront'
            }
        }
        
        with patch.object(module.sf, 'fetchUrl', return_value=mock_response):
            result = module.checkHeaders("example.com")
            self.assertTrue(result)

    def test_checkHeaders_no_cloudfront(self):
        """Test checkHeaders when no CloudFront headers are found."""
        module = sfp_cloudfront()
        module.__name__ = "sfp_cloudfront"
        module.tempStorage = MagicMock(return_value={})
        module.setup(self.scanner, self.default_options)
        
        # Mock HTTP response without CloudFront headers
        mock_response = {
            'headers': {
                'Server': 'nginx',
                'Content-Type': 'text/html'
            }
        }
        
        with patch.object(module.sf, 'fetchUrl', return_value=mock_response):
            result = module.checkHeaders("example.com")
            self.assertFalse(result)

    @patch.object(sfp_cloudfront, 'queryDns')
    def test_handleEvent_cloudfront_detected_via_dns(self, mock_queryDns):
        """Test handleEvent when CloudFront is detected via DNS."""
        module = sfp_cloudfront()
        module.__name__ = "sfp_cloudfront"
        module.tempStorage = MagicMock(return_value={})
        module.setup(self.scanner, self.default_options)
        
        # Mock DNS detection
        mock_queryDns.return_value = "d123456.cloudfront.net"
        
        # Mock notifyListeners
        module.notifyListeners = MagicMock()
        
        # Create test event
        root_event = SpiderFootEvent("ROOT", "example.com", "", "")
        event = SpiderFootEvent("DOMAIN_NAME", "example.com", "test_module", root_event)
        
        # Set target
        target = SpiderFootTarget("example.com", "INTERNET_NAME")
        module.setTarget(target)
        
        module.handleEvent(event)
        
        # Verify that events were generated
        self.assertTrue(module.notifyListeners.called)
        self.assertGreaterEqual(module.notifyListeners.call_count, 3)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()


if __name__ == '__main__':
    unittest.main()
