#!/usr/bin/env python3
"""
Comprehensive unit test suite for sf_orchestrator.py
Tests the modular orchestrator functionality, argument parsing, and component coordination.
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
import sys
import os
import argparse
from io import StringIO

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the module under test
import sf_orchestrator


class TestSpiderFootOrchestrator(unittest.TestCase):
    """Test the SpiderFootOrchestrator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.original_argv = sys.argv.copy()
        
    def tearDown(self):
        """Clean up after tests."""
        sys.argv = self.original_argv

    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ValidationUtils')
    def test_orchestrator_initialization(self, mock_validation, mock_module_manager, mock_config_manager):
        """Test orchestrator initializes all components correctly."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        mock_config_manager.assert_called_once()
        mock_module_manager.assert_called_once()
        mock_validation.assert_called_once()
        
        self.assertIsNotNone(orchestrator.config_manager)
        self.assertIsNotNone(orchestrator.module_manager)
        self.assertIsNotNone(orchestrator.validation_utils)
        self.assertIsNone(orchestrator.scan_manager)
        self.assertIsNone(orchestrator.server_manager)

    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.ScanManager')
    @patch('sf_orchestrator.ServerManager')
    @patch('sf_orchestrator.mp.Queue')
    @patch('sf_orchestrator.logListenerSetup')
    @patch('sf_orchestrator.logWorkerSetup')
    def test_initialize_method(self, mock_log_worker, mock_log_listener, mock_queue,
                              mock_server_manager, mock_scan_manager, mock_validation,
                              mock_module_manager, mock_config_manager):
        """Test the initialize method sets up all components."""
        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config_instance.get_default_config.return_value = {'_debug': False}
        mock_config_instance.initialize_configuration.return_value = None
        mock_config_manager.return_value = mock_config_instance
        
        mock_module_instance = MagicMock()
        mock_module_instance.load_modules.return_value = {'module1': {}}
        mock_module_instance.load_correlation_rules.return_value = []
        mock_module_manager.return_value = mock_module_instance
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.initialize()
        
        # Verify initialization calls
        mock_config_instance.get_default_config.assert_called_once()
        mock_config_instance.initialize_configuration.assert_called_once()
        mock_module_instance.load_modules.assert_called_once()
        mock_module_instance.load_correlation_rules.assert_called_once()
        mock_queue.assert_called_once()
        mock_log_listener.assert_called_once()
        mock_log_worker.assert_called_once()

    def test_create_argument_parser(self):
        """Test argument parser creation with all expected arguments."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        parser = orchestrator.create_argument_parser()
        
        self.assertIsInstance(parser, argparse.ArgumentParser)
        
        # Test that all expected arguments are present
        expected_args = [
            '-d', '--debug', '-V', '--version', '--max-threads', '-q',
            '-l', '--listen', '--api', '--api-listen', '--api-workers', '--both',
            '-s', '-m', '-t', '-u', '-x',
            '-o', '-H', '-n', '-r', '-S', '-D', '-f', '-F',
            '-M', '--modules', '-T', '--types', '-C', '--correlate'
        ]
        
        # Parse help to get available options
        with patch('sys.stderr', new_callable=StringIO):
            try:
                parser.parse_args(['--help'])
            except SystemExit:
                pass  # --help causes SystemExit
        
        # Check parser._option_string_actions for available options
        available_options = set(parser._option_string_actions.keys())
        for arg in expected_args:
            self.assertIn(arg, available_options, f"Missing argument: {arg}")

    @patch('sys.exit')
    def test_handle_version(self, mock_exit):
        """Test version handling."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with patch('builtins.print') as mock_print:
            orchestrator.handle_version()
        
        mock_print.assert_called_once()
        mock_exit.assert_called_once_with(0)
        self.assertIn('SpiderFoot', mock_print.call_args[0][0])

    @patch('sf_orchestrator.SpiderFootDb')
    @patch('sys.exit')
    def test_handle_modules_list(self, mock_exit, mock_db):
        """Test module listing functionality."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        # Mock module manager
        orchestrator.module_manager = MagicMock()
        orchestrator.module_manager.list_modules.return_value = ['module1', 'module2', 'module3']
        
        # Mock modules data
        orchestrator.modules = {
            'module1': {'descr': 'Test module 1'},
            'module2': {'descr': 'Test module 2'},
            'module3': {'descr': 'Test module 3'}
        }
        
        with patch('builtins.print') as mock_print:
            orchestrator.handle_modules_list()
        
        # Should print total count and each module
        self.assertEqual(mock_print.call_count, 4)  # 1 total + 3 modules
        mock_exit.assert_called_once_with(0)

    @patch('sf_orchestrator.SpiderFootDb')
    @patch('sys.exit')
    def test_handle_types_list(self, mock_exit, mock_db):
        """Test event types listing functionality."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config = {'_debug': False}
        
        # Mock database
        mock_db_instance = MagicMock()
        mock_db_instance.eventTypes.return_value = [
            (1, 'DOMAIN_NAME'),
            (2, 'IP_ADDRESS'),
            (3, 'EMAIL_ADDRESS')
        ]
        mock_db.return_value = mock_db_instance
        
        with patch('builtins.print') as mock_print:
            orchestrator.handle_types_list()
        
        # Should print total count and each type
        self.assertEqual(mock_print.call_count, 4)  # 1 total + 3 types
        mock_exit.assert_called_once_with(0)

    @patch('sf_orchestrator.SpiderFootDb')
    @patch('sys.exit')
    def test_handle_correlations(self, mock_exit, mock_db):
        """Test correlation handling functionality."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config = {'__correlationrules__': ['rule1', 'rule2']}
        
        # Mock database and correlation components
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        scan_id = 'test_scan_123'
        
        with patch('sf_orchestrator.RuleExecutor') as mock_executor, \
             patch('sf_orchestrator.EventEnricher') as mock_enricher, \
             patch('sf_orchestrator.ResultAggregator') as mock_aggregator, \
             patch('builtins.print') as mock_print:
            
            # Setup mocks
            mock_executor_instance = MagicMock()
            mock_executor_instance.run.return_value = {'rule1': {'events': []}}
            mock_executor.return_value = mock_executor_instance
            
            mock_enricher_instance = MagicMock()
            mock_enricher_instance.enrich_sources.return_value = []
            mock_enricher_instance.enrich_entities.return_value = []
            mock_enricher.return_value = mock_enricher_instance
            
            mock_aggregator_instance = MagicMock()
            mock_aggregator_instance.aggregate.return_value = 5
            mock_aggregator.return_value = mock_aggregator_instance
            
            orchestrator.handle_correlations(scan_id)
        
        mock_executor.assert_called_once()
        mock_executor_instance.run.assert_called_once()
        mock_print.assert_called_once()
        mock_exit.assert_called_once_with(0)

    def test_build_output_config(self):
        """Test output configuration building from arguments."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        # Create mock args with various output options
        mock_args = MagicMock()
        mock_args.o = 'json'
        mock_args.H = True
        mock_args.n = True
        mock_args.r = True
        mock_args.S = 100
        mock_args.D = ';'
        mock_args.f = True
        mock_args.F = 'DOMAIN_NAME,IP_ADDRESS'
        mock_args.t = 'DOMAIN_NAME'
        
        output_config = orchestrator._build_output_config(mock_args)
        
        expected_keys = ['format', 'no_headers', 'strip_newlines', 'show_source', 
                        'max_length', 'delimiter', 'filter_requested', 'show_only', 'requested']
        
        for key in expected_keys:
            self.assertIn(key, output_config)

    @patch('sf_orchestrator.ScanManager')
    def test_handle_scan(self, mock_scan_manager):
        """Test scan handling functionality."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config = {'_debug': False}
        orchestrator.modules = {'module1': {}}
        orchestrator.logging_queue = MagicMock()
        
        # Mock scan manager
        mock_scan_instance = MagicMock()
        mock_scan_instance.execute_scan_from_args.return_value = 'scan_123'
        mock_scan_manager.return_value = mock_scan_instance
        
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        
        with patch('sys.exit') as mock_exit:
            orchestrator.handle_scan(mock_args)
        
        mock_scan_manager.assert_called_once_with(orchestrator.config)
        mock_scan_instance.execute_scan_from_args.assert_called_once()
        mock_exit.assert_called_once_with(0)

    @patch('sf_orchestrator.ServerManager')
    def test_handle_server_startup_web_only(self, mock_server_manager):
        """Test server startup for web UI only."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config = {'_debug': False}
        orchestrator.config_manager = MagicMock()
        orchestrator.config_manager.get_web_config.return_value = {'host': '127.0.0.1', 'port': 5001}
        orchestrator.config_manager.get_api_config.return_value = {'host': '127.0.0.1', 'port': 8001}
        orchestrator.logging_queue = MagicMock()
        
        mock_server_instance = MagicMock()
        mock_server_manager.return_value = mock_server_instance
        
        mock_args = MagicMock()
        mock_args.listen = None
        mock_args.api_listen = None
        mock_args.api_workers = None
        mock_args.api = False
        mock_args.both = False
        
        orchestrator.handle_server_startup(mock_args)
        
        mock_server_manager.assert_called_once_with(orchestrator.config)
        mock_server_instance.start_web_server.assert_called_once()

    @patch('sf_orchestrator.ServerManager')
    def test_handle_server_startup_api_only(self, mock_server_manager):
        """Test server startup for API only."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config = {'_debug': False}
        orchestrator.config_manager = MagicMock()
        orchestrator.config_manager.get_web_config.return_value = {'host': '127.0.0.1', 'port': 5001}
        orchestrator.config_manager.get_api_config.return_value = {'host': '127.0.0.1', 'port': 8001}
        orchestrator.logging_queue = MagicMock()
        
        mock_server_instance = MagicMock()
        mock_server_manager.return_value = mock_server_instance
        
        mock_args = MagicMock()
        mock_args.listen = None
        mock_args.api_listen = None
        mock_args.api_workers = None
        mock_args.api = True
        mock_args.both = False
        
        orchestrator.handle_server_startup(mock_args)
        
        mock_server_instance.start_fastapi_server.assert_called_once()

    @patch('sf_orchestrator.ServerManager')
    def test_handle_server_startup_both(self, mock_server_manager):
        """Test server startup for both web UI and API."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config = {'_debug': False}
        orchestrator.config_manager = MagicMock()
        orchestrator.config_manager.get_web_config.return_value = {'host': '127.0.0.1', 'port': 5001}
        orchestrator.config_manager.get_api_config.return_value = {'host': '127.0.0.1', 'port': 8001}
        orchestrator.logging_queue = MagicMock()
        
        mock_server_instance = MagicMock()
        mock_server_manager.return_value = mock_server_instance
        
        mock_args = MagicMock()
        mock_args.listen = None
        mock_args.api_listen = None
        mock_args.api_workers = None
        mock_args.api = False
        mock_args.both = True
        
        orchestrator.handle_server_startup(mock_args)
        
        mock_server_instance.start_both_servers.assert_called_once()

    def test_handle_server_startup_with_overrides(self):
        """Test server startup with command line overrides."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config_manager = MagicMock()
        
        # Mock initial configs
        web_config = {'host': '127.0.0.1', 'port': 5001}
        api_config = {'host': '127.0.0.1', 'port': 8001, 'workers': 1}
        orchestrator.config_manager.get_web_config.return_value = web_config
        orchestrator.config_manager.get_api_config.return_value = api_config
        
        mock_args = MagicMock()
        mock_args.listen = '0.0.0.0:8080'
        mock_args.api_listen = '0.0.0.0:9090'
        mock_args.api_workers = 4
        mock_args.api = False
        mock_args.both = False
        
        with patch('sf_orchestrator.ServerManager'):
            orchestrator.handle_server_startup(mock_args)
        
        # Check that configs were updated
        self.assertEqual(web_config['host'], '0.0.0.0')
        self.assertEqual(web_config['port'], 8080)
        self.assertEqual(api_config['host'], '0.0.0.0')
        self.assertEqual(api_config['port'], 9090)
        self.assertEqual(api_config['workers'], 4)

    @patch('sf_orchestrator.SpiderFootOrchestrator.initialize')
    @patch('sf_orchestrator.SpiderFootOrchestrator.create_argument_parser')
    @patch('sf_orchestrator.SpiderFootOrchestrator.handle_version')
    def test_run_version_handling(self, mock_handle_version, mock_create_parser, mock_initialize):
        """Test run method with version argument."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.version = True
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.run(['--version'])
        
        mock_initialize.assert_called_once()
        mock_handle_version.assert_called_once()

    @patch('sf_orchestrator.SpiderFootOrchestrator.initialize')
    @patch('sf_orchestrator.SpiderFootOrchestrator.create_argument_parser')
    @patch('sf_orchestrator.SpiderFootOrchestrator.handle_modules_list')
    def test_run_modules_listing(self, mock_handle_modules, mock_create_parser, mock_initialize):
        """Test run method with modules listing argument."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.version = False
        mock_args.modules = True
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.run(['--modules'])
        
        mock_handle_modules.assert_called_once()

    @patch('sf_orchestrator.SpiderFootOrchestrator.initialize')
    @patch('sf_orchestrator.SpiderFootOrchestrator.create_argument_parser')
    @patch('sf_orchestrator.SpiderFootOrchestrator.handle_scan')
    def test_run_scan_mode(self, mock_handle_scan, mock_create_parser, mock_initialize):
        """Test run method with scan arguments."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.version = False
        mock_args.modules = False
        mock_args.types = False
        mock_args.correlate = None
        mock_args.s = 'example.com'
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.run(['-s', 'example.com'])
        
        mock_handle_scan.assert_called_once_with(mock_args)

    @patch('sf_orchestrator.SpiderFootOrchestrator.initialize')
    @patch('sf_orchestrator.SpiderFootOrchestrator.create_argument_parser')
    @patch('sf_orchestrator.SpiderFootOrchestrator.handle_server_startup')
    def test_run_server_mode(self, mock_handle_server, mock_create_parser, mock_initialize):
        """Test run method with server arguments."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.version = False
        mock_args.modules = False
        mock_args.types = False
        mock_args.correlate = None
        mock_args.s = None
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.run([])
        
        mock_handle_server.assert_called_once_with(mock_args)


class TestSpiderFootOrchestratorEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions in sf_orchestrator.py."""

    def setUp(self):
        """Set up test fixtures."""
        self.original_argv = sys.argv.copy()

    def tearDown(self):
        """Clean up after tests."""
        sys.argv = self.original_argv

    @patch('sf_orchestrator.logging.getLogger')
    def test_initialization_exception_handling(self, mock_logger):
        """Test orchestrator handles initialization exceptions."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        with patch('sf_orchestrator.ConfigManager', side_effect=Exception("Config failed")):
            orchestrator = sf_orchestrator.SpiderFootOrchestrator()
            
            with patch('sys.exit') as mock_exit:
                orchestrator.initialize()
            
            mock_exit.assert_called_with(-1)
            mock_log.critical.assert_called_once()

    @patch('sf_orchestrator.logging.getLogger')
    def test_scan_handling_exception(self, mock_logger):
        """Test scan handling with exceptions."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with patch('sf_orchestrator.ScanManager', side_effect=Exception("Scan failed")):
            with patch('sys.exit') as mock_exit:
                orchestrator.handle_scan(MagicMock())
            
            mock_exit.assert_called_with(-1)
            mock_log.error.assert_called_once()

    @patch('sf_orchestrator.logging.getLogger')
    def test_correlation_handling_exception(self, mock_logger):
        """Test correlation handling with exceptions."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with patch('sf_orchestrator.SpiderFootDb', side_effect=Exception("DB failed")):
            with patch('sys.exit') as mock_exit:
                orchestrator.handle_correlations('test_scan')
            
            mock_exit.assert_called_with(-1)
            mock_log.error.assert_called_once()

    @patch('sf_orchestrator.SpiderFootOrchestrator.initialize')
    @patch('sf_orchestrator.logging.getLogger')
    def test_run_keyboard_interrupt(self, mock_logger, mock_initialize):
        """Test run method handles KeyboardInterrupt."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        mock_initialize.side_effect = KeyboardInterrupt()
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with patch('sys.exit') as mock_exit:
            orchestrator.run()
        
        mock_exit.assert_called_with(0)
        mock_log.info.assert_called_with("Interrupted by user.")

    @patch('sf_orchestrator.SpiderFootOrchestrator.initialize')
    @patch('sf_orchestrator.logging.getLogger')
    def test_run_general_exception(self, mock_logger, mock_initialize):
        """Test run method handles general exceptions."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        mock_initialize.side_effect = Exception("General error")
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with patch('sys.exit') as mock_exit:
            orchestrator.run()
        
        mock_exit.assert_called_with(-1)
        mock_log.critical.assert_called_once()

    @patch('sf_orchestrator.SpiderFootDb')
    def test_handle_types_list_no_types(self, mock_db):
        """Test handle_types_list when no event types exist."""
        mock_db_instance = MagicMock()
        mock_db_instance.eventTypes.return_value = []
        mock_db.return_value = mock_db_instance
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config = {'_debug': False}
        
        with patch('builtins.print') as mock_print, \
             patch('sys.exit') as mock_exit:
            orchestrator.handle_types_list()
        
        mock_print.assert_called_with("Total event types: 0")
        mock_exit.assert_called_with(0)

    def test_build_output_config_minimal_args(self):
        """Test _build_output_config with minimal arguments."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        mock_args = MagicMock()
        # Set all optional args to None/False
        mock_args.o = None
        mock_args.H = False
        mock_args.n = False
        mock_args.r = False
        mock_args.S = None
        mock_args.D = None
        mock_args.f = False
        mock_args.F = None
        mock_args.t = None
        
        output_config = orchestrator._build_output_config(mock_args)
        
        # Should return empty config for minimal args
        expected_empty_keys = ['format', 'no_headers', 'strip_newlines', 'show_source',
                              'max_length', 'delimiter', 'filter_requested', 'show_only', 'requested']
        
        for key in expected_empty_keys:
            if key in output_config:
                self.assertFalse(output_config[key] if isinstance(output_config[key], bool) else not output_config[key])


class TestModuleFunctions(unittest.TestCase):
    """Test module-level functions in sf_orchestrator.py."""

    def setUp(self):
        """Set up test fixtures."""
        self.original_argv = sys.argv.copy()

    def tearDown(self):
        """Clean up after tests."""
        sys.argv = self.original_argv

    @patch('sf_orchestrator.SpiderFootOrchestrator')
    def test_main_function(self, mock_orchestrator):
        """Test the main function."""
        mock_instance = MagicMock()
        mock_orchestrator.return_value = mock_instance
        
        sf_orchestrator.main()
        
        mock_orchestrator.assert_called_once()
        mock_instance.run.assert_called_once()

    @patch('builtins.print')
    @patch('sys.exit')
    def test_main_with_usage_message(self, mock_exit, mock_print):
        """Test main function shows usage when no args provided."""
        sys.argv = ['sf_orchestrator.py']
        
        with patch('sf_orchestrator.SpiderFootOrchestrator') as mock_orchestrator:
            sf_orchestrator.main()
        
        # Should still create orchestrator and run
        mock_orchestrator.assert_called_once()


if __name__ == '__main__':
    unittest.main()
