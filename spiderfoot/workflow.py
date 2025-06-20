"""SpiderFoot Workflow Management.

This module provides workflow functionality for orchestrating multiple scans,
cross-correlations, and CTI report generation.
"""

import asyncio
import json
import logging
import multiprocessing as mp
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Callable

from spiderfoot import SpiderFootDb, SpiderFootHelpers, SpiderFootCorrelator
from spiderfoot.workspace import SpiderFootWorkspace
from sfscan import startSpiderFootScanner


class SpiderFootWorkflow:
    """Manages SpiderFoot workflows for multi-target scanning and analysis."""

    def __init__(self, config: dict, workspace: SpiderFootWorkspace, logging_queue=None):
        """Initialize workflow.
        
        Args:
            config: SpiderFoot configuration
            workspace: Associated workspace
            logging_queue: Logging queue for scan processes
        """
        self.config = config
        self.workspace = workspace
        self.logging_queue = logging_queue
        self.db = SpiderFootDb(config)
        self.log = logging.getLogger("spiderfoot.workflow")
        
        self.active_scans = {}
        self.scan_results = {}
        self.workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        
    def start_multi_target_scan(
        self, 
        targets: List[dict], 
        modules: List[str], 
        scan_options: dict = None,
        progress_callback: Callable = None
    ) -> List[str]:
        """Start scans for multiple targets.
        
        Args:
            targets: List of target dictionaries with 'value' and 'type'
            modules: List of modules to use for scanning
            scan_options: Additional scan configuration options
            progress_callback: Callback for progress updates
            
        Returns:
            List of scan IDs
        """
        scan_ids = []
        scan_options = scan_options or {}
        
        self.log.info(f"Starting multi-target scan for {len(targets)} targets")
        
        for target in targets:
            try:
                scan_id = self._start_single_scan(
                    target_value=target['value'],
                    target_type=target['type'],
                    modules=modules,
                    scan_options=scan_options,
                    target_metadata=target.get('metadata', {})
                )
                scan_ids.append(scan_id)
                
                # Add scan to workspace
                target_id = target.get('target_id')
                self.workspace.add_scan(scan_id, target_id)
                
                if progress_callback:
                    progress_callback(f"Started scan {scan_id} for target {target['value']}")
                    
            except Exception as e:
                self.log.error(f"Failed to start scan for target {target['value']}: {e}")
                if progress_callback:
                    progress_callback(f"Failed to start scan for target {target['value']}: {e}")
        
        return scan_ids

    def _start_single_scan(
        self, 
        target_value: str, 
        target_type: str, 
        modules: List[str],
        scan_options: dict,
        target_metadata: dict = None
    ) -> str:
        """Start a single scan.
        
        Args:
            target_value: Target to scan
            target_type: Type of target
            modules: Modules to use
            scan_options: Scan configuration
            target_metadata: Additional target metadata
            
        Returns:
            Scan ID
        """
        scan_id = SpiderFootHelpers.genScanInstanceId()
        scan_name = f"Workflow_{self.workflow_id}_{target_value}"
        
        # Prepare scan config
        scan_config = self.config.copy()
        scan_config.update(scan_options)
        scan_config['_modulesenabled'] = modules
        
        # Store scan metadata
        self.active_scans[scan_id] = {
            'target_value': target_value,
            'target_type': target_type,
            'started_time': time.time(),
            'status': 'STARTING',
            'metadata': target_metadata or {}
        }
        
        try:
            # Start scan process
            if self.logging_queue:
                p = mp.Process(
                    target=startSpiderFootScanner,
                    args=(
                        self.logging_queue, scan_name, scan_id, 
                        target_value, target_type, modules, scan_config
                    )
                )
                p.daemon = True
                p.start()
                
                self.active_scans[scan_id]['process'] = p
                self.active_scans[scan_id]['status'] = 'RUNNING'
                
                self.log.info(f"Started scan {scan_id} for target {target_value}")
                
            return scan_id
            
        except Exception as e:
            self.active_scans[scan_id]['status'] = 'FAILED'
            self.log.error(f"Failed to start scan for {target_value}: {e}")
            raise

    def wait_for_scans_completion(
        self, 
        scan_ids: List[str], 
        timeout: int = 3600,
        progress_callback: Callable = None
    ) -> Dict[str, str]:
        """Wait for multiple scans to complete.
        
        Args:
            scan_ids: List of scan IDs to wait for
            timeout: Maximum wait time in seconds
            progress_callback: Callback for progress updates
            
        Returns:
            Dictionary mapping scan_id to final status
        """
        start_time = time.time()
        scan_statuses = {}
        
        self.log.info(f"Waiting for {len(scan_ids)} scans to complete")
        
        while time.time() - start_time < timeout:
            completed_count = 0
            
            for scan_id in scan_ids:
                if scan_id in scan_statuses:
                    completed_count += 1
                    continue
                    
                scan_info = self.db.scanInstanceGet(scan_id)
                if scan_info:
                    status = scan_info[5]
                    
                    if status in ["FINISHED", "ABORTED", "ERROR-FAILED"]:
                        scan_statuses[scan_id] = status
                        completed_count += 1
                        
                        if progress_callback:
                            progress_callback(f"Scan {scan_id} completed with status: {status}")
                        
                        # Update active scan status
                        if scan_id in self.active_scans:
                            self.active_scans[scan_id]['status'] = status
                            self.active_scans[scan_id]['completed_time'] = time.time()
            
            if completed_count == len(scan_ids):
                self.log.info(f"All {len(scan_ids)} scans completed")
                break
                
            time.sleep(10)  # Check every 10 seconds
        
        # Handle timeout
        for scan_id in scan_ids:
            if scan_id not in scan_statuses:
                scan_statuses[scan_id] = 'TIMEOUT'
                self.log.warning(f"Scan {scan_id} timed out")
        
        return scan_statuses

    def run_cross_correlation(
        self, 
        scan_ids: List[str] = None,
        correlation_rules: List[str] = None
    ) -> List[dict]:
        """Run cross-correlation analysis across multiple scans.
        
        Args:
            scan_ids: List of scan IDs to correlate (default: all workspace scans)
            correlation_rules: Specific correlation rules to run
            
        Returns:
            List of correlation results
        """
        if not scan_ids:
            scan_ids = self.workspace.get_scan_ids()
            
        if not scan_ids:
            self.log.warning("No scans available for cross-correlation")
            return []
        
        self.log.info(f"Running cross-correlation analysis on {len(scan_ids)} scans")
        
        # Create cross-correlation engine
        correlator = SpiderFootWorkspaceCorrelator(
            self.db, 
            self.config.get('__correlationrules__', []),
            scan_ids
        )
        
        try:
            correlation_results = correlator.run_cross_correlations(correlation_rules)
            
            # Store results in workspace metadata
            if not self.workspace.metadata.get('correlations'):
                self.workspace.metadata['correlations'] = []
            
            correlation_run = {
                'timestamp': time.time(),
                'scan_ids': scan_ids,
                'results_count': len(correlation_results),
                'results': correlation_results
            }
            
            self.workspace.metadata['correlations'].append(correlation_run)
            self.workspace.save_workspace()
            
            self.log.info(f"Cross-correlation completed: {len(correlation_results)} results")
            return correlation_results
            
        except Exception as e:
            self.log.error(f"Cross-correlation failed: {e}")
            raise

    def get_scan_status(self, scan_id: str = None) -> Dict[str, Any]:
        """Get status of scans in workflow.
        
        Args:
            scan_id: Specific scan ID (optional)
            
        Returns:
            Scan status information
        """
        if scan_id:
            if scan_id in self.active_scans:
                return self.active_scans[scan_id]
            else:
                scan_info = self.db.scanInstanceGet(scan_id)
                if scan_info:
                    return {
                        'scan_id': scan_id,
                        'status': scan_info[5],
                        'target_value': scan_info[2],
                        'created': scan_info[3],
                        'started': scan_info[4],
                        'ended': scan_info[6] if len(scan_info) > 6 else None
                    }
                return None
        else:
            # Return status of all scans
            all_statuses = {}
            
            for scan_id in self.workspace.get_scan_ids():
                status = self.get_scan_status(scan_id)
                if status:
                    all_statuses[scan_id] = status
                    
            return all_statuses

    def cleanup_workflow(self) -> None:
        """Clean up workflow resources."""
        # Terminate any running processes
        for scan_id, scan_info in self.active_scans.items():
            if 'process' in scan_info and scan_info['process'].is_alive():
                try:
                    scan_info['process'].terminate()
                    scan_info['process'].join(timeout=5)
                    if scan_info['process'].is_alive():
                        scan_info['process'].kill()
                except Exception as e:
                    self.log.warning(f"Failed to cleanup scan process {scan_id}: {e}")
        
        self.log.info(f"Workflow {self.workflow_id} cleanup completed")


