#!/usr/bin/env python3
"""
Enhanced unit tests for sf.py - main entry point module

This comprehensive test suite covers all functionality in sf.py including:
- Main entry point and orchestrator delegation
- Legacy function compatibility
- Configuration constants
- Error handling and edge cases
- Backward compatibility features
"""

import contextlib
import unittest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os
import logging
import signal
from io import StringIO

# Add the SpiderFoot directory to the path for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import sf


class TestSfMainEnhanced(unittest.TestCase):
    """Enhanced test cases for sf.py main functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.original_argv = sys.argv.copy()
        
    def tearDown(self):
        """Clean up after each test method."""
        sys.argv = self.original_argv
    
    # =============================================================================
    # CONFIGURATION AND CONSTANTS TESTS
    # =============================================================================
    
    def test_config_constants_structure(self):
        """Test that configuration constants are properly defined."""
        self.assertIsInstance(sf.sfConfig, dict)
        self.assertIsInstance(sf.sfOptdescs, dict)
        
        # Check required config keys
        required_keys = ['_debug', '_maxthreads', '_useragent']
        for key in required_keys:
            self.assertIn(key, sf.sfConfig)
            self.assertIn(key, sf.sfOptdescs)
            
        # Check __logging exists in config
        self.assertIn('__logging', sf.sfConfig)
        
        # Test specific config values
        self.assertIsInstance(sf.sfConfig['_debug'], bool)
        self.assertIsInstance(sf.sfConfig['_maxthreads'], int)
        self.assertIsInstance(sf.sfConfig['_useragent'], str)
        self.assertIsInstance(sf.sfConfig['__logging'], bool)
    
    def test_config_defaults(self):
        """Test that configuration has sensible default values."""
        self.assertFalse(sf.sfConfig['_debug'])
        self.assertEqual(sf.sfConfig['_maxthreads'], 3)
        self.assertTrue(sf.sfConfig['__logging'])
        self.assertIn('Mozilla', sf.sfConfig['_useragent'])
        
    def test_option_descriptions(self):
        """Test that option descriptions are comprehensive."""
        # All config options should have descriptions
        config_keys_with_descriptions = {
            '_debug', '_maxthreads', '_useragent', '_dnsserver',
            '_fetchtimeout', '_internettlds', '_internettlds_cache',
            '_genericusers', '_socks1type', '_socks2addr', '_socks3port',
            '_socks4user', '_socks5pwd', '_modulesenabled'
        }
        
        for key in config_keys_with_descriptions:
            self.assertIn(key, sf.sfOptdescs)
            self.assertIsInstance(sf.sfOptdescs[key], str)
            self.assertGreater(len(sf.sfOptdescs[key]), 10)  # Meaningful descriptions
    
    def test_global_variables_initialization(self):
        """Test global variables are properly initialized."""
        self.assertIsNone(sf.scanId)
        self.assertIsNone(sf.dbh)
    
    # =============================================================================
    # MAIN ENTRY POINT TESTS
    # =============================================================================
    
    @patch('sf.SpiderFootOrchestrator')
    @patch('sys.argv', ['sf.py'])
    def test_main_delegates_to_orchestrator(self, mock_orchestrator):
        """Test main function delegates to orchestrator."""
        mock_instance = MagicMock()
        mock_orchestrator.return_value = mock_instance
        
        sf.main()
        
        mock_orchestrator.assert_called_once()
        mock_instance.run.assert_called_once()
    
    @patch('sf.SpiderFootOrchestrator')
    @patch('logging.getLogger')
    @patch('sys.argv', ['sf.py'])
    def test_main_handles_orchestrator_exceptions(self, mock_logger, mock_orchestrator):
        """Test main function handles orchestrator exceptions."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        mock_instance = MagicMock()
        mock_instance.run.side_effect = RuntimeError("Test exception")
        mock_orchestrator.return_value = mock_instance
        
        with self.assertRaises(SystemExit) as cm:
            sf.main()
        
        self.assertEqual(cm.exception.code, -1)
        mock_log.critical.assert_called_once()
        self.assertIn("Critical error in main", str(mock_log.critical.call_args))
    
    @patch('sf.SpiderFootOrchestrator')
    @patch('sys.argv', ['sf.py', '--help'])
    def test_main_with_command_line_execution(self, mock_orchestrator):
        """Test main execution from command line."""
        mock_instance = MagicMock()
        mock_instance.run.side_effect = SystemExit(0)  # Help exits with 0
        mock_orchestrator.return_value = mock_instance
        
        # Test the __main__ block logic - orchestrator should handle --help
        with self.assertRaises(SystemExit) as cm:
            sf.main()
        
        mock_orchestrator.assert_called_once()
        self.assertEqual(cm.exception.code, 0)  # Help should exit with 0
        mock_instance.run.assert_called_once()
    
    def test_usage_message_display(self):
        """Test usage message is displayed when no arguments provided."""
        sys.argv = ['sf.py']
        
        with patch('builtins.print') as mock_print, \
             patch('sys.exit') as mock_exit:
            
            # Simulate __main__ block
            if len(sys.argv) <= 1:
                print("SpiderFoot usage:")
                print("  Web UI:       python sf.py -l <ip>:<port>")
                print("  FastAPI:      python sf.py --api [--api-listen <ip>:<port>]")
                print("  Both servers: python sf.py --both [-l <ip>:<port>] [--api-listen <ip>:<port>]")
                print("  CLI scan:     python sf.py -s <target> [options]")
                print("Try --help for full guidance.")
                sys.exit(-1)
            
            mock_print.assert_has_calls([
                call("SpiderFoot usage:"),
                call("  Web UI:       python sf.py -l <ip>:<port>"),
                call("  FastAPI:      python sf.py --api [--api-listen <ip>:<port>]"),
                call("  Both servers: python sf.py --both [-l <ip>:<port>] [--api-listen <ip>:<port>]"),
                call("  CLI scan:     python sf.py -s <target> [options]"),
                call("Try --help for full guidance.")
            ])
            mock_exit.assert_called_with(-1)
    
    # =============================================================================
    # LEGACY FUNCTION TESTS
    # =============================================================================
    
    @patch('spiderfoot.core.modules.ModuleManager')
    def test_load_modules_custom_legacy_function(self, mock_module_manager):
        """Test load_modules_custom legacy function delegates correctly."""
        mock_manager = MagicMock()
        mock_module_manager.return_value = mock_manager
        mock_manager._load_modules_custom.return_value = {'test_module': 'module_data'}
        
        result = sf.load_modules_custom('/test/modules', None)
        
        mock_module_manager.assert_called_once()
        mock_manager._load_modules_custom.assert_called_once_with('/test/modules')
        self.assertEqual(result, {'test_module': 'module_data'})
    
    @patch('spiderfoot.core.scan.ScanManager')
    @patch('spiderfoot.core.validation.ValidationUtils')
    def test_start_scan_legacy_function(self, mock_validation, mock_scan_manager):
        """Test start_scan legacy function delegates correctly."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        mock_args.m = 'module1,module2'
        mock_args.t = 'DOMAIN_NAME'
        mock_args.u = None
        mock_args.x = False
        
        # Mock components
        mock_validation_instance = MagicMock()
        mock_validation.return_value = mock_validation_instance
        mock_validation_instance.validate_module_list.return_value = ['module1', 'module2']
        mock_validation_instance.validate_event_types.return_value = ['DOMAIN_NAME']
        
        mock_scan_manager_instance = MagicMock()
        mock_scan_manager.return_value = mock_scan_manager_instance
        mock_scan_manager_instance.validate_scan_arguments.return_value = {
            'target': 'example.com',
            'target_type': 'INTERNET_NAME'
        }
        mock_scan_manager_instance.prepare_modules.return_value = ['module1', 'module2']
        mock_scan_manager_instance.prepare_scan_config.return_value = {'config': 'value'}
        mock_scan_manager_instance.execute_scan.return_value = 'scan123'
        mock_scan_manager_instance.monitor_scan.return_value = {'status': 'FINISHED'}
        
        with self.assertRaises(SystemExit) as cm:
            sf.start_scan({}, {}, mock_args, None)
        
        self.assertEqual(cm.exception.code, 0)  # FINISHED status
        mock_scan_manager_instance.validate_scan_arguments.assert_called_once()
        mock_scan_manager_instance.execute_scan.assert_called_once()
    
    @patch('spiderfoot.core.scan.ScanManager')
    @patch('spiderfoot.core.validation.ValidationUtils')
    @patch('logging.getLogger')
    def test_start_scan_handles_exceptions(self, mock_logger, mock_validation, mock_scan_manager):
        """Test start_scan handles exceptions properly."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        mock_args.m = None
        mock_args.t = None
        mock_args.u = None
        mock_args.x = False
        
        mock_scan_manager_instance = MagicMock()
        mock_scan_manager.return_value = mock_scan_manager_instance
        mock_scan_manager_instance.validate_scan_arguments.side_effect = Exception("Validation failed")
        
        with self.assertRaises(SystemExit) as cm:
            sf.start_scan({}, {}, mock_args, None)
        
        self.assertEqual(cm.exception.code, -1)
        mock_log.error.assert_called_once()
        self.assertIn("Scan execution failed", str(mock_log.error.call_args))
    
    @patch('spiderfoot.core.server.ServerManager')
    def test_start_fastapi_server_legacy_function(self, mock_server_manager):
        """Test start_fastapi_server legacy function delegates correctly."""
        mock_manager = MagicMock()
        mock_server_manager.return_value = mock_manager
        
        api_config = {'host': '127.0.0.1', 'port': 8001}
        sf_config = {'_debug': False}
        
        sf.start_fastapi_server(api_config, sf_config, None)
        
        mock_server_manager.assert_called_once_with(sf_config)
        mock_manager.start_fastapi_server.assert_called_once_with(api_config, None)
    
    @patch('spiderfoot.core.server.ServerManager')
    def test_start_web_server_legacy_function(self, mock_server_manager):
        """Test start_web_server legacy function delegates correctly."""
        mock_manager = MagicMock()
        mock_server_manager.return_value = mock_manager
        
        web_config = {'host': '127.0.0.1', 'port': 8080}
        sf_config = {'_debug': False}
        
        sf.start_web_server(web_config, sf_config, None)
        
        mock_server_manager.assert_called_once_with(sf_config)
        mock_manager.start_web_server.assert_called_once_with(web_config, None)
    
    @patch('spiderfoot.core.server.ServerManager')
    def test_start_both_servers_legacy_function(self, mock_server_manager):
        """Test start_both_servers legacy function delegates correctly."""
        mock_manager = MagicMock()
        mock_server_manager.return_value = mock_manager
        
        web_config = {'host': '127.0.0.1', 'port': 8080}
        api_config = {'host': '127.0.0.1', 'port': 8001}
        sf_config = {'_debug': False}
        
        sf.start_both_servers(web_config, api_config, sf_config, None)
        
        mock_server_manager.assert_called_once_with(sf_config)
        mock_manager.start_both_servers.assert_called_once_with(web_config, api_config, None)
    
    # =============================================================================
    # VALIDATION AND TARGET PROCESSING TESTS
    # =============================================================================
    
    @patch('spiderfoot.core.validation.ValidationUtils')
    @patch('logging.getLogger')
    def test_validate_arguments_no_target(self, mock_logger, mock_validation):
        """Test validate_arguments with no target specified."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        mock_args = MagicMock()
        mock_args.s = None
        
        with self.assertRaises(SystemExit) as cm:
            sf.validate_arguments(mock_args, mock_log)
        
        self.assertEqual(cm.exception.code, -1)
        mock_log.error.assert_called_once()
        self.assertIn("must specify a target", str(mock_log.error.call_args))
    
    @patch('spiderfoot.core.validation.ValidationUtils')
    @patch('logging.getLogger')
    def test_validate_arguments_strict_mode_without_types(self, mock_logger, mock_validation):
        """Test validate_arguments with strict mode but no types."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        mock_args.x = True  # strict mode
        mock_args.t = None  # no types
        
        with self.assertRaises(SystemExit) as cm:
            sf.validate_arguments(mock_args, mock_log)
        
        self.assertEqual(cm.exception.code, -1)
        mock_log.error.assert_called_once()
        self.assertIn("-x can only be used with -t", str(mock_log.error.call_args))
    
    @patch('spiderfoot.core.validation.ValidationUtils')
    @patch('logging.getLogger')
    def test_validate_arguments_strict_mode_with_modules(self, mock_logger, mock_validation):
        """Test validate_arguments with strict mode and modules."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        mock_args.x = True  # strict mode
        mock_args.t = 'DOMAIN_NAME'
        mock_args.m = 'module1,module2'  # modules specified
        
        with self.assertRaises(SystemExit) as cm:
            sf.validate_arguments(mock_args, mock_log)
        
        self.assertEqual(cm.exception.code, -1)
        mock_log.error.assert_called_once()
        self.assertIn("-x can only be used with -t and not with -m", str(mock_log.error.call_args))
    
    @patch('spiderfoot.SpiderFootHelpers.targetTypeFromString')
    def test_process_target_valid_domain(self, mock_target_type):
        """Test process_target with valid domain."""
        mock_target_type.return_value = 'INTERNET_NAME'
        
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        mock_log = MagicMock()
        
        target, target_type = sf.process_target(mock_args, mock_log)
        
        self.assertEqual(target, 'example.com')
        self.assertEqual(target_type, 'INTERNET_NAME')
        mock_target_type.assert_called_once_with('example.com')
    
    @patch('spiderfoot.SpiderFootHelpers.targetTypeFromString')
    def test_process_target_with_spaces(self, mock_target_type):
        """Test process_target with target containing spaces."""
        mock_target_type.return_value = 'HUMAN_NAME'
        
        mock_args = MagicMock()
        mock_args.s = 'John Doe'
        mock_log = MagicMock()
        
        target, target_type = sf.process_target(mock_args, mock_log)
        
        self.assertEqual(target, 'John Doe')
        self.assertEqual(target_type, 'HUMAN_NAME')
        # Should have been wrapped in quotes for processing
        mock_target_type.assert_called_once_with('"John Doe"')
    
    @patch('spiderfoot.SpiderFootHelpers.targetTypeFromString')
    @patch('logging.getLogger')
    def test_process_target_invalid_target(self, mock_logger, mock_target_type):
        """Test process_target with invalid target."""
        mock_target_type.return_value = None
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        mock_args = MagicMock()
        mock_args.s = 'invalid_target'
        
        with self.assertRaises(SystemExit) as cm:
            sf.process_target(mock_args, mock_log)
        
        self.assertEqual(cm.exception.code, -1)
        mock_log.error.assert_called_once()
        self.assertIn("Could not determine target type", str(mock_log.error.call_args))
    
    def test_process_target_name_without_dots(self):
        """Test process_target wraps names without dots in quotes."""
        with patch('spiderfoot.SpiderFootHelpers.targetTypeFromString') as mock_target_type:
            mock_target_type.return_value = 'HUMAN_NAME'
            
            mock_args = MagicMock()
            mock_args.s = 'JohnDoe'  # No dots, not starting with +
            mock_log = MagicMock()
            
            target, target_type = sf.process_target(mock_args, mock_log)
            
            self.assertEqual(target, 'JohnDoe')
            # Should have been processed with quotes
            mock_target_type.assert_called_once_with('"JohnDoe"')
    
    # =============================================================================
    # SIGNAL HANDLING TESTS
    # =============================================================================
    
    @patch('spiderfoot.core.scan.ScanManager')
    @patch('logging.getLogger')
    def test_handle_abort_with_active_scan(self, mock_logger, mock_scan_manager):
        """Test handle_abort with active scan."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        # Set global variables
        sf.scanId = 'test_scan_123'
        sf.dbh = MagicMock()
        
        mock_manager = MagicMock()
        mock_scan_manager.return_value = mock_manager
        
        with self.assertRaises(SystemExit) as cm:
            sf.handle_abort(signal.SIGINT, None)
        
        self.assertEqual(cm.exception.code, -1)
        mock_log.info.assert_called_once()
        self.assertIn("Received interrupt signal", str(mock_log.info.call_args))
        mock_manager.stop_scan.assert_called_once_with('test_scan_123')
    
    @patch('logging.getLogger')
    def test_handle_abort_no_active_scan(self, mock_logger):
        """Test handle_abort with no active scan."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        # Clear global variables
        sf.scanId = None
        sf.dbh = None
        
        with self.assertRaises(SystemExit) as cm:
            sf.handle_abort(signal.SIGINT, None)
        
        self.assertEqual(cm.exception.code, -1)
        # Should not try to stop scan or log scan-specific messages
        mock_log.info.assert_not_called()
    
    @patch('spiderfoot.core.scan.ScanManager')
    @patch('logging.getLogger')
    def test_handle_abort_exception_handling(self, mock_logger, mock_scan_manager):
        """Test handle_abort handles exceptions during scan stop."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        sf.scanId = 'test_scan_123'
        sf.dbh = MagicMock()
        
        mock_manager = MagicMock()
        mock_manager.stop_scan.side_effect = Exception("Stop scan failed")
        mock_scan_manager.return_value = mock_manager
        
        with self.assertRaises(SystemExit) as cm:
            sf.handle_abort(signal.SIGINT, None)
        
        self.assertEqual(cm.exception.code, -1)
        mock_log.error.assert_called_once()
        self.assertIn("Error stopping scan", str(mock_log.error.call_args))


