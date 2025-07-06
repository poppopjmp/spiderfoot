#!/usr/bin/env python3
"""
Enhanced unit tests for sf_orchestrator.py - modular orchestrator

This comprehensive test suite covers all functionality in sf_orchestrator.py including:
- Orchestrator initialization and component management
- Argument parsing and command handling
- Server startup and management
- Scan execution and monitoring
- Correlation rule processing
- Error handling and edge cases
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os
import argparse

# Add the SpiderFoot directory to the path for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import sf_orchestrator


class TestSpiderFootOrchestratorEnhanced(unittest.TestCase):
    """Enhanced test cases for SpiderFootOrchestrator."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.original_argv = sys.argv.copy()
        
    def tearDown(self):
        """Clean up after each test method."""
        sys.argv = self.original_argv
    
    # =============================================================================
    # INITIALIZATION TESTS
    # =============================================================================
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_orchestrator_initialization(self, mock_logger, mock_validation, 
                                       mock_config, mock_modules):
        """Test orchestrator initializes all components correctly."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        # Verify components are initialized
        mock_config.assert_called_once()
        mock_modules.assert_called_once()
        mock_validation.assert_called_once()
        
        # Verify attributes are set
        self.assertIsNotNone(orchestrator.config_manager)
        self.assertIsNotNone(orchestrator.module_manager)
        self.assertIsNotNone(orchestrator.validation_utils)
        self.assertIsNone(orchestrator.scan_manager)  # Initialized later
        self.assertIsNone(orchestrator.server_manager)  # Initialized later
    
    @patch('sf_orchestrator.ScanManager')
    @patch('sf_orchestrator.ServerManager')
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_orchestrator_initialize_method(self, mock_logger, mock_validation,
                                          mock_config, mock_modules, 
                                          mock_server, mock_scan):
        """Test orchestrator initialize method sets up all components."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        # Mock config manager
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.initialize.return_value = {'_debug': False}
        
        # Mock module manager  
        mock_modules_instance = MagicMock()
        mock_modules.return_value = mock_modules_instance
        mock_modules_instance.load_modules.return_value = {'module1': {}}
        mock_modules_instance.load_correlation_rules.return_value = []
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.initialize()
        
        # Verify initialization steps
        mock_config_instance.initialize.assert_called_once()
        mock_config_instance.validate_legacy_files.assert_called_once()
        mock_modules_instance.load_modules.assert_called_once()
        mock_modules_instance.load_correlation_rules.assert_called_once()
        
        # Verify managers are created
        mock_scan.assert_called_once()
        mock_server.assert_called_once()
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_orchestrator_initialize_handles_exceptions(self, mock_logger, mock_validation,
                                                       mock_config, mock_modules):
        """Test orchestrator initialize handles exceptions gracefully."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.initialize.side_effect = Exception("Config load failed")
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with self.assertRaises(Exception):
            orchestrator.initialize()
        
        mock_log.critical.assert_called()
    
    # =============================================================================
    # ARGUMENT PARSER TESTS
    # =============================================================================
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_create_argument_parser(self, mock_logger, mock_validation,
                                   mock_config, mock_modules):
        """Test argument parser creation with all options."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        parser = orchestrator.create_argument_parser()
        
        self.assertIsInstance(parser, argparse.ArgumentParser)
        
        # Test that parser can handle various argument combinations
        test_args = [
            ['--debug'],
            ['--version'],
            ['-l', '127.0.0.1:8080'],
            ['--api'],
            ['--both'],
            ['-s', 'example.com'],
            ['-m', 'module1,module2'],
            ['-t', 'DOMAIN_NAME,IP_ADDRESS'],
            ['-u', 'passive'],
            ['-x'],
            ['-o', 'json'],
            ['--modules'],
            ['--types'],
            ['-C', 'scan123']
        ]
        
        for args in test_args:
            try:
                parsed = parser.parse_args(args)
                self.assertIsNotNone(parsed)
            except SystemExit:
                # Some args like --help will cause SystemExit, which is expected
                pass
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_argument_parser_scan_options(self, mock_logger, mock_validation,
                                         mock_config, mock_modules):
        """Test argument parser handles scan options correctly."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        parser = orchestrator.create_argument_parser()
        
        args = parser.parse_args(['-s', 'example.com', '-m', 'module1,module2', 
                                 '-t', 'DOMAIN_NAME', '-o', 'json'])
        
        self.assertEqual(args.s, 'example.com')
        self.assertEqual(args.m, 'module1,module2')
        self.assertEqual(args.t, 'DOMAIN_NAME')
        self.assertEqual(args.o, 'json')
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_argument_parser_server_options(self, mock_logger, mock_validation,
                                           mock_config, mock_modules):
        """Test argument parser handles server options correctly."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        parser = orchestrator.create_argument_parser()
        
        args = parser.parse_args(['--both', '-l', '0.0.0.0:8080', 
                                 '--api-listen', '0.0.0.0:8001', '--api-workers', '4'])
        
        self.assertTrue(args.both)
        self.assertEqual(args.listen, '0.0.0.0:8080')
        self.assertEqual(args.api_listen, '0.0.0.0:8001')
        self.assertEqual(args.api_workers, 4)
    
    # =============================================================================
    # VERSION AND INFO HANDLING TESTS
    # =============================================================================
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    @patch('builtins.print')
    def test_handle_version(self, mock_print, mock_logger, mock_validation,
                           mock_config, mock_modules):
        """Test version handling."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with self.assertRaises(SystemExit) as cm:
            orchestrator.handle_version()
        
        self.assertEqual(cm.exception.code, 0)
        mock_print.assert_called_once()
        self.assertIn("SpiderFoot", str(mock_print.call_args))
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    @patch('builtins.print')
    def test_handle_modules_list(self, mock_print, mock_logger, mock_validation,
                                mock_config, mock_modules):
        """Test modules listing."""
        mock_modules_instance = MagicMock()
        mock_modules.return_value = mock_modules_instance
        mock_modules_instance.list_modules.return_value = ['module1', 'module2', 'module3']
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with self.assertRaises(SystemExit) as cm:
            orchestrator.handle_modules_list()
        
        self.assertEqual(cm.exception.code, 0)
        mock_modules_instance.list_modules.assert_called_once()
        # Should print total count and module list
        self.assertTrue(mock_print.call_count >= 2)
    
    @patch('sf_orchestrator.SpiderFootDb')
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    @patch('builtins.print')
    def test_handle_types_list(self, mock_print, mock_logger, mock_validation,
                              mock_config, mock_modules, mock_db):
        """Test event types listing."""
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        mock_db_instance.eventTypes.return_value = ['DOMAIN_NAME', 'IP_ADDRESS', 'EMAIL_ADDRESS']
        
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.config = {'__database': 'test.db'}
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config = {'__database': 'test.db'}
        
        with self.assertRaises(SystemExit) as cm:
            orchestrator.handle_types_list()
        
        self.assertEqual(cm.exception.code, 0)
        mock_db_instance.eventTypes.assert_called_once()
        self.assertTrue(mock_print.call_count >= 1)
    
    # =============================================================================
    # CORRELATION HANDLING TESTS
    # =============================================================================
    
    @patch('sf_orchestrator.ScanManager')
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_handle_correlations(self, mock_logger, mock_validation, mock_config,
                                mock_modules, mock_scan_manager):
        """Test correlation handling."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.validation_utils = MagicMock()
        orchestrator.validation_utils.validate_scan_id.return_value = 'scan123'
        orchestrator.config = {'test': True}
        orchestrator.correlation_rules = [{'rule1': 'test'}]
        
        # Mock the correlation imports
        with patch('spiderfoot.correlation.rule_executor.RuleExecutor') as mock_executor_class, \
             patch('spiderfoot.correlation.event_enricher.EventEnricher') as mock_enricher_class, \
             patch('spiderfoot.correlation.result_aggregator.ResultAggregator') as mock_aggregator_class, \
             patch('sf_orchestrator.SpiderFootDb') as mock_db_class, \
             patch('builtins.print') as mock_print:
            
            # Set up mocks
            mock_executor = MagicMock()
            mock_executor_class.return_value = mock_executor
            mock_executor.run.return_value = {'rule1': {'events': []}}
            
            mock_enricher = MagicMock()
            mock_enricher_class.return_value = mock_enricher
            mock_enricher.enrich_sources.return_value = []
            mock_enricher.enrich_entities.return_value = []
            
            mock_aggregator = MagicMock()
            mock_aggregator_class.return_value = mock_aggregator
            mock_aggregator.aggregate.return_value = 5
            
            mock_db = MagicMock()
            mock_db_class.return_value = mock_db
            
            with self.assertRaises(SystemExit) as cm:
                orchestrator.handle_correlations('scan123')
        
        self.assertEqual(cm.exception.code, 0)
        mock_print.assert_called_with("Correlated 5 results for scan scan123")
    
    @patch('sf_orchestrator.ScanManager')
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_handle_correlations_error(self, mock_logger, mock_validation, mock_config,
                                      mock_modules, mock_scan_manager):
        """Test correlation handling with errors."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        mock_scan_manager_instance = MagicMock()
        mock_scan_manager.return_value = mock_scan_manager_instance
        mock_scan_manager_instance.run_correlations.side_effect = Exception("Correlation failed")
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.scan_manager = mock_scan_manager_instance
        
        with self.assertRaises(SystemExit) as cm:
            orchestrator.handle_correlations('scan123')
        
        self.assertEqual(cm.exception.code, -1)
        mock_log.error.assert_called()
    
    # =============================================================================
    # SCAN HANDLING TESTS
    # =============================================================================
    
    @patch('sf_orchestrator.ScanManager')
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_handle_scan(self, mock_logger, mock_validation, mock_config,
                        mock_modules, mock_scan_manager):
        """Test scan handling."""
        mock_scan_manager_instance = MagicMock()
        mock_scan_manager.return_value = mock_scan_manager_instance
        mock_scan_manager_instance.execute_scan_cli.return_value = {
            'success': True,
            'scan_id': 'scan123',
            'results': []
        }
        
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        mock_args.m = 'module1,module2'
        mock_args.t = 'DOMAIN_NAME'
        mock_args.o = 'json'
        mock_args.u = None
        mock_args.x = False
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.scan_manager = mock_scan_manager_instance
        # Need to set up additional required attributes
        orchestrator.modules = {'module1': {}, 'module2': {}}
        orchestrator.config_manager = MagicMock()
        orchestrator.validation_utils = MagicMock()
        orchestrator.validation_utils.validate_module_list.return_value = ['module1', 'module2']
        orchestrator.validation_utils.validate_event_types.return_value = ['DOMAIN_NAME']
        orchestrator.config = {}
        
        # Mock the scan manager methods
        mock_scan_manager_instance.validate_scan_arguments.return_value = {
            'target': 'example.com',
            'target_type': 'DOMAIN_NAME'
        }
        mock_scan_manager_instance.prepare_modules.return_value = ['module1', 'module2']
        mock_scan_manager_instance.prepare_scan_config.return_value = {}
        mock_scan_manager_instance.setup_signal_handler.return_value = None
        mock_scan_manager_instance.execute_scan.return_value = 'scan123'
        mock_scan_manager_instance.monitor_scan.return_value = {'status': 'FINISHED'}
        
        with patch.object(orchestrator, '_build_output_config') as mock_build_config:
            mock_build_config.return_value = {'_format': 'json'}
            
            with self.assertRaises(SystemExit) as cm:
                orchestrator.handle_scan(mock_args)
        
        self.assertEqual(cm.exception.code, 0)
        mock_scan_manager_instance.execute_scan.assert_called_once()
    
    @patch('sf_orchestrator.ScanManager')
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_handle_scan_error(self, mock_logger, mock_validation, mock_config,
                              mock_modules, mock_scan_manager):
        """Test scan handling with errors."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        mock_scan_manager_instance = MagicMock()
        mock_scan_manager.return_value = mock_scan_manager_instance
        
        # Mock the scan manager methods to raise exception during execution
        mock_scan_manager_instance.prepare_scan_params.return_value = {
            'target': 'example.com',
            'target_type': 'IP'
        }
        mock_scan_manager_instance.get_enabled_modules.return_value = ['sfp_dnsresolve']
        mock_scan_manager_instance.execute_scan.side_effect = Exception("Scan failed")
        
        mock_args = MagicMock()
        mock_args.s = 'example.com'
        mock_args.t = None
        mock_args.m = None
        mock_args.F = None
        mock_args.correlate = False
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.scan_manager = mock_scan_manager_instance
        orchestrator.module_manager = MagicMock()
        orchestrator.config_manager = MagicMock()
        orchestrator.logging_queue = MagicMock()
        
        with self.assertRaises(SystemExit) as cm:
            orchestrator.handle_scan(mock_args)
        
        self.assertEqual(cm.exception.code, -1)
        mock_log.error.assert_called()
    
    def test_build_output_config(self):
        """Test output configuration building."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        # Mock validation_utils
        orchestrator.validation_utils = MagicMock()
        orchestrator.validation_utils.validate_output_format.return_value = 'json'
        orchestrator.validation_utils.validate_event_types.side_effect = lambda x: x.split(',')
        
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
        
        config = orchestrator._build_output_config(mock_args)
        
        # Fix: Use actual config keys from implementation
        self.assertEqual(config['_format'], 'json')
        self.assertFalse(config['_showheaders'])
        self.assertTrue(config['_stripnewline'])
        self.assertTrue(config['_showsource'])
        self.assertEqual(config['_maxlength'], 100)
        self.assertEqual(config['_csvdelim'], ';')
        self.assertTrue(config['_showonlyrequested'])
        # Note: args.t overwrites args.F, so only DOMAIN_NAME is in _requested
        self.assertEqual(config['_requested'], ['DOMAIN_NAME'])
    
    # =============================================================================
    # SERVER HANDLING TESTS
    # =============================================================================
    
    @patch('sf_orchestrator.ServerManager')
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_handle_server_startup_web_only(self, mock_logger, mock_validation,
                                           mock_config, mock_modules, mock_server_manager):
        """Test server startup for web UI only."""
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.get_web_config.return_value = {'host': '127.0.0.1', 'port': 8080}
        mock_config_instance.get_api_config.return_value = {'host': '127.0.0.1', 'port': 8001}
        
        mock_server_manager_instance = MagicMock()
        mock_server_manager.return_value = mock_server_manager_instance
        
        mock_args = MagicMock()
        mock_args.api = False
        mock_args.both = False
        mock_args.listen = None
        mock_args.api_listen = None
        mock_args.api_workers = None
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config_manager = mock_config_instance
        orchestrator.server_manager = mock_server_manager_instance
        
        orchestrator.handle_server_startup(mock_args)
        
        mock_server_manager_instance.start_web_server.assert_called_once()
    
    @patch('sf_orchestrator.ServerManager')
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_handle_server_startup_api_only(self, mock_logger, mock_validation,
                                           mock_config, mock_modules, mock_server_manager):
        """Test server startup for API only."""
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.get_web_config.return_value = {'host': '127.0.0.1', 'port': 8080}
        mock_config_instance.get_api_config.return_value = {'host': '127.0.0.1', 'port': 8001}
        
        mock_server_manager_instance = MagicMock()
        mock_server_manager.return_value = mock_server_manager_instance
        
        mock_args = MagicMock()
        mock_args.api = True
        mock_args.both = False
        mock_args.listen = None
        mock_args.api_listen = None
        mock_args.api_workers = None
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config_manager = mock_config_instance
        orchestrator.server_manager = mock_server_manager_instance
        
        orchestrator.handle_server_startup(mock_args)
        
        mock_server_manager_instance.start_fastapi_server.assert_called_once()
    
    @patch('sf_orchestrator.ServerManager')
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_handle_server_startup_both(self, mock_logger, mock_validation,
                                       mock_config, mock_modules, mock_server_manager):
        """Test server startup for both web UI and API."""
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.get_web_config.return_value = {'host': '127.0.0.1', 'port': 8080}
        mock_config_instance.get_api_config.return_value = {'host': '127.0.0.1', 'port': 8001}
        
        mock_validation_instance = MagicMock()
        mock_validation.return_value = mock_validation_instance
        mock_validation_instance.parse_host_port.return_value = ('0.0.0.0', 9080)
        
        mock_server_manager_instance = MagicMock()
        mock_server_manager.return_value = mock_server_manager_instance
        
        mock_args = MagicMock()
        mock_args.api = False
        mock_args.both = True
        mock_args.listen = '0.0.0.0:9080'
        mock_args.api_listen = '0.0.0.0:9001'
        mock_args.api_workers = 4
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        orchestrator.config_manager = mock_config_instance
        orchestrator.validation_utils = mock_validation_instance
        orchestrator.server_manager = mock_server_manager_instance
        
        orchestrator.handle_server_startup(mock_args)
        
        mock_server_manager_instance.start_both_servers.assert_called_once()
    
    # =============================================================================
    # MAIN RUN METHOD TESTS
    # =============================================================================
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_run_with_version_argument(self, mock_logger, mock_validation,
                                      mock_config, mock_modules):
        """Test run method with version argument."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with patch.object(orchestrator, 'create_argument_parser') as mock_parser_creator, \
             patch.object(orchestrator, 'handle_version') as mock_handle_version:
            
            mock_parser = MagicMock()
            mock_parser_creator.return_value = mock_parser
            mock_args = MagicMock()
            mock_args.version = True
            mock_args.s = None
            mock_args.modules = False
            mock_args.types = False
            mock_args.correlate = False
            mock_args.listen = None
            mock_args.api = False
            mock_args.both = False
            mock_parser.parse_args.return_value = mock_args
            
            # Mock handle_version to raise SystemExit like the real method
            mock_handle_version.side_effect = SystemExit(0)
            
            with self.assertRaises(SystemExit) as cm:
                orchestrator.run(['--version'])
            
            self.assertEqual(cm.exception.code, 0)
            mock_handle_version.assert_called_once()
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_run_with_scan_argument(self, mock_logger, mock_validation,
                                   mock_config, mock_modules):
        """Test run method with scan argument."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        # Initialize config to avoid None assignment error
        orchestrator.config = {}
        
        with patch.object(orchestrator, 'create_argument_parser') as mock_parser_creator, \
             patch.object(orchestrator, 'initialize') as mock_initialize, \
             patch.object(orchestrator, 'handle_scan') as mock_handle_scan:
            
            mock_parser = MagicMock()
            mock_parser_creator.return_value = mock_parser
            mock_args = MagicMock()
            mock_args.version = False
            mock_args.modules = False
            mock_args.types = False
            mock_args.s = 'example.com'
            mock_args.correlate = None
            mock_args.listen = None
            mock_args.api = False
            mock_args.both = False
            mock_args.debug = False
            mock_args.q = False
            mock_parser.parse_args.return_value = mock_args
            
            orchestrator.run(['-s', 'example.com'])
            
            mock_initialize.assert_called_once()
            mock_handle_scan.assert_called_once_with(mock_args)
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_run_keyboard_interrupt(self, mock_logger, mock_validation,
                                   mock_config, mock_modules):
        """Test run method handles KeyboardInterrupt."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with patch.object(orchestrator, 'create_argument_parser') as mock_parser_creator:
            mock_parser = MagicMock()
            mock_parser_creator.return_value = mock_parser
            mock_parser.parse_args.side_effect = KeyboardInterrupt()
            
            with self.assertRaises(SystemExit) as cm:
                orchestrator.run(['-s', 'example.com'])
            
            self.assertEqual(cm.exception.code, 0)
            mock_log.info.assert_called_with("Interrupted by user")
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_run_general_exception(self, mock_logger, mock_validation,
                                  mock_config, mock_modules):
        """Test run method handles general exceptions."""
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with patch.object(orchestrator, 'create_argument_parser') as mock_parser_creator:
            mock_parser = MagicMock()
            mock_parser_creator.return_value = mock_parser
            mock_parser.parse_args.side_effect = Exception("Unexpected error")
            
            with self.assertRaises(SystemExit) as cm:
                orchestrator.run(['-s', 'example.com'])
            
            self.assertEqual(cm.exception.code, -1)
            mock_log.critical.assert_called()


