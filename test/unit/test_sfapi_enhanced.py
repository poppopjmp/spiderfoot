#!/usr/bin/env python3
"""
Enhanced comprehensive test suite for sfapi.py
Extends existing tests with better coverage for the modular API structure.
"""

import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os
import json
from io import BytesIO

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set testing mode
os.environ['TESTING_MODE'] = '1'

import sfapi


class TestSfApiMain(unittest.TestCase):
    """Test main function and entry point for sfapi.py."""

    @patch('sfapi.uvicorn.run')
    @patch('sfapi.argparse.ArgumentParser')
    def test_main_function_default_args(self, mock_parser_class, mock_uvicorn):
        """Test main function with default arguments."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.host = '127.0.0.1'
        mock_args.port = 8001
        mock_args.config = None
        mock_args.reload = False
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        sfapi.main()
        
        mock_uvicorn.assert_called_once_with(
            "spiderfoot.api.main:app",
            host='127.0.0.1',
            port=8001,
            reload=False,
            log_level="info"
        )

    @patch('sfapi.uvicorn.run')
    @patch('sfapi.argparse.ArgumentParser')
    def test_main_function_custom_args(self, mock_parser_class, mock_uvicorn):
        """Test main function with custom arguments."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.host = '0.0.0.0'
        mock_args.port = 9000
        mock_args.config = '/path/to/config.json'
        mock_args.reload = True
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        sfapi.main()
        
        mock_uvicorn.assert_called_once_with(
            "spiderfoot.api.main:app",
            host='0.0.0.0',
            port=9000,
            reload=True,
            log_level="info"
        )

    def test_argument_parser_setup(self):
        """Test that argument parser is properly configured."""
        with patch('sfapi.argparse.ArgumentParser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser
            
            with patch('sfapi.uvicorn.run'):
                sfapi.main()
            
            # Verify parser creation and argument additions
            mock_parser_class.assert_called_once_with(description='SpiderFoot REST API Server')
            
            # Check that arguments were added
            add_argument_calls = mock_parser.add_argument.call_args_list
            self.assertTrue(len(add_argument_calls) >= 4)  # At least 4 arguments
            
            # Verify specific arguments
            arg_names = [call[0][0] for call in add_argument_calls]
            expected_args = ['-H', '-p', '-c', '--reload']
            for expected_arg in expected_args:
                self.assertIn(expected_arg, arg_names)


class TestSfApiImports(unittest.TestCase):
    """Test import functionality and module re-exports."""

    def test_legacy_imports_available(self):
        """Test that legacy imports are available for backward compatibility."""
        # Test that important classes/functions are importable
        from sfapi import app
        self.assertIsNotNone(app)
        
        # Test legacy compatibility imports
        try:
            from sfapi import get_app_config, optional_auth
            from sfapi import ScanRequest, WorkspaceRequest, ScanResponse, WorkspaceResponse
            from sfapi import search_base, app_config
            from sfapi import SpiderFootDb, SpiderFoot, SpiderFootHelpers
            from sfapi import clean_user_input, build_excel
            from sfapi import WebSocketManager, openpyxl
            
            # All should be importable without error
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Legacy import failed: {e}")

    def test_logging_setup(self):
        """Test that logging is properly configured."""
        self.assertIsNotNone(sfapi.logger)
        self.assertEqual(sfapi.logger.name, "sfapi")

    def test_security_reference(self):
        """Test security object reference."""
        self.assertIsNotNone(sfapi.security)
        # Should be the optional_auth function
        from sfapi import optional_auth
        self.assertEqual(sfapi.security, optional_auth)

    def test_config_class_reference(self):
        """Test Config class reference setup."""
        # Config should be either a class or None
        self.assertTrue(sfapi.Config is None or callable(sfapi.Config))


class TestSfApiModularStructure(unittest.TestCase):
    """Test the modular structure and delegation to spiderfoot.api.main."""

    @patch('sfapi.app')
    def test_app_import_delegation(self, mock_app):
        """Test that app is properly imported from spiderfoot.api.main."""
        # The app should be imported from the modular structure
        import sfapi
        # Just verify it's accessible
        self.assertTrue(hasattr(sfapi, 'app'))

    def test_dependencies_import(self):
        """Test that dependencies are properly imported."""
        try:
            from sfapi import get_app_config, optional_auth, app_config
            # Should not raise ImportError
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Dependencies import failed: {e}")

    def test_models_import(self):
        """Test that API models are properly imported."""
        try:
            from sfapi import ScanRequest, WorkspaceRequest, ScanResponse, WorkspaceResponse
            # Should not raise ImportError
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Models import failed: {e}")

    def test_utils_import(self):
        """Test that utility functions are properly imported."""
        try:
            from sfapi import clean_user_input, build_excel
            # Should not raise ImportError
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Utils import failed: {e}")

    def test_websocket_import(self):
        """Test that WebSocket manager is properly imported."""
        try:
            from sfapi import WebSocketManager
            # Should not raise ImportError
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"WebSocket import failed: {e}")


