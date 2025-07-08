#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sf_orchestrator
# Purpose:      Modular orchestrator for SpiderFoot - integrates CLI, API, WebUI
#
# Author:      SpiderFoot Team
#
# Created:     2025-07-06
# Copyright:   (c) SpiderFoot Team 2025
# Licence:     MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Modular Orchestrator

This module serves as the main entry point for SpiderFoot, providing a clean
interface that orchestrates the various components (CLI, API, WebUI) using
modular, reusable components.
"""

import argparse
import logging
import multiprocessing as mp
import os
import sys
from pathlib import Path

# Import modular components
from spiderfoot.core.config import ConfigManager
from spiderfoot.core.modules import ModuleManager
from spiderfoot.core.scan import ScanManager
from spiderfoot.core.server import ServerManager
from spiderfoot.core.validation import ValidationUtils

# Import SpiderFoot core
from spiderfoot import __version__, SpiderFootDb
from spiderfoot.logger import logListenerSetup, logWorkerSetup


class SpiderFootOrchestrator:
    """
    Main orchestrator class that coordinates all SpiderFoot components.
    This provides a clean, modular interface for CLI, API, and WebUI.
    """
    
    def __init__(self):
        """Initialize the SpiderFoot orchestrator."""
        self.log = logging.getLogger(f"spiderfoot.{__name__}")
        
        # Initialize modular components
        self.config_manager = ConfigManager()
        self.module_manager = ModuleManager()
        self.validation_utils = ValidationUtils()
        
        # These will be initialized after configuration
        self.scan_manager = None
        self.server_manager = None
        
        # Runtime state
        self.config = None
        self.modules = None
        self.correlation_rules = None
        self.logging_queue = None
    
    def initialize(self) -> None:
        """Initialize all components with proper configuration."""
        try:
            # Validate Python version
            self.validation_utils.validate_python_version()
            
            # Ensure we're in the correct directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            os.chdir(script_dir)
            
            # Add current directory to Python path
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            
            # Initialize configuration
            self.config = self.config_manager.initialize()
            
            # Validate legacy files
            self.config_manager.validate_legacy_files()
            
            # Load modules and correlation rules
            self.modules = self.module_manager.load_modules()
            self.correlation_rules = self.module_manager.load_correlation_rules()
            
            # Update config with loaded components
            self.config['__modules__'] = self.modules
            self.config['__correlationrules__'] = self.correlation_rules
            
            # Initialize remaining managers
            self.scan_manager = ScanManager(self.config)
            self.server_manager = ServerManager(self.config)
            
            # Set up logging
            self.logging_queue = mp.Queue()
            
            # Configure logging level based on any previous settings
            current_log_level = logging.getLogger().getEffectiveLevel()
            if current_log_level == logging.WARNING:
                # Quiet mode - modify config to reflect this
                self.config['_debug'] = False
                self.config['__logging'] = False  # Disable verbose logging
            elif current_log_level == logging.DEBUG:
                # Debug mode
                self.config['_debug'] = True
                self.config['__logging'] = True
            else:
                # Normal mode
                self.config['_debug'] = False
                self.config['__logging'] = True
            
            logListenerSetup(self.logging_queue, self.config)
            logWorkerSetup(self.logging_queue)
            
            self.log.info("SpiderFoot orchestrator initialized successfully")
            
        except Exception as e:
            self.log.critical(f"Failed to initialize SpiderFoot orchestrator: {e}", exc_info=True)
            raise
    
    def create_argument_parser(self) -> argparse.ArgumentParser:
        """
        Create and configure the argument parser.
        
        Returns:
            Configured ArgumentParser instance
        """
        parser = argparse.ArgumentParser(
            description=f"SpiderFoot {__version__}: Open Source Intelligence Automation."
        )
        
        # General options
        parser.add_argument("-d", "--debug", action='store_true',
                          help="Enable debug output.")
        parser.add_argument("-V", "--version", action='store_true',
                          help="Display the version of SpiderFoot and exit.")
        parser.add_argument("--max-threads", type=int,
                          help="Max number of modules to run concurrently.")
        parser.add_argument("-q", action='store_true',
                          help="Disable logging. This will also hide errors!")
        
        # Server options
        parser.add_argument("-l", "--listen", metavar="IP:port",
                          help="IP and port to listen on for web UI.")
        parser.add_argument("--api", action='store_true',
                          help="Start FastAPI server instead of web UI.")
        parser.add_argument("--api-listen", metavar="IP:port",
                          help="IP and port for FastAPI server to listen on.")
        parser.add_argument("--api-workers", type=int, default=1,
                          help="Number of FastAPI worker processes.")
        parser.add_argument("--both", action='store_true',
                          help="Start both web UI and FastAPI servers.")
        
        # Scanning options
        parser.add_argument("-s", metavar="TARGET", help="Target for the scan.")
        parser.add_argument("-m", metavar="mod1,mod2,...", type=str, 
                          help="Modules to enable.")
        parser.add_argument("-t", metavar="type1,type2,...", type=str,
                          help="Event types to collect (modules selected automatically).")
        parser.add_argument("-u", choices=["all", "footprint", "investigate", "passive"],
                          type=str, help="Select modules automatically by use case")
        parser.add_argument("-x", action='store_true', 
                          help="STRICT MODE. Will only enable modules that can directly consume your target.")
        
        # Output options
        parser.add_argument("-o", choices=["tab", "csv", "json"],
                          type=str, help="Output format. Tab is default.")
        parser.add_argument("-H", action='store_true',
                          help="Don't print field headers, just data.")
        parser.add_argument("-n", action='store_true',
                          help="Strip newlines from data.")
        parser.add_argument("-r", action='store_true',
                          help="Include the source data field in tab/csv output.")
        parser.add_argument("-S", metavar="LENGTH", type=int,
                          help="Maximum data length to display.")
        parser.add_argument("-D", metavar='DELIMITER', type=str,
                          help="Delimiter to use for CSV output. Default is ,.")
        parser.add_argument("-f", action='store_true',
                          help="Filter out other event types that weren't requested with -t.")
        parser.add_argument("-F", metavar="type1,type2,...", type=str,
                          help="Show only a set of event types, comma-separated.")
        
        # Information options
        parser.add_argument("-M", "--modules", action='store_true',
                          help="List available modules.")
        parser.add_argument("-T", "--types", action='store_true',
                          help="List available event types.")
        parser.add_argument("-C", "--correlate", metavar="scanID",
                          help="Run correlation rules against a scan ID.")
        
        return parser
    
    def handle_version(self) -> None:
        """Handle version display."""
        print(f"SpiderFoot {__version__}")
        sys.exit(0)
    
    def handle_modules_list(self) -> None:
        """Handle module listing."""
        modules = self.module_manager.list_modules()
        print(f"Total modules: {len(modules)}")
        
        for module_name in modules:
            info = self.module_manager.get_module_info(module_name)
            description = info.get('descr', 'No description') if info else 'No description'
            print(f"{module_name}: {description}")
        
        sys.exit(0)
    
    def handle_types_list(self) -> None:
        """Handle event types listing."""
        dbh = SpiderFootDb(self.config, init=True)
        etypes = dbh.eventTypes()
        
        if etypes:
            print(f"Total event types: {len(etypes)}")
            for etype in sorted(etypes, key=lambda x: x[1]):
                print(f"{etype[1]}")
        
        sys.exit(0)
    
    def handle_correlations(self, scan_id: str) -> None:
        """
        Handle correlation execution.
        
        Args:
            scan_id: Scan ID to run correlations against
        """
        try:
            from spiderfoot.correlation.rule_executor import RuleExecutor
            from spiderfoot.correlation.event_enricher import EventEnricher
            from spiderfoot.correlation.result_aggregator import ResultAggregator
            
            # Validate scan ID
            scan_id = self.validation_utils.validate_scan_id(scan_id)
            
            dbh = SpiderFootDb(self.config, init=True)
            rules = self.correlation_rules
            
            # Execute rules
            executor = RuleExecutor(dbh, rules, scan_ids=[scan_id])
            results = executor.run()
            
            # Enrich results
            enricher = EventEnricher(dbh)
            for rule_id, result in results.items():
                if 'events' in result:
                    result['events'] = enricher.enrich_sources(scan_id, result['events'])
                    result['events'] = enricher.enrich_entities(scan_id, result['events'])
            
            # Aggregate results
            aggregator = ResultAggregator()
            agg_count = aggregator.aggregate(list(results.values()), method='count')
            
            print(f"Correlated {agg_count} results for scan {scan_id}")
            sys.exit(0)
            
        except Exception as e:
            self.log.error(f"Correlation execution failed: {e}")
            sys.exit(-1)
    
    def handle_scan(self, args) -> None:
        """
        Handle scan execution.
        
        Args:
            args: Parsed command line arguments
        """
        try:
            # Validate scan arguments
            scan_params = self.scan_manager.validate_scan_arguments(
                target=args.s,
                modules=self.validation_utils.validate_module_list(args.m) if args.m else None,
                event_types=self.validation_utils.validate_event_types(args.t) if args.t else None,
                usecase=args.u,
                strict_mode=args.x
            )
            
            # Prepare modules
            module_list = self.scan_manager.prepare_modules(scan_params, self.modules)
            
            if not module_list:
                self.log.error("Based on your criteria, no modules were enabled.")
                sys.exit(-1)
            
            # Prepare output configuration
            output_config = self._build_output_config(args)
            
            # Prepare scan configuration
            scan_config = self.scan_manager.prepare_scan_config(scan_params, output_config)
            
            # Apply command line configuration
            self.config_manager.apply_command_line_args(args)
            scan_config.update(self.config)
            
            # Set up signal handler
            self.scan_manager.setup_signal_handler("pending")
            
            # Execute scan
            scan_id = self.scan_manager.execute_scan(
                scan_name=scan_params['target'],
                target=scan_params['target'],
                target_type=scan_params['target_type'],
                modules=module_list,
                config=scan_config,
                logging_queue=self.logging_queue
            )
            
            # Monitor scan to completion
            result = self.scan_manager.monitor_scan(scan_id)
            
            if result['status'] == 'FINISHED':
                self.log.info(f"Scan {scan_id} completed successfully")
            else:
                self.log.warning(f"Scan {scan_id} ended with status: {result['status']}")
            
            sys.exit(0)
            
        except Exception as e:
            self.log.error(f"Scan execution failed: {e}")
            sys.exit(-1)
    
    def _build_output_config(self, args) -> dict:
        """
        Build output configuration from command line arguments.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Dict containing output configuration
        """
        output_config = {}
        
        if args.o:
            output_config['_format'] = self.validation_utils.validate_output_format(args.o)
        
        if args.H:
            output_config['_showheaders'] = False
        
        if args.n:
            output_config['_stripnewline'] = True
        
        if args.r:
            output_config['_showsource'] = True
        
        if args.S:
            output_config['_maxlength'] = args.S
        
        if args.D:
            output_config['_csvdelim'] = args.D
        
        if args.f:
            output_config['_showonlyrequested'] = True
        
        if args.F:
            output_config['_requested'] = self.validation_utils.validate_event_types(args.F)
            output_config['_showonlyrequested'] = True
        
        if args.t:
            output_config['_requested'] = self.validation_utils.validate_event_types(args.t)
        
        return output_config
    
    def handle_server_startup(self, args) -> None:
        """
        Handle server startup based on arguments.
        
        Args:
            args: Parsed command line arguments
        """
        # Prepare server configurations
        web_config = self.config_manager.get_web_config()
        api_config = self.config_manager.get_api_config()
        
        # Apply command line overrides
        if args.listen:
            try:
                host, port = self.validation_utils.parse_host_port(args.listen)
                web_config.update({'host': host, 'port': port})
            except ValueError as e:
                self.log.error(f"Invalid listen address: {e}")
                sys.exit(-1)
        
        if args.api_listen:
            try:
                host, port = self.validation_utils.parse_host_port(args.api_listen, default_port=8001)
                api_config.update({'host': host, 'port': port})
            except ValueError as e:
                self.log.error(f"Invalid API listen address: {e}")
                sys.exit(-1)
        
        if args.api_workers:
            api_config['workers'] = args.api_workers
        
        # Start appropriate server(s)
        if args.api:
            self.server_manager.start_fastapi_server(api_config, self.logging_queue)
        elif args.both:
            self.server_manager.start_both_servers(web_config, api_config, self.logging_queue)
        else:
            self.server_manager.start_web_server(web_config, self.logging_queue)
    
    def run(self, args=None) -> None:
        """
        Main entry point for the orchestrator.
        
        Args:
            args: Optional list of command line arguments
        """
        try:
            # Parse command line arguments
            parser = self.create_argument_parser()
            parsed_args = parser.parse_args(args)
            
            # Handle version first
            if parsed_args.version:
                self.handle_version()
            
            # Configure logging based on command line arguments BEFORE initialization
            self._configure_logging(parsed_args)
            
            # Initialize if we have any actual operation to perform
            if any([parsed_args.s, parsed_args.modules, parsed_args.types, parsed_args.correlate,
                   parsed_args.listen, parsed_args.api, parsed_args.both, 
                   hasattr(parsed_args, 'listen') or hasattr(parsed_args, 'api')]):
                self.initialize()
            
            # Apply configuration from command line
            if hasattr(parsed_args, 'debug') and parsed_args.debug:
                if self.config:
                    self.config['_debug'] = True
            
            # Handle information requests
            if parsed_args.modules:
                self.handle_modules_list()
            
            if parsed_args.types:
                self.handle_types_list()
            
            if parsed_args.correlate:
                self.handle_correlations(parsed_args.correlate)
            
            # Handle scanning
            if parsed_args.s:
                self.handle_scan(parsed_args)
            
            # Handle server startup
            if any([parsed_args.listen, parsed_args.api, parsed_args.both]) or not any(vars(parsed_args).values()):
                self.handle_server_startup(parsed_args)
            
        except KeyboardInterrupt:
            self.log.info("Interrupted by user")
            sys.exit(0)
        except Exception as e:
            self.log.critical(f"Unhandled exception in orchestrator: {e}", exc_info=True)
            sys.exit(-1)

    def _configure_logging(self, parsed_args) -> None:
        """
        Configure logging based on command line arguments.
        
        Args:
            parsed_args: Parsed command line arguments
        """
        log_level = logging.INFO
        
        # Handle quiet mode - should suppress INFO and below
        if hasattr(parsed_args, 'q') and parsed_args.q:
            log_level = logging.WARNING
        
        # Handle debug mode - overrides quiet
        if hasattr(parsed_args, 'debug') and parsed_args.debug:
            log_level = logging.DEBUG
            
        # Configure root logger
        logging.getLogger().setLevel(log_level)
        
        # Set specific logger levels
        for logger_name in ['spiderfoot', 'sf_orchestrator', 'scan', 'core', 'rule_executor']:
            logger = logging.getLogger(logger_name)
            logger.setLevel(log_level)


def main():
    """Main entry point when called directly."""
    if len(sys.argv) <= 1:
        print("SpiderFoot usage:")
        print("  Web UI:       python sf_orchestrator.py -l <ip>:<port>")
        print("  FastAPI:      python sf_orchestrator.py --api [--api-listen <ip>:<port>]")
        print("  Both servers: python sf_orchestrator.py --both [-l <ip>:<port>] [--api-listen <ip>:<port>]")
        print("  CLI scan:     python sf_orchestrator.py -s <target> [options]")
        print("Try --help for full guidance.")
        sys.exit(-1)
    
    orchestrator = SpiderFootOrchestrator()
    orchestrator.run()


if __name__ == '__main__':
    main()
