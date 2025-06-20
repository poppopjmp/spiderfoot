import pytest
import unittest
from unittest.mock import patch, MagicMock, Mock
import sys
from io import StringIO

from modules.sfp__stor_stdout import sfp__stor_stdout
from sflib import SpiderFoot
from spiderfoot.event import SpiderFootEvent
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleStor_stdout(SpiderFootTestBase):
    """Comprehensive test suite for stdout storage module.
    
    Tests output formatting, filtering, and proper event handling.
    """

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Create SpiderFoot instance
        self.sf_instance = SpiderFoot(self.default_options)
        
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()

    @unittest.skip("This module contains an extra private option")
    def test_opts(self):
        module = sfp__stor_stdout()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test basic setup functionality."""
        module = sfp__stor_stdout()
        module.setup(self.sf_instance, dict())
        
        self.assertIsNotNone(module.sf)
        self.assertIsNotNone(module.opts)

    def test_setup_with_options(self):
        """Test setup with custom options."""
        module = sfp__stor_stdout()
        custom_opts = {
            'maxdata': 100,
            'format': 'json'
        }
        module.setup(self.sf_instance, custom_opts)
        
        # Verify options were set correctly
        for key, value in custom_opts.items():
            if key in module.opts:
                self.assertEqual(module.opts[key], value)

    def test_watchedEvents_should_return_list(self):
        """Test that watchedEvents returns a list."""
        module = sfp__stor_stdout()
        events = module.watchedEvents()
        self.assertIsInstance(events, list)
        # Should watch all events
        self.assertIn("*", events)

    def test_producedEvents_should_return_list(self):
        """Test that producedEvents returns a list."""
        module = sfp__stor_stdout()
        events = module.producedEvents()
        self.assertIsInstance(events, list)

    @patch('sys.stdout', new_callable=StringIO)
    def test_handle_event_basic_output(self, mock_stdout):
        """Test basic event handling and output."""
        module = sfp__stor_stdout()
        module.setup(self.sf_instance, dict())
        
        # Create test event
        test_event = SpiderFootEvent("IP_ADDRESS", "192.168.1.1", "test_module", None)
        test_event.confidence = 100
        test_event.visibility = 1
        test_event.risk = 0
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        module.handleEvent(test_event)
        
        # Check that something was written to stdout
        output = mock_stdout.getvalue()
        self.assertIn("192.168.1.1", output)
        self.assertIn("IP_ADDRESS", output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_handle_event_with_data_truncation(self, mock_stdout):
        """Test event handling with data truncation."""
        module = sfp__stor_stdout()
        module.setup(self.sf_instance, {'maxdata': 10})  # Very small limit
        
        # Create test event with large data
        large_data = "x" * 100  # 100 characters
        test_event = SpiderFootEvent("LARGE_DATA", large_data, "test_module", None)
        test_event.confidence = 100
        test_event.visibility = 1
        test_event.risk = 0
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        module.handleEvent(test_event)
        
        # Check that data was truncated
        output = mock_stdout.getvalue()
        self.assertIn("LARGE_DATA", output)
        # Should contain truncated marker
        self.assertTrue(len(output) < len(large_data) + 50)  # Much shorter than original

    @patch('sys.stdout', new_callable=StringIO)
    def test_handle_event_disabled(self, mock_stdout):
        """Test that no output occurs when module is disabled."""
        module = sfp__stor_stdout()
        module.setup(self.sf_instance, {'_store': False})
        
        # Create test event
        test_event = SpiderFootEvent("IP_ADDRESS", "192.168.1.1", "test_module", None)
        
        module.handleEvent(test_event)
        
        # Check that nothing was written to stdout
        output = mock_stdout.getvalue()
        self.assertEqual(output, "")

    @patch('sys.stdout', new_callable=StringIO)
    def test_handle_multiple_events(self, mock_stdout):
        """Test handling multiple events."""
        module = sfp__stor_stdout()
        module.setup(self.sf_instance, dict())
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        # Create multiple test events
        events = [
            SpiderFootEvent("IP_ADDRESS", "192.168.1.1", "test_module", None),
            SpiderFootEvent("DOMAIN_NAME", "example.com", "test_module", None),
            SpiderFootEvent("URL", "http://example.com", "test_module", None)
        ]
        
        for event in events:
            event.confidence = 100
            event.visibility = 1
            event.risk = 0
            module.handleEvent(event)
        
        # Check that all events were output
        output = mock_stdout.getvalue()
        self.assertIn("192.168.1.1", output)
        self.assertIn("example.com", output)
        self.assertIn("http://example.com", output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_handle_event_with_special_characters(self, mock_stdout):
        """Test handling events with special characters."""
        module = sfp__stor_stdout()
        module.setup(self.sf_instance, dict())
        
        # Create test event with special characters
        special_data = "test\nwith\ttabs\rand\x00nulls"
        test_event = SpiderFootEvent("SPECIAL_DATA", special_data, "test_module", None)
        test_event.confidence = 100
        test_event.visibility = 1
        test_event.risk = 0
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        # Should handle special characters gracefully
        try:
            module.handleEvent(test_event)
            output = mock_stdout.getvalue()
            # Should produce some output without crashing
            self.assertIsInstance(output, str)
        except Exception as e:
            self.fail(f"Module should handle special characters gracefully: {e}")

    @patch('sys.stdout', new_callable=StringIO)
    def test_handle_event_unicode(self, mock_stdout):
        """Test handling events with Unicode characters."""
        module = sfp__stor_stdout()
        module.setup(self.sf_instance, dict())
        
        # Create test event with Unicode characters
        unicode_data = "测试数据 with émojis 🚀"
        test_event = SpiderFootEvent("UNICODE_DATA", unicode_data, "test_module", None)
        test_event.confidence = 100
        test_event.visibility = 1
        test_event.risk = 0
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        # Should handle Unicode characters gracefully
        try:
            module.handleEvent(test_event)
            output = mock_stdout.getvalue()
            # Should produce some output without crashing
            self.assertIsInstance(output, str)
        except Exception as e:
            self.fail(f"Module should handle Unicode characters gracefully: {e}")

    def test_output_formatting_consistency(self):
        """Test that output formatting is consistent."""
        module = sfp__stor_stdout()
        module.setup(self.sf_instance, dict())
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        # Test that the module has consistent formatting methods
        # This is a structural test to ensure the module maintains its interface
        self.assertTrue(hasattr(module, 'handleEvent'))
        self.assertTrue(hasattr(module, 'setup'))
        self.assertTrue(hasattr(module, 'watchedEvents'))
        self.assertTrue(hasattr(module, 'producedEvents'))

    @patch('sys.stdout')
    def test_stdout_error_handling(self, mock_stdout):
        """Test error handling when stdout operations fail."""
        # Simulate stdout write error
        mock_stdout.write.side_effect = IOError("Stdout write failed")
        
        module = sfp__stor_stdout()
        module.setup(self.sf_instance, dict())
        
        # Create test event
        test_event = SpiderFootEvent("IP_ADDRESS", "192.168.1.1", "test_module", None)
        test_event.confidence = 100
        test_event.visibility = 1
        test_event.risk = 0
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        # Should handle stdout errors gracefully without crashing
        try:
            module.handleEvent(test_event)
        except Exception as e:
            self.fail(f"Module should handle stdout errors gracefully: {e}")

    def test_empty_event_data(self):
        """Test handling of events with empty data."""
        module = sfp__stor_stdout()
        module.setup(self.sf_instance, dict())
        
        # Create test event with empty data
        test_event = SpiderFootEvent("EMPTY_DATA", "", "test_module", None)
        test_event.confidence = 100
        test_event.visibility = 1
        test_event.risk = 0
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        # Should handle empty data gracefully
        try:
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                module.handleEvent(test_event)
                output = mock_stdout.getvalue()
                # Should still produce some output for the event type
                self.assertIn("EMPTY_DATA", output)
        except Exception as e:
            self.fail(f"Module should handle empty data gracefully: {e}")

    def test_none_event_data(self):
        """Test handling of events with None data."""
        module = sfp__stor_stdout()
        module.setup(self.sf_instance, dict())
        
        # Create test event with None data
        test_event = SpiderFootEvent("NULL_DATA", None, "test_module", None)
        test_event.confidence = 100
        test_event.visibility = 1
        test_event.risk = 0
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        # Should handle None data gracefully
        try:
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                module.handleEvent(test_event)
                output = mock_stdout.getvalue()
                # Should still produce some output for the event type
                self.assertIn("NULL_DATA", output)
        except Exception as e:
            self.fail(f"Module should handle None data gracefully: {e}")
