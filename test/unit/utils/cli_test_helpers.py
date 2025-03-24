"""
CLI test helpers for SpiderFoot command-line tests
"""

from unittest.mock import MagicMock, patch
import os
import tempfile
import sys


def mock_cli_arguments():
    """Mock command line arguments for CLI tests."""
    # Save original arguments
    orig_args = sys.argv
    
    # Set up test arguments
    sys.argv = ['spiderfoot.py', '-l', '127.0.0.1:5001']
    
    # Return a function to restore original arguments
    def restore():
        sys.argv = orig_args
    
    return restore


def setup_cli_test_environment(test_class):
    """
    Set up a CLI test environment with mocked dependencies.
    
    Args:
        test_class: The test class instance
    """
    # Create a mock SFDB
    mock_db = MagicMock()
    patch('sflib.SpiderFootDb', return_value=mock_db).start()
    test_class.mock_db = mock_db
    
    # Mock the SpiderFootHelpers
    mock_sfh = MagicMock()
    patch('sflib.SpiderFootHelpers', return_value=mock_sfh).start()
    test_class.mock_sfh = mock_sfh
    
    # Mock the SpiderFootScanner
    mock_scanner = MagicMock()
    patch('sflib.SpiderFootScanner', return_value=mock_scanner).start()
    test_class.mock_scanner = mock_scanner
    
    # Set up default options
    test_class.default_opts = {
        '__database': ':memory:',
        '__modules__': 'modules',
        '_useragent': 'Mozilla',
        '_dnsserver': '8.8.8.8',
        '_fetchtimeout': 5,
        '__logging': True,
        '_debug': False
    }
    
    # Add cleanup to the test class's tearDown
    original_tearDown = test_class.tearDown
    def new_tearDown():
        patch.stopall()
        original_tearDown()
    
    test_class.tearDown = new_tearDown