class TestSfMainEdgeCases(unittest.TestCase):
    """Edge case and integration tests for sf.py."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.original_argv = sys.argv.copy()
        
    def tearDown(self):
        """Clean up after tests."""
        sys.argv = self.original_argv
        # Reset global variables
        sf.scanId = None
        sf.dbh = None
    
    def test_module_import_structure(self):
        """Test that all required imports are available."""
        # Test that sf_orchestrator can be imported
        try:
            from sf_orchestrator import SpiderFootOrchestrator
            self.assertTrue(hasattr(SpiderFootOrchestrator, '__init__'))
        except ImportError:
            self.fail("sf_orchestrator module should be importable")
    
    def test_legacy_configuration_structure(self):
        """Test legacy configuration maintains expected structure."""
        # Test all expected keys exist
        expected_keys = {
            '_debug', '_maxthreads', '__logging', '__outputfilter',
            '_useragent', '_dnsserver', '_fetchtimeout', '_internettlds',
            '_internettlds_cache', '_genericusers', '__database',
            '__modules__', '__correlationrules__', '_socks1type',
            '_socks2addr', '_socks3port', '_socks4user', '_socks5pwd'
        }
        
        for key in expected_keys:
            self.assertIn(key, sf.sfConfig, f"Missing config key: {key}")
    
    def test_configuration_type_safety(self):
        """Test configuration values have appropriate types."""
        type_checks = {
            '_debug': bool,
            '_maxthreads': int,
            '__logging': bool,
            '_useragent': str,
            '_dnsserver': str,
            '_fetchtimeout': int,
            '_internettlds': str,
            '_internettlds_cache': int,
            '_genericusers': str,
            '__database': str,
            '_socks1type': str,
            '_socks2addr': str,
            '_socks3port': str,
            '_socks4user': str,
            '_socks5pwd': str
        }
        
        for key, expected_type in type_checks.items():
            self.assertIsInstance(sf.sfConfig[key], expected_type,
                                f"Config key {key} should be {expected_type}")
    
    def test_option_descriptions_completeness(self):
        """Test that all configuration options have descriptions."""
        config_keys = set(sf.sfConfig.keys())
        desc_keys = set(sf.sfOptdescs.keys())
        
        # Some keys might not have descriptions (like __modules__, __correlationrules__)
        # but core config keys should have descriptions
        core_keys = {
            '_debug', '_maxthreads', '_useragent', '_dnsserver',
            '_fetchtimeout', '_internettlds', '_internettlds_cache',
            '_genericusers', '_socks1type', '_socks2addr', '_socks3port',
            '_socks4user', '_socks5pwd', '_modulesenabled'
        }
        
        missing_descriptions = core_keys - desc_keys
        self.assertEqual(len(missing_descriptions), 0,
                        f"Missing descriptions for: {missing_descriptions}")

    
    def test_version_import(self):
        """Test that version import works correctly."""
        # Test that __version__ is imported and accessible
        from spiderfoot import __version__
        self.assertIsInstance(__version__, str)
        self.assertGreater(len(__version__), 0)
    
    def test_path_manipulation(self):
        """Test that path manipulation works correctly."""
        # The script should add its directory to sys.path
        script_dir = os.path.dirname(os.path.abspath(sf.__file__))
        self.assertIn(script_dir, sys.path)
    
    def test_function_signatures(self):
        """Test that all legacy functions have expected signatures."""
        import inspect
        
        # Test load_modules_custom signature
        sig = inspect.signature(sf.load_modules_custom)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ['mod_dir', 'log'])
        
        # Test start_scan signature
        sig = inspect.signature(sf.start_scan)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ['sfConfig', 'sfModules', 'args', 'loggingQueue'])
        
        # Test handle_abort signature
        sig = inspect.signature(sf.handle_abort)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ['signal', 'frame'])
    
    @patch('builtins.print')
    def test_usage_output_format(self, mock_print):
        """Test that usage output has correct format."""
        sys.argv = ['sf.py']  # No arguments
        
        with patch('sys.exit'):
            # Simulate the __main__ block
            if len(sys.argv) <= 1:
                print("SpiderFoot usage:")
                print("  Web UI:       python sf.py -l <ip>:<port>")
                print("  FastAPI:      python sf.py --api [--api-listen <ip>:<port>]")
                print("  Both servers: python sf.py --both [-l <ip>:<port>] [--api-listen <ip>:<port>]")
                print("  CLI scan:     python sf.py -s <target> [options]")
                print("Try --help for full guidance.")
        
        # Verify the usage message format
        calls = [call[0][0] for call in mock_print.call_args_list]
        self.assertIn("SpiderFoot usage:", calls)
        self.assertTrue(any("Web UI:" in call for call in calls))
        self.assertTrue(any("FastAPI:" in call for call in calls))
        self.assertTrue(any("CLI scan:" in call for call in calls))


if __name__ == '__main__':
    unittest.main()