class SpiderFootWorkspaceCorrelator(SpiderFootCorrelator):
    """Extended correlator for cross-workspace analysis."""
    
    def __init__(self, dbh: SpiderFootDb, ruleset: List[dict], scan_ids: List[str]):
        """Initialize workspace correlator.
        
        Args:
            dbh: Database handle
            ruleset: Correlation rules
            scan_ids: List of scan IDs to correlate across
        """
        # Convert ruleset format for parent class
        rules_dict = {}
        for rule in ruleset:
            rule_id = rule.get('id', f"rule_{len(rules_dict)}")
            rules_dict[rule_id] = rule.get('rawYaml', '')
        
        super().__init__(dbh, rules_dict)
        self.scan_ids = scan_ids
        self.cross_scan_rules = self._load_cross_scan_rules()
    
    def _load_cross_scan_rules(self) -> List[dict]:
        """Load correlation rules suitable for cross-scan analysis."""
        cross_scan_rules = []
        
        # Define cross-scan correlation rules
        rules = [
            {
                'id': 'cross_scan_shared_infrastructure',
                'name': 'Shared Infrastructure Across Targets',
                'description': 'Identifies shared hosting, DNS servers, or certificates across different targets',
                'fields': ['IP_ADDRESS', 'DOMAIN_NAME', 'SSL_CERTIFICATE_ISSUED']
            },
            {
                'id': 'cross_scan_similar_technologies',
                'name': 'Similar Technologies Across Targets',
                'description': 'Identifies similar web technologies, CMS, or software versions',
                'fields': ['WEBSERVER_TECHNOLOGY', 'OPERATING_SYSTEM']
            },
            {
                'id': 'cross_scan_threat_indicators',
                'name': 'Threat Indicators Across Targets',
                'description': 'Identifies shared threat indicators or malicious activities',
                'fields': ['MALICIOUS_IPADDR', 'MALICIOUS_INTERNET_NAME', 'BLACKLISTED_IPADDR']
            }
        ]
        
        return rules
    
    def run_cross_correlations(self, specific_rules: List[str] = None) -> List[dict]:
        """Run cross-correlation analysis across multiple scans.
        
        Args:
            specific_rules: Specific rules to run (optional)
            
        Returns:
            List of cross-correlation results
        """
        results = []
        
        # Get data from all scans
        cross_scan_data = self._collect_cross_scan_data()
        
        # Run cross-scan correlation rules
        for rule in self.cross_scan_rules:
            if specific_rules and rule['id'] not in specific_rules:
                continue
                
            try:
                rule_results = self._apply_cross_scan_rule(rule, cross_scan_data)
                results.extend(rule_results)
            except Exception as e:
                self.log.error(f"Failed to apply cross-scan rule {rule['id']}: {e}")
        
        return results
    
    def _collect_cross_scan_data(self) -> Dict[str, List[dict]]:
        """Collect data from all scans for cross-correlation.
        
        Returns:
            Dictionary mapping data types to events across all scans
        """
        cross_scan_data = {}
        
        for scan_id in self.scan_ids:
            scan_events = self.dbh.scanResultEvent(scan_id, 'ALL')
            
            for event in scan_events:
                event_type = event[4]
                event_data = {
                    'scan_id': scan_id,
                    'created': event[0],
                    'data': event[1],
                    'module': event[3],
                    'type': event_type,
                    'confidence': event[6],
                    'visibility': event[7],
                    'risk': event[8]
                }
                
                if event_type not in cross_scan_data:
                    cross_scan_data[event_type] = []
                cross_scan_data[event_type].append(event_data)
        
        return cross_scan_data
    
    def _apply_cross_scan_rule(self, rule: dict, cross_scan_data: Dict[str, List[dict]]) -> List[dict]:
        """Apply a cross-scan correlation rule.
        
        Args:
            rule: Correlation rule definition
            cross_scan_data: Data from all scans
            
        Returns:
            List of correlation results
        """
        results = []
        rule_id = rule['id']
        
        # Get relevant data for this rule
        relevant_data = {}
        for field in rule['fields']:
            if field in cross_scan_data:
                relevant_data[field] = cross_scan_data[field]
        
        if not relevant_data:
            return results
        
        # Apply rule-specific logic
        if rule_id == 'cross_scan_shared_infrastructure':
            results = self._find_shared_infrastructure(relevant_data)
        elif rule_id == 'cross_scan_similar_technologies':
            results = self._find_similar_technologies(relevant_data)
        elif rule_id == 'cross_scan_threat_indicators':
            results = self._find_shared_threats(relevant_data)
        
        # Add rule metadata to results
        for result in results:
            result['rule_id'] = rule_id
            result['rule_name'] = rule['name']
            result['rule_description'] = rule['description']
        
        return results
    
    def _find_shared_infrastructure(self, data: Dict[str, List[dict]]) -> List[dict]:
        """Find shared infrastructure across scans."""
        results = []
        
        # Group by data value across different scans
        for data_type, events in data.items():
            value_to_scans = {}
            
            for event in events:
                value = event['data']
                scan_id = event['scan_id']
                
                if value not in value_to_scans:
                    value_to_scans[value] = set()
                value_to_scans[value].add(scan_id)
            
            # Find values shared across multiple scans
            for value, scan_set in value_to_scans.items():
                if len(scan_set) > 1:  # Shared across at least 2 scans
                    results.append({
                        'type': 'shared_infrastructure',
                        'data_type': data_type,
                        'shared_value': value,
                        'scan_ids': list(scan_set),
                        'scan_count': len(scan_set),
                        'confidence': 85,
                        'risk': 'INFO'
                    })
        
        return results
    
    def _find_similar_technologies(self, data: Dict[str, List[dict]]) -> List[dict]:
        """Find similar technologies across scans."""
        results = []
        
        # This would implement technology pattern matching
        # For now, a simplified version
        for data_type, events in data.items():
            tech_patterns = {}
            
            for event in events:
                scan_id = event['scan_id']
                data_value = event['data'].lower()
                
                # Extract technology patterns (simplified)
                for pattern in ['apache', 'nginx', 'iis', 'php', 'mysql', 'wordpress']:
                    if pattern in data_value:
                        if pattern not in tech_patterns:
                            tech_patterns[pattern] = set()
                        tech_patterns[pattern].add(scan_id)
            
            # Find patterns across multiple scans
            for pattern, scan_set in tech_patterns.items():
                if len(scan_set) > 1:
                    results.append({
                        'type': 'similar_technology',
                        'technology': pattern,
                        'scan_ids': list(scan_set),
                        'scan_count': len(scan_set),
                        'confidence': 75,
                        'risk': 'INFO'
                    })
        
        return results
    
    def _find_shared_threats(self, data: Dict[str, List[dict]]) -> List[dict]:
        """Find shared threat indicators across scans."""
        results = []
        
        # Group threat indicators
        threat_to_scans = {}
        
        for data_type, events in data.items():
            for event in events:
                threat_value = event['data']
                scan_id = event['scan_id']
                
                if threat_value not in threat_to_scans:
                    threat_to_scans[threat_value] = {
                        'scans': set(),
                        'type': data_type,
                        'risk': event.get('risk', 'MEDIUM')
                    }
                threat_to_scans[threat_value]['scans'].add(scan_id)
        
        # Find threats across multiple scans
        for threat_value, threat_info in threat_to_scans.items():
            if len(threat_info['scans']) > 1:
                results.append({
                    'type': 'shared_threat',
                    'threat_value': threat_value,
                    'threat_type': threat_info['type'],
                    'scan_ids': list(threat_info['scans']),
                    'scan_count': len(threat_info['scans']),
                    'confidence': 95,
                    'risk': threat_info['risk']
                })
        
        return results
