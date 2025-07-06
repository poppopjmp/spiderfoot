"""
Scan Manager for SpiderFoot

This module handles scan-related operations including validation, 
preparation, execution, and monitoring.
"""

import sys
import time
import signal
import logging
import multiprocessing as mp
from typing import Dict, Any, List, Optional, Tuple
from copy import deepcopy

from spiderfoot import SpiderFootDb, SpiderFootHelpers
from spiderfoot.sflib import SpiderFoot
from spiderfoot.scan_service.scanner import startSpiderFootScanner


class ScanManager:
    """Centralized scan management for SpiderFoot."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the scan manager.
        
        Args:
            config: SpiderFoot configuration dictionary
        """
        self.config = config
        self.log = logging.getLogger(f"spiderfoot.{__name__}")
        self.active_scans = {}
        
    def validate_scan_arguments(self, target: str, modules: Optional[List[str]] = None,
                               event_types: Optional[List[str]] = None,
                               usecase: Optional[str] = None,
                               strict_mode: bool = False) -> Dict[str, Any]:
        """
        Validate scan arguments and prepare scan parameters.
        
        Args:
            target: Scan target
            modules: List of modules to use
            event_types: List of event types to collect
            usecase: Use case selection
            strict_mode: Enable strict mode
            
        Returns:
            Dict containing validated scan parameters
            
        Raises:
            ValueError: If validation fails
        """
        if not target:
            raise ValueError("Target is required for scanning")
        
        # Process target
        processed_target, target_type = self._process_target(target)
        
        if strict_mode and not event_types:
            raise ValueError("Strict mode can only be used with event types specified")
        
        if strict_mode and modules:
            raise ValueError("Strict mode cannot be used with specific modules")
        
        return {
            'target': processed_target,
            'target_type': target_type,
            'modules': modules or [],
            'event_types': event_types or [],
            'usecase': usecase,
            'strict_mode': strict_mode
        }
    
    def _process_target(self, target: str) -> Tuple[str, str]:
        """
        Process and validate the scan target.
        
        Args:
            target: Raw target string
            
        Returns:
            Tuple of (processed_target, target_type)
            
        Raises:
            ValueError: If target is invalid
        """
        # Handle quoted targets (usernames and names)
        if " " in target:
            target = f'"{target}"'
        if "." not in target and not target.startswith("+") and '"' not in target:
            target = f'"{target}"'
            
        target_type = SpiderFootHelpers.targetTypeFromString(target)
        
        if not target_type:
            raise ValueError(f"Could not determine target type. Invalid target: {target}")
        
        # Remove quotes for processing
        processed_target = target.strip('"')
        
        return processed_target, target_type
    
    def prepare_modules(self, scan_params: Dict[str, Any], sf_modules: Dict[str, Any]) -> List[str]:
        """
        Prepare module list based on scan parameters.
        
        Args:
            scan_params: Validated scan parameters
            sf_modules: Available SpiderFoot modules
            
        Returns:
            List of module names to use for the scan
        """
        sf = SpiderFoot(self.config)
        modlist = []
        
        target_type = scan_params['target_type']
        modules = scan_params['modules']
        event_types = scan_params['event_types']
        usecase = scan_params['usecase']
        strict_mode = scan_params['strict_mode']
        
        # Auto-select all modules if none specified
        if not event_types and not modules and not usecase:
            self.log.warning("No modules, types or use case specified, enabling all modules")
            for module_name in sf_modules.keys():
                if "__" not in module_name:  # Skip internal modules
                    modlist.append(module_name)
        
        # Module selection by event types
        if event_types:
            types_str = ",".join(event_types)
            modlist = sf.modulesProducing(types_str)
            newmods = deepcopy(modlist)
            newmodcpy = deepcopy(newmods)
            
            # Find modules producing the required types
            while len(newmodcpy) > 0:
                for etype in sf.eventsToModules(newmodcpy):
                    producing_mods = sf.modulesProducing(etype)
                    for mod in producing_mods:
                        if mod not in modlist and mod not in newmods:
                            newmods.append(mod)
                newmodcpy = deepcopy(newmods)
                newmods = []
        
        # Module selection by specific modules
        if modules:
            modlist = [mod for mod in modules if mod]  # Filter out empty strings
        
        # Module selection by use case
        if usecase:
            usecase_formatted = usecase[0].upper() + usecase[1:].lower()
            for mod_name, mod_info in sf_modules.items():
                groups = mod_info.get('group', '')
                if isinstance(groups, str):
                    groups = [groups]
                if usecase_formatted == 'All' or usecase_formatted in groups:
                    if mod_name not in modlist:
                        modlist.append(mod_name)
        
        # Apply strict mode filtering
        if strict_mode and event_types:
            strict_modlist = []
            consuming_mods = sf.modulesConsuming([target_type])
            
            for mod in consuming_mods:
                if mod not in strict_modlist:
                    strict_modlist.append(mod)
            
            # Filter by modules producing requested types
            final_modlist = []
            for mod in strict_modlist:
                mod_produces = sf.moduleProduces(mod)
                for event_type in event_types:
                    if event_type in mod_produces and mod not in final_modlist:
                        final_modlist.append(mod)
            
            modlist = final_modlist
        
        # Add required storage modules
        storage_modules = ["sfp__stor_db", "sfp__stor_stdout", "sfp__stor_elasticsearch"]
        for storage_mod in storage_modules:
            if storage_mod not in modlist:
                modlist.append(storage_mod)
        
        return modlist
    
    def prepare_scan_config(self, scan_params: Dict[str, Any], output_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Prepare scan configuration.
        
        Args:
            scan_params: Validated scan parameters
            output_config: Optional output configuration
            
        Returns:
            Dict containing scan configuration
        """
        dbh = SpiderFootDb(self.config, init=True)
        sf = SpiderFoot(self.config)
        
        # Get configuration from database
        cfg = sf.configUnserialize(dbh.configGet(), self.config)
        
        # Apply scan-specific settings
        if scan_params.get('strict_mode') and scan_params.get('event_types'):
            cfg['__outputfilter'] = scan_params['event_types']
        
        # Apply output configuration if provided
        if output_config:
            # Configure stdout module
            if '__modules__' in cfg and 'sfp__stor_stdout' in cfg['__modules__']:
                stdout_opts = cfg['__modules__']['sfp__stor_stdout'].get('opts', {})
                
                # Apply output format settings
                for key, value in output_config.items():
                    if key.startswith('_'):  # Configuration keys start with underscore
                        stdout_opts[key] = value
        
        return cfg
    
    def execute_scan(self, scan_name: str, target: str, target_type: str,
                    modules: List[str], config: Dict[str, Any],
                    logging_queue: mp.Queue) -> str:
        """
        Execute a scan with the given parameters.
        
        Args:
            scan_name: Name for the scan
            target: Scan target
            target_type: Type of target
            modules: List of modules to use
            config: Scan configuration
            logging_queue: Logging queue for multiprocessing
            
        Returns:
            Scan ID
            
        Raises:
            RuntimeError: If scan fails to start
        """
        # Generate unique scan ID
        scan_id = SpiderFootHelpers.genScanInstanceId()
        
        try:
            # Start scan process
            process = mp.Process(
                target=startSpiderFootScanner,
                args=(logging_queue, scan_name, scan_id, target, target_type, modules, config)
            )
            process.daemon = True
            process.start()
            
            # Store scan process info
            self.active_scans[scan_id] = {
                'process': process,
                'scan_name': scan_name,
                'target': target,
                'target_type': target_type,
                'modules': modules,
                'start_time': time.time()
            }
            
            self.log.info(f"Started scan {scan_id} for target {target}")
            return scan_id
            
        except Exception as e:
            self.log.error(f"Failed to start scan: {e}")
            raise RuntimeError(f"Scan execution failed: {e}")
    
    def monitor_scan(self, scan_id: str, timeout: int = 0) -> Dict[str, Any]:
        """
        Monitor a scan until completion or timeout.
        
        Args:
            scan_id: Scan ID to monitor
            timeout: Timeout in seconds (0 = no timeout)
            
        Returns:
            Dict containing scan status information
        """
        dbh = SpiderFootDb(self.config, init=True)
        start_time = time.time()
        
        while True:
            time.sleep(1)
            
            # Check timeout
            if timeout > 0 and (time.time() - start_time) > timeout:
                return {'status': 'TIMEOUT', 'scan_id': scan_id}
            
            # Get scan info from database
            info = dbh.scanInstanceGet(scan_id)
            if not info:
                continue
                
            status = info[5]
            if status in ["ERROR-FAILED", "ABORT-REQUESTED", "ABORTED", "FINISHED"]:
                # Wait for process cleanup
                if scan_id in self.active_scans:
                    process = self.active_scans[scan_id]['process']
                    process.join(timeout=60)
                    if process.is_alive():
                        self.log.warning(f"Process for scan {scan_id} didn't terminate, killing it")
                        process.terminate()
                    del self.active_scans[scan_id]
                
                return {
                    'status': status,
                    'scan_id': scan_id,
                    'scan_name': info[0],
                    'target': info[1],
                    'created': info[2],
                    'started': info[3],
                    'ended': info[4]
                }
    
    def stop_scan(self, scan_id: str) -> bool:
        """
        Stop a running scan.
        
        Args:
            scan_id: Scan ID to stop
            
        Returns:
            True if scan was stopped successfully
        """
        try:
            dbh = SpiderFootDb(self.config, init=True)
            
            # Mark scan as aborted in database
            dbh.scanInstanceSet(scan_id, None, None, "ABORT-REQUESTED")
            
            # Terminate process if still active
            if scan_id in self.active_scans:
                process = self.active_scans[scan_id]['process']
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=10)
                del self.active_scans[scan_id]
            
            self.log.info(f"Stopped scan {scan_id}")
            return True
            
        except Exception as e:
            self.log.error(f"Failed to stop scan {scan_id}: {e}")
            return False
    
    def get_scan_status(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a scan.
        
        Args:
            scan_id: Scan ID to check
            
        Returns:
            Dict containing scan status or None if not found
        """
        try:
            dbh = SpiderFootDb(self.config, init=True)
            info = dbh.scanInstanceGet(scan_id)
            
            if not info:
                return None
            
            return {
                'scan_id': scan_id,
                'scan_name': info[0],
                'target': info[1],
                'created': info[2],
                'started': info[3],
                'ended': info[4],
                'status': info[5]
            }
            
        except Exception as e:
            self.log.error(f"Failed to get scan status for {scan_id}: {e}")
            return None
    
    def setup_signal_handler(self, scan_id: str) -> None:
        """
        Set up signal handler for scan interruption.
        
        Args:
            scan_id: Scan ID to handle interruption for
        """
        def handle_abort(signum, frame):
            self.log.info(f"Received interrupt signal, stopping scan {scan_id}")
            self.stop_scan(scan_id)
            sys.exit(-1)
        
        signal.signal(signal.SIGINT, handle_abort)