class TestSfApiCompatibility(unittest.TestCase):
    """Test backward compatibility features."""

    def test_clean_user_input_function_exists(self):
        """Test that clean_user_input function is available."""
        self.assertTrue(hasattr(sfapi, 'clean_user_input'))
        self.assertTrue(callable(sfapi.clean_user_input))

    def test_build_excel_function_exists(self):
        """Test that build_excel function is available."""
        self.assertTrue(hasattr(sfapi, 'build_excel'))
        self.assertTrue(callable(sfapi.build_excel))

    def test_search_base_function_exists(self):
        """Test that search_base function is available."""
        self.assertTrue(hasattr(sfapi, 'search_base'))
        self.assertTrue(callable(sfapi.search_base))

    def test_spiderfoot_classes_available(self):
        """Test that core SpiderFoot classes are available."""
        self.assertTrue(hasattr(sfapi, 'SpiderFootDb'))
        self.assertTrue(hasattr(sfapi, 'SpiderFoot'))
        self.assertTrue(hasattr(sfapi, 'SpiderFootHelpers'))
        
        # These should be classes
        self.assertTrue(callable(sfapi.SpiderFootDb))
        self.assertTrue(callable(sfapi.SpiderFoot))

    def test_openpyxl_import(self):
        """Test that openpyxl is properly imported."""
        self.assertTrue(hasattr(sfapi, 'openpyxl'))


class TestSfApiErrorHandling(unittest.TestCase):
    """Test error handling in sfapi.py."""

    @patch('sfapi.uvicorn.run', side_effect=Exception("Server start failed"))
    @patch('sfapi.argparse.ArgumentParser')
    def test_main_handles_uvicorn_exceptions(self, mock_parser_class, mock_uvicorn):
        """Test that main function handles uvicorn startup exceptions."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.host = '127.0.0.1'
        mock_args.port = 8001
        mock_args.config = None
        mock_args.reload = False
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        # Should raise the exception (not catch it silently)
        with self.assertRaises(Exception) as context:
            sfapi.main()
        
        self.assertEqual(str(context.exception), "Server start failed")

    @patch('sfapi.argparse.ArgumentParser', side_effect=Exception("Parser creation failed"))
    def test_main_handles_parser_exceptions(self, mock_parser_class):
        """Test that main function handles argument parser exceptions."""
        # Should raise the exception
        with self.assertRaises(Exception) as context:
            sfapi.main()
        
        self.assertEqual(str(context.exception), "Parser creation failed")


class TestSfApiDocumentation(unittest.TestCase):
    """Test documentation and module metadata."""

    def test_module_docstring(self):
        """Test that module has proper docstring."""
        import sfapi
        self.assertIsNotNone(sfapi.__doc__)
        self.assertIn("SpiderFoot REST API", sfapi.__doc__)
        self.assertIn("modular", sfapi.__doc__)

    def test_main_function_docstring(self):
        """Test that main function has proper docstring."""
        self.assertIsNotNone(sfapi.main.__doc__)
        self.assertIn("Main function", sfapi.main.__doc__)
        self.assertIn("modular", sfapi.main.__doc__)


class TestSfApiIntegration(unittest.TestCase):
    """Test integration aspects of sfapi.py."""

    @patch('sfapi.uvicorn')
    def test_main_integration_with_uvicorn(self, mock_uvicorn):
        """Test main function properly integrates with uvicorn."""
        with patch('sfapi.argparse.ArgumentParser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.host = '127.0.0.1'
            mock_args.port = 8001
            mock_args.config = None
            mock_args.reload = False
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser
            
            sfapi.main()
            
            # Verify uvicorn.run was called with correct module reference
            mock_uvicorn.run.assert_called_once()
            call_args = mock_uvicorn.run.call_args
            self.assertEqual(call_args[1]['host'], '127.0.0.1')
            self.assertEqual(call_args[1]['port'], 8001)
            self.assertIn("spiderfoot.api.main:app", call_args[0])

    def test_if_name_main_execution(self):
        """Test __name__ == '__main__' execution path."""
        # This test verifies that the if __name__ == '__main__' block exists
        # and would call main() when executed directly
        
        # Read the module source to verify the pattern exists
        import inspect
        import sfapi
        
        source = inspect.getsource(sfapi)
        self.assertIn('if __name__ == "__main__":', source)
        self.assertIn('main()', source)


class TestSfApiEdgeCases(unittest.TestCase):
    """Test edge cases and unusual scenarios."""

    def test_import_without_dependencies(self):
        """Test behavior when optional dependencies are missing."""
        # This would be tested in an environment where some dependencies aren't installed
        # For now, just ensure the module loads
        import sfapi
        self.assertIsNotNone(sfapi)

    @patch('sfapi.argparse.ArgumentParser')
    def test_main_with_empty_args(self, mock_parser_class):
        """Test main function with empty/minimal arguments."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        # Set up minimal args
        mock_args.host = '127.0.0.1'
        mock_args.port = 8001
        mock_args.config = None
        mock_args.reload = False
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        with patch('sfapi.uvicorn.run') as mock_uvicorn:
            sfapi.main()
            mock_uvicorn.assert_called_once()

    def test_module_level_variables_types(self):
        """Test that module-level variables have expected types."""
        import sfapi
        
        # Logger should be a logger instance
        import logging
        self.assertIsInstance(sfapi.logger, logging.Logger)
        
        # Security should be callable (function)
        self.assertTrue(callable(sfapi.security))
        
        # Config should be either None or a class
        self.assertTrue(sfapi.Config is None or (isinstance(sfapi.Config, type) or callable(sfapi.Config)))


if __name__ == '__main__':
    unittest.main()