class TestSpiderFootOrchestratorEdgeCases(unittest.TestCase):
    """Edge case and integration tests for SpiderFootOrchestrator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.original_argv = sys.argv.copy()
        
    def tearDown(self):
        """Clean up after tests."""
        sys.argv = self.original_argv
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_orchestrator_main_function(self, mock_logger, mock_validation,
                                       mock_config, mock_modules):
        """Test the main function creates and runs orchestrator."""
        with patch.object(sf_orchestrator.SpiderFootOrchestrator, 'run') as mock_run:
            with patch('builtins.print') as mock_print:
                sys.argv = ['sf_orchestrator.py']
                
                with self.assertRaises(SystemExit) as cm:
                    sf_orchestrator.main()
                
                self.assertEqual(cm.exception.code, -1)
                mock_print.assert_called()
                # When argv has only the script name, main() exits before creating orchestrator
                mock_run.assert_not_called()
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_orchestrator_with_minimal_arguments(self, mock_logger, mock_validation,
                                                mock_config, mock_modules):
        """Test orchestrator with minimal valid arguments."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        with patch.object(orchestrator, 'initialize') as mock_initialize, \
             patch.object(orchestrator, 'handle_server_startup') as mock_handle_server:
            
            mock_config_instance = MagicMock()
            mock_config.return_value = mock_config_instance
            orchestrator.config_manager = mock_config_instance
            
            # Test with just web server startup
            orchestrator.run(['-l', '127.0.0.1:8080'])
            
            mock_initialize.assert_called_once()
            mock_handle_server.assert_called_once()
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_build_output_config_defaults(self, mock_logger, mock_validation,
                                         mock_config, mock_modules):
        """Test output config building with default values."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        
        mock_args = MagicMock()
        # Set all optional arguments to None/False
        mock_args.o = None
        mock_args.H = False
        mock_args.n = False
        mock_args.r = False
        mock_args.S = None
        mock_args.D = None
        mock_args.f = False
        mock_args.F = None
        mock_args.t = None
        
        config = orchestrator._build_output_config(mock_args)
        
        # Should have empty config since no options were set
        # The method only adds keys when args are truthy
        self.assertEqual(config, {})
    
    @patch('sf_orchestrator.ModuleManager')
    @patch('sf_orchestrator.ConfigManager')
    @patch('sf_orchestrator.ValidationUtils')
    @patch('sf_orchestrator.logging.getLogger')
    def test_argument_parsing_edge_cases(self, mock_logger, mock_validation,
                                        mock_config, mock_modules):
        """Test argument parsing with edge cases."""
        orchestrator = sf_orchestrator.SpiderFootOrchestrator()
        parser = orchestrator.create_argument_parser()
        
        # Test with conflicting options
        test_cases = [
            ['-s', 'example.com', '-x', '-t', 'DOMAIN_NAME'],  # Valid strict mode
            ['--api', '--api-workers', '0'],  # Zero workers
            ['-S', '0'],  # Zero max length
            ['-m', ''],  # Empty module list
            ['-t', ''],  # Empty type list
        ]
        
        for args in test_cases:
            try:
                parsed = parser.parse_args(args)
                self.assertIsNotNone(parsed)
            except (SystemExit, ValueError):
                # Some combinations might be invalid
                pass
    
    def test_version_import_availability(self):
        """Test that version import works correctly."""
        # Test that __version__ is accessible
        try:
            from spiderfoot import __version__
            self.assertIsInstance(__version__, str)
            self.assertGreater(len(__version__), 0)
        except ImportError:
            self.fail("spiderfoot.__version__ should be importable")


if __name__ == '__main__':
    unittest.main()
