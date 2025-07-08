#!/usr/bin/env python3
"""
Comprehensive unit test suite for sf.py (main entry point)
Tests the modular entry point functionality, backward compatibility, and edge cases.

NOTE: Many of these tests are for legacy functionality that no longer exists
in the new modular architecture. They should be updated or replaced with
tests for the new SpiderFootOrchestrator-based architecture.
"""

import unittest
from unittest.mock import MagicMock, patch, call, mock_open
import sys
import os
import tempfile
from io import StringIO
import argparse

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the module under test
import sf


@unittest.skip("Legacy tests for obsolete module structure - needs updating for new orchestrator architecture")
class TestSfMain(unittest.TestCase):
    """Test the main sf.py entry point and legacy functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.original_argv = sys.argv.copy()
        
    def tearDown(self):
        """Clean up after tests."""
        sys.argv = self.original_argv

    @patch('sf.SpiderFootOrchestrator')
    def test_main_delegates_to_orchestrator(self, mock_orchestrator):
        """Test that main() properly delegates to the orchestrator."""
        mock_instance = MagicMock()
        mock_orchestrator.return_value = mock_instance
        
        sf.main()
        
        mock_orchestrator.assert_called_once()
        mock_instance.run.assert_called_once()

    @patch('sf.SpiderFootOrchestrator')
    @patch('sf.logging.getLogger')
    def test_main_handles_exceptions(self, mock_logger, mock_orchestrator):
        """Test that main() properly handles exceptions."""
        mock_instance = MagicMock()
        mock_instance.run.side_effect = Exception("Test error")
        mock_orchestrator.return_value = mock_instance
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        with self.assertRaises(SystemExit):
            sf.main()
        
        mock_log.critical.assert_called_once()

    @patch('sf.ModuleManager')
    def test_load_modules_custom_legacy_function(self, mock_module_manager):
        """Test the legacy load_modules_custom function."""
        mock_manager = MagicMock()
        mock_manager._load_modules_custom.return_value = {'module1': {}, 'module2': {}}
        mock_module_manager.return_value = mock_manager
        
        result = sf.load_modules_custom('/test/path', MagicMock())
        
        mock_module_manager.assert_called_once()
        mock_manager._load_modules_custom.assert_called_once_with('/test/path')
        self.assertEqual(result, {'module1': {}, 'module2': {}})

    @patch('sf.ScanManager')
    @patch('sf.ValidationUtils')
    def test_start_scan_legacy_function(self, mock_validation, mock_scan_manager):
        """Test the legacy start_scan function."""
        # Setup mocks
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        mock_args.m = 'module1,module2'
        mock_args.t = 'DOMAIN_NAME'
        mock_args.u = None
        mock_args.x = False
        
        mock_validation_instance = MagicMock()
        mock_validation_instance.validate_module_list.return_value = ['module1', 'module2']
        mock_validation_instance.validate_event_types.return_value = ['DOMAIN_NAME']
        mock_validation.return_value = mock_validation_instance
        
        mock_scan_instance = MagicMock()
        mock_scan_instance.validate_scan_arguments.return_value = {
            'target': 'example.com',
            'target_type': 'DOMAIN_NAME'
        }
        mock_scan_instance.prepare_modules.return_value = ['module1', 'module2']
        mock_scan_instance.prepare_scan_config.return_value = {}
        mock_scan_instance.execute_scan.return_value = 'scan123'
        mock_scan_instance.monitor_scan.return_value = {'status': 'FINISHED'}
        mock_scan_manager.return_value = mock_scan_instance
        
        # Test successful scan
        with patch('sys.exit') as mock_exit:
            sf.start_scan({}, {}, mock_args, MagicMock())
            mock_exit.assert_called_with(0)

    @patch('sf.ScanManager')
    @patch('sf.ValidationUtils')
    @patch('sf.logging.getLogger')
    def test_start_scan_handles_exceptions(self, mock_logger, mock_validation, mock_scan_manager):
        """Test that start_scan handles exceptions properly."""
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        
        mock_scan_instance = MagicMock()
        mock_scan_instance.validate_scan_arguments.side_effect = Exception("Validation failed")
        mock_scan_manager.return_value = mock_scan_instance
        
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        with patch('sys.exit') as mock_exit:
            sf.start_scan({}, {}, mock_args, MagicMock())
            mock_exit.assert_called_with(-1)
        
        mock_log.error.assert_called_once()

    @patch('sf.ServerManager')
    def test_start_fastapi_server_legacy_function(self, mock_server_manager):
        """Test the legacy start_fastapi_server function."""
        mock_server_instance = MagicMock()
        mock_server_manager.return_value = mock_server_instance
        
        api_config = {'host': '127.0.0.1', 'port': 8001}
        sf_config = {'_debug': False}
        logging_queue = MagicMock()
        
        sf.start_fastapi_server(api_config, sf_config, logging_queue)
        
        mock_server_manager.assert_called_once_with(sf_config)
        mock_server_instance.start_fastapi_server.assert_called_once_with(api_config, logging_queue)

    @patch('sf.ServerManager')
    def test_start_both_servers_legacy_function(self, mock_server_manager):
        """Test the legacy start_both_servers function."""
        mock_server_instance = MagicMock()
        mock_server_manager.return_value = mock_server_instance
        
        web_config = {'host': '127.0.0.1', 'port': 5001}
        api_config = {'host': '127.0.0.1', 'port': 8001}
        sf_config = {'_debug': False}
        logging_queue = MagicMock()
        
        sf.start_both_servers(web_config, api_config, sf_config, logging_queue)
        
        mock_server_manager.assert_called_once_with(sf_config)
        mock_server_instance.start_both_servers.assert_called_once_with(web_config, api_config, logging_queue)

    @patch('sf.ServerManager')
    def test_start_web_server_legacy_function(self, mock_server_manager):
        """Test the legacy start_web_server function."""
        mock_server_instance = MagicMock()
        mock_server_manager.return_value = mock_server_instance
        
        web_config = {'host': '127.0.0.1', 'port': 5001}
        sf_config = {'_debug': False}
        logging_queue = MagicMock()
        
        sf.start_web_server(web_config, sf_config, logging_queue)
        
        mock_server_manager.assert_called_once_with(sf_config)
        mock_server_instance.start_web_server.assert_called_once_with(web_config, logging_queue)

    @patch('sf.ScanManager')
    @patch('sf.logging.getLogger')
    def test_handle_abort(self, mock_logger, mock_scan_manager):
        """Test the handle_abort function."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        # Setup global variables
        sf.scanId = 'test_scan_123'
        sf.dbh = MagicMock()
        
        mock_scan_instance = MagicMock()
        mock_scan_manager.return_value = mock_scan_instance
        
        with patch('sys.exit') as mock_exit:
            sf.handle_abort('signal', 'frame')
            mock_exit.assert_called_with(-1)
        
        mock_log.info.assert_called_once()
        mock_scan_instance.stop_scan.assert_called_once_with('test_scan_123')

    @patch('sf.ValidationUtils')
    @patch('sf.logging.getLogger')
    def test_validate_arguments_no_target(self, mock_logger, mock_validation):
        """Test validate_arguments with no target specified."""
        mock_args = MagicMock()
        mock_args.s = None
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        with patch('sys.exit') as mock_exit:
            sf.validate_arguments(mock_args, mock_log)
            mock_exit.assert_called_with(-1)
        
        mock_log.error.assert_called_once()

    @patch('sf.ValidationUtils')
    def test_validate_arguments_strict_mode_without_types(self, mock_validation):
        """Test validate_arguments with strict mode but no event types."""
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        mock_args.x = True
        mock_args.t = None
        mock_log = MagicMock()
        
        with patch('sys.exit') as mock_exit:
            sf.validate_arguments(mock_args, mock_log)
            mock_exit.assert_called_with(-1)
        
        mock_log.error.assert_called_once()

    @patch('sf.ValidationUtils')
    def test_validate_arguments_strict_mode_with_modules(self, mock_validation):
        """Test validate_arguments with strict mode and modules specified."""
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        mock_args.x = True
        mock_args.t = 'DOMAIN_NAME'
        mock_args.m = 'module1'
        mock_log = MagicMock()
        
        with patch('sys.exit') as mock_exit:
            sf.validate_arguments(mock_args, mock_log)
            mock_exit.assert_called_with(-1)
        
        mock_log.error.assert_called_once()

    @patch('sf.SpiderFootHelpers.targetTypeFromString')
    def test_process_target_valid_domain(self, mock_target_type):
        """Test process_target with a valid domain."""
        mock_target_type.return_value = 'INTERNET_NAME'
        
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        
        target, target_type = sf.process_target(mock_args, MagicMock())
        
        self.assertEqual(target, 'example.com')
        self.assertEqual(target_type, 'INTERNET_NAME')

    @patch('sf.SpiderFootHelpers.targetTypeFromString')
    def test_process_target_with_spaces(self, mock_target_type):
        """Test process_target with target containing spaces."""
        mock_target_type.return_value = 'HUMAN_NAME'
        
        mock_args = MagicMock()
        mock_args.s = 'John Doe'
        
        target, target_type = sf.process_target(mock_args, MagicMock())
        
        self.assertEqual(target, 'John Doe')
        self.assertEqual(target_type, 'HUMAN_NAME')
        mock_target_type.assert_called_with('"John Doe"')

    @patch('sf.SpiderFootHelpers.targetTypeFromString')
    def test_process_target_invalid_target(self, mock_target_type):
        """Test process_target with invalid target."""
        mock_target_type.return_value = None
        
        mock_args = MagicMock()
        mock_args.s = 'invalid_target'
        mock_log = MagicMock()
        
        with patch('sys.exit') as mock_exit:
            sf.process_target(mock_args, mock_log)
            mock_exit.assert_called_with(-1)
        
        mock_log.error.assert_called_once()    @patch('sf.SpiderFootOrchestrator')
    def test_main_with_no_arguments(self, mock_orchestrator):
        """Test main entry point with no arguments."""
        mock_instance = MagicMock()
        mock_orchestrator.return_value = mock_instance
        
        sys.argv = ['sf.py']
        
        with patch('sys.exit'):
            # Import and execute __main__ section
            exec(compile(open('sf.py').read(), 'sf.py', 'exec'))
        
        # Should not exit since orchestrator handles argument processing
        mock_orchestrator.assert_called_once()
        mock_instance.run.assert_called_once()

    def test_config_constants(self):
        """Test that configuration constants are properly defined."""
        self.assertIsInstance(sf.sfConfig, dict)
        self.assertIsInstance(sf.sfOptdescs, dict)
        
        # Check required config keys
        required_keys = ['_debug', '_maxthreads', '_useragent']
        for key in required_keys:
            self.assertIn(key, sf.sfConfig)
            self.assertIn(key, sf.sfOptdescs)
            
        # Check __logging exists in config but description might be missing
        self.assertIn('__logging', sf.sfConfig)

    def test_global_variables_initialization(self):
        """Test that global variables are properly initialized."""
        self.assertIsNone(sf.scanId)
        self.assertIsNone(sf.dbh)


class TestSfMainEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions in sf.py."""

    def setUp(self):
        """Set up test fixtures."""
        self.original_argv = sys.argv.copy()

    def tearDown(self):
        """Clean up after tests."""
        sys.argv = self.original_argv

    @patch('sf.ScanManager')
    @patch('sf.logging.getLogger')
    def test_handle_abort_no_scan_id(self, mock_logger, mock_scan_manager):
        """Test handle_abort when no scan is running."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        # Clear global variables
        sf.scanId = None
        sf.dbh = None
        
        with patch('sys.exit') as mock_exit:
            sf.handle_abort('signal', 'frame')
            mock_exit.assert_called_with(-1)
        
        # Should not attempt to stop scan
        mock_scan_manager.assert_not_called()

    @patch('sf.ScanManager')
    @patch('sf.logging.getLogger')
    def test_handle_abort_exception_handling(self, mock_logger, mock_scan_manager):
        """Test handle_abort when stop_scan raises an exception."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        sf.scanId = 'test_scan'
        sf.dbh = MagicMock()
        
        mock_scan_instance = MagicMock()
        mock_scan_instance.stop_scan.side_effect = Exception("Stop failed")
        mock_scan_manager.return_value = mock_scan_instance
        
        with patch('sys.exit') as mock_exit:
            sf.handle_abort('signal', 'frame')
            mock_exit.assert_called_with(-1)
        
        mock_log.error.assert_called_once()

    @patch('sf.ValidationUtils')
    def test_validate_arguments_edge_cases(self, mock_validation):
        """Test validate_arguments with various argument combinations."""
        mock_log = MagicMock()
        
        # Test case: has target, no strict mode issues
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        mock_args.x = False
        mock_args.t = 'DOMAIN_NAME'
        mock_args.m = None
        
        # Should not call sys.exit
        sf.validate_arguments(mock_args, mock_log)
        mock_log.error.assert_not_called()

    def test_legacy_configuration_structure(self):
        """Test that legacy configuration structure is maintained."""
        # Verify sfConfig has all expected keys with correct types
        expected_config = {
            '_debug': bool,
            '_maxthreads': int,
            '__logging': bool,
            '__outputfilter': type(None),
            '_useragent': str,
            '_dnsserver': str,
            '_fetchtimeout': int,
            '_internettlds': str,
            '_internettlds_cache': int,
            '_genericusers': str,
            '__database': str,
            '__modules__': type(None),
            '__correlationrules__': type(None),
            '_socks1type': str,
            '_socks2addr': str,
            '_socks3port': str,
            '_socks4user': str,
            '_socks5pwd': str,
        }
        
        for key, expected_type in expected_config.items():
            self.assertIn(key, sf.sfConfig)
            self.assertIsInstance(sf.sfConfig[key], expected_type)

    def test_option_descriptions_completeness(self):
        """Test that all configuration options have descriptions."""
        # Every key in sfConfig should have a description
        for key in sf.sfConfig.keys():
            if not key.startswith('__'):  # Skip internal keys
                self.assertIn(key, sf.sfOptdescs, f"Missing description for {key}")
                self.assertIsInstance(sf.sfOptdescs[key], str)
                self.assertTrue(len(sf.sfOptdescs[key]) > 0)


if __name__ == '__main__':
    unittest.main()
