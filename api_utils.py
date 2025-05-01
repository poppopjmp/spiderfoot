# -*- coding: utf-8 -*-
# -----------------------------------------------------------------
# Name:         api_utils
# Purpose:      Utilities shared between API implementations
#
# Author:       Agostino Panico <van1sh@van1shland.io>
#
# FastAPI Port: '01/05/2025
# Copyright:    (c) Agostino Panico
# License:      MIT
# -----------------------------------------------------------------
import json
import time
from typing import Dict, Any, List
import logging

class ApiHelpers:
    """Helper functions for API implementations."""
    
    @staticmethod
    def format_error(status_code: int, message: str) -> Dict[str, Any]:
        """Create a standardized error response structure.
        
        Args:
            status_code (int): HTTP response status code
            message (str): Error message
            
        Returns:
            dict: Error response structure
        """
        return {
            'error': {
                'http_status': status_code,
                'message': message,
            }
        }
    
    @staticmethod
    def validate_scan_input(
        scanname: str, 
        scantarget: str, 
        modulelist: str = None, 
        typelist: str = None, 
        usecase: str = None, 
        config: Dict[str, Any] = None
    ) -> tuple:
        """Validate scan inputs and build module list.
        
        Args:
            scanname (str): Name of scan
            scantarget (str): Target for scan
            modulelist (str): Comma-separated module list
            typelist (str): Comma-separated event types
            usecase (str): Use case (all, footprint, investigate, passive)
            config (dict): SpiderFoot configuration
            
        Returns:
            tuple: (error_dict or None, target_type, normalized_target, module_list)
        """
        from sflib import SpiderFoot
        from spiderfoot import SpiderFootHelpers

        scanname = scanname.strip()
        scantarget = scantarget.strip()

        if not scanname:
            return ({"status_code": 400, "message": "Scan name cannot be empty."}, None, None, None)

        if not scantarget:
            return ({"status_code": 400, "message": "Scan target cannot be empty."}, None, None, None)

        if not typelist and not modulelist and not usecase:
            return ({"status_code": 400, "message": "Must specify modules, types, or a use case."}, None, None, None)

        targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
        if targetType is None:
            return ({"status_code": 400, "message": f"Could not determine target type for: {scantarget}"}, None, None, None)

        if not config:
            return ({"status_code": 500, "message": "Internal error: No configuration provided"}, None, None, None)

        sf = SpiderFoot(config)
        final_modlist = list()

        if modulelist:
            final_modlist = modulelist.split(',')
            valid_mods = list(config.get('__modules__', {}).keys())
            invalid_mods = [m for m in final_modlist if m not in valid_mods]
            if invalid_mods:
                return ({"status_code": 400, "message": f"Invalid modules specified: {', '.join(invalid_mods)}"}, None, None, None)

        if len(final_modlist) == 0 and typelist:
            types = typelist.split(',')
            final_modlist = sf.modulesProducing(types)
            if not final_modlist:
                return ({"status_code": 400, "message": f"No modules found producing specified types: {typelist}"}, None, None, None)

        if len(final_modlist) == 0 and usecase:
            if usecase == 'all':
                final_modlist = list(config.get('__modules__', {}).keys())
            elif usecase == 'footprint':
                final_modlist = sf.modulesProducing(config['_internettargets'])
            elif usecase == 'investigate':
                final_modlist = sf.modulesProducing(config['_genericusers'])
            elif usecase == 'passive':
                all_mods = config.get('__modules__', {})
                final_modlist = [m for m in all_mods if not all_mods[m].get('invasive', False)]
            else:
                return ({"status_code": 400, "message": f"Invalid use case specified: {usecase}"}, None, None, None)

        if not final_modlist:
            return ({"status_code": 400, "message": "No modules selected for scan."}, None, None, None)

        # Ensure storage modules are included/excluded as needed
        if "sfp__stor_db" not in final_modlist:
            final_modlist.append("sfp__stor_db")
        final_modlist.sort()

        if "sfp__stor_stdout" in final_modlist:
            final_modlist.remove("sfp__stor_stdout")

        # Normalize target based on type
        if targetType not in ["HUMAN_NAME", "USERNAME", "BITCOIN_ADDRESS"]:
            scantarget_normalized = scantarget.lower()
        else:
            scantarget_normalized = scantarget

        return (None, targetType, scantarget_normalized, final_modlist)
    
    @staticmethod
    def start_scan(
        logging_queue, 
        scanname: str, 
        scantarget: str, 
        module_list: list, 
        target_type: str, 
        config: Dict[str, Any]
    ) -> tuple:
        """Start a SpiderFoot scan.
        
        Args:
            logging_queue: Multiprocessing queue for logging
            scanname (str): Name of scan
            scantarget (str): Target for scan
            module_list (list): List of modules to run
            target_type (str): Type of target (e.g., DOMAIN, IP_ADDRESS)
            config (dict): SpiderFoot configuration
            
        Returns:
            tuple: (error_dict or None, scan_id)
        """
        import multiprocessing as mp
        import time
        from sfscan import startSpiderFootScanner
        from spiderfoot import SpiderFootDb, SpiderFootHelpers

        scan_id = SpiderFootHelpers.genScanInstanceId()
        db = SpiderFootDb(config)
        
        try:
            p = mp.Process(target=startSpiderFootScanner, args=(
                logging_queue, scanname, scan_id, scantarget, target_type, module_list, config))
            p.daemon = True
            p.start()
        except Exception as e:
            log = logging.getLogger("spiderfoot.api_utils")
            log.error(f"[-] Scan [{scan_id}] failed: {e}", exc_info=True)
            return ({"status_code": 500, "message": f"Scan [{scan_id}] failed to start: {e}"}, None)

        # Wait until the scan has initialized (with a timeout)
        start_time = time.time()
        while db.scanInstanceGet(scan_id) is None:
            if time.time() - start_time > 30:  # 30 second timeout
                return ({"status_code": 500, "message": f"Scan [{scan_id}] failed to initialize within timeout."}, None)
            time.sleep(1)

        return (None, scan_id)
    
    @staticmethod
    def load_modules_and_rules(config: Dict[str, Any], base_path: str = None) -> Dict[str, Any]:
        """Load modules and correlation rules into config.
        
        Args:
            config (dict): SpiderFoot configuration
            base_path (str): Base path for module/rule directories
            
        Returns:
            dict: Updated config with modules and rules
        """
        import os
        from spiderfoot import SpiderFootHelpers
        
        log = logging.getLogger("spiderfoot.api_utils")
        
        if not base_path:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Load modules
        mod_dir = os.path.join(base_path, 'modules')
        try:
            modules = SpiderFootHelpers.loadModulesAsDict(mod_dir, ['sfp_template.py'])
            if modules:
                config['__modules__'] = modules
                log.info(f"Loaded {len(modules)} modules")
        except Exception as e:
            log.error(f"Failed to load modules: {e}", exc_info=True)
        
        # Load correlation rules
        rules_dir = os.path.join(base_path, 'correlations')
        try:
            rules = SpiderFootHelpers.loadCorrelationRulesAsDict(rules_dir)
            if rules:
                config['__correlationrules__'] = rules
                log.info(f"Loaded {len(rules)} correlation rules")
        except Exception as e:
            log.error(f"Failed to load correlation rules: {e}", exc_info=True)
            
        return config
    
    @staticmethod
    def save_config(config: Dict[str, Any], new_options: Dict[str, Any]) -> tuple:
        """Save configuration settings.
        
        Args:
            config (dict): Current SpiderFoot configuration
            new_options (dict): New configuration options to save
            
        Returns:
            tuple: (error_dict or None, updated_config)
        """
        from sflib import SpiderFoot
        from spiderfoot import SpiderFootDb
        from copy import deepcopy
        
        log = logging.getLogger("spiderfoot.api_utils")
        
        try:
            dbh = SpiderFootDb(config)
            sf = SpiderFoot(config)
            current_config_structure = deepcopy(config)
            unserialized_opts = sf.configUnserialize(new_options, current_config_structure)

            updated_config = deepcopy(config)
            updated_config.update(unserialized_opts)

            serialized_for_db = sf.configSerialize(updated_config)
            dbh.configSet(serialized_for_db)
            return (None, updated_config)
        except Exception as e:
            log.error(f"Error saving settings: {e}", exc_info=True)
            return ({"status_code": 500, "message": f"Failed to save settings: {e}"}, None)
    
    @staticmethod
    def format_scan_correlation_results(correlations: List) -> List[List]:
        """Format scan correlation results for API response.
        
        Args:
            correlations (list): Raw correlation results from database
            
        Returns:
            list: Formatted correlation results
        """
        if not correlations:
            return []
            
        retdata = []
        for row in correlations:
            # Structure: correlation_id, correlation, rule name, rule risk, rule id, rule description, events, created
            if len(row) < 6:
                continue
                
            retdata.append([
                row[0],  # correlation_id
                row[1],  # correlation
                row[2],  # rule name
                row[3],  # rule risk
                row[4],  # rule id
                row[5],  # rule description
                row[6] if len(row) > 6 else "",  # events
                row[7] if len(row) > 7 else ""   # created
            ])
            
        return retdata
    
    @staticmethod
    def prepare_scan_options_response(scan_id: str, meta: List, config: Dict[str, Any], config_obj: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare scan options response.
        
        Args:
            scan_id (str): Scan ID
            meta (list): Scan metadata
            config (dict): Scan-specific configuration
            config_obj (dict): Global SpiderFoot configuration
            
        Returns:
            dict: Formatted scan options response
        """
        from sflib import SpiderFoot
        import time
        
        ret = dict()
        
        if meta[3] != 0:
            started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(meta[3]))
        else:
            started = "Not yet"

        if meta[4] != 0:
            finished = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(meta[4]))
        else:
            finished = "Not yet"

        ret['meta'] = [meta[0], meta[1], meta[2], started, finished, meta[5]]
        ret['config'] = config
        ret['configdesc'] = dict()
        
        sf = SpiderFoot(config_obj)
        for key in list(ret['config'].keys()):
            if ':' not in key:
                # Global option
                if key in sf.config and '_description' in sf.config[key]:
                    desc = sf.config[key]['_description']
                    if desc:
                        ret['configdesc'][key] = desc
            else:
                # Module option
                mod = key.split(":")[0]
                opt = key.split(":")[1]
                if mod in sf.config.get('__modules__', {}) and 'opts' in sf.config['__modules__'][mod]:
                    if opt in sf.config['__modules__'][mod]['opts']:
                        if '_description' in sf.config['__modules__'][mod]['opts'][opt]:
                            desc = sf.config['__modules__'][mod]['opts'][opt]['_description']
                            if desc:
                                ret['configdesc'][key] = desc

        return ret

    @staticmethod
    def serialize_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare configuration for JSON serialization.
        
        Args:
            config (dict): SpiderFoot configuration
            
        Returns:
            dict: Configuration safe for serialization
        """
        # Deep copy to avoid modifying the original
        serializable_config = {}
        
        # Handle complex types and make config JSON serializable
        for key, value in config.items():
            try:
                # Test if value is JSON serializable
                json.dumps(value)
                serializable_config[key] = value
            except (TypeError, OverflowError):
                # Convert non-serializable types to strings
                if isinstance(value, (set, tuple)):
                    serializable_config[key] = list(value)
                else:
                    serializable_config[key] = str(value)
        
        return serializable_config
    
    @staticmethod
    def format_scan_list(scan_list: List) -> List[List]:
        """Format scan list for API response.
        
        Args:
            scan_list (list): Raw scan list from database
            
        Returns:
            list: Formatted scan list
        """
        retlist = []
        for scan in scan_list:
            created = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(scan[3]))
            if scan[4]:
                finished = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(scan[4]))
            else:
                finished = ""
            retlist.append([scan[0], scan[1], created, finished, scan[5]])
        return retlist
    
    @staticmethod
    def format_scan_events(scan_events: List) -> List[List]:
        """Format scan event results for API response.
        
        Args:
            scan_events (list): Raw scan events from database
            
        Returns:
            list: Formatted scan events
        """
        retdata = []
        for row in scan_events:
            lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
            retdata.append([
                lastseen,
                row[1],  # Data
                row[2],  # Module
                row[3],  # Source
                row[4],  # Event Type
                row[5],  # confidence
                row[6],  # visibility
                row[7],  # risk
                row[8],  # hash
                row[9],  # source event hash
                row[10],  # module instance ID
                row[11],  # scan instance ID
                row[13],  # false positive
                row[14],  # id
            ])
        return retdata
