"""SpiderFoot Workspace Management.

This module provides workspace functionality for managing multiple scans,
targets, and cross-correlations within a unified context.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from spiderfoot import SpiderFootDb, SpiderFootHelpers, SpiderFootCorrelator


class SpiderFootWorkspace:
    """Manages SpiderFoot workspaces for multi-target, multi-scan operations."""

    def __init__(self, config: dict, workspace_id: str = None, name: str = None):
        """Initialize workspace.
        
        Args:
            config: SpiderFoot configuration
            workspace_id: Existing workspace ID to load
            name: Name for new workspace
        """
        self.config = config
        self.db = SpiderFootDb(config, init=True)
        self.log = logging.getLogger(f"spiderfoot.workspace")
        
        # Ensure workspace table exists before any operations
        self._ensure_workspace_table()
        
        if workspace_id:
            self.workspace_id = workspace_id
            self.load_workspace()
        else:
            self.workspace_id = self._generate_workspace_id()
            self.name = name or f"Workspace_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.created_time = time.time()
            self.modified_time = time.time()
            self.description = ""            
            self.targets = []
            self.scans = []
            self.metadata = {}
            self.correlations = []
            self.workflows = []
            self._create_workspace()

    def _ensure_workspace_table(self) -> None:
        """Ensure workspace table exists in database."""
        try:
            with self.db.dbhLock:
                # Create workspace table if it doesn't exist
                self.db.dbh.execute("""
                    CREATE TABLE IF NOT EXISTS tbl_workspaces (
                        workspace_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        created_time REAL,
                        modified_time REAL,
                        targets TEXT,
                        scans TEXT,
                        metadata TEXT,
                        correlations TEXT,
                        workflows TEXT
                    )
                """)
                
                # Check if we need to add missing columns for existing tables
                self.db.dbh.execute("PRAGMA table_info(tbl_workspaces)")
                columns = [col[1] for col in self.db.dbh.fetchall()]
                
                if 'correlations' not in columns:
                    self.db.dbh.execute("ALTER TABLE tbl_workspaces ADD COLUMN correlations TEXT")
                if 'workflows' not in columns:
                    self.db.dbh.execute("ALTER TABLE tbl_workspaces ADD COLUMN workflows TEXT")
                
                self.db.conn.commit()
                
        except Exception as e:
            self.log.error(f"Failed to ensure workspace table: {e}")
            raise

    def _generate_workspace_id(self) -> str:
        """Generate unique workspace ID."""
        return f"ws_{uuid.uuid4().hex[:12]}"

    def _create_workspace(self) -> None:
        """Create workspace in database."""
        try:
            workspace_data = {
                'workspace_id': self.workspace_id,
                'name': self.name,
                'description': self.description,
                'created_time': self.created_time,
                'modified_time': self.modified_time,
                'targets': json.dumps(self.targets),
                'scans': json.dumps(self.scans),
                'metadata': json.dumps(self.metadata),
                'correlations': json.dumps(self.correlations),
                'workflows': json.dumps(self.workflows)
            }
              # Create workspace table if it doesn't exist
            with self.db.dbhLock:
                try:
                    # Try to create the table with new schema
                    self.db.dbh.execute("""
                        CREATE TABLE IF NOT EXISTS tbl_workspaces (
                            workspace_id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            description TEXT,
                            created_time REAL,
                            modified_time REAL,
                            targets TEXT,
                            scans TEXT,
                            metadata TEXT,
                            correlations TEXT,
                            workflows TEXT
                        )
                    """)
                    
                    # Check if we need to add missing columns for existing tables
                    self.db.dbh.execute("PRAGMA table_info(tbl_workspaces)")
                    columns = [col[1] for col in self.db.dbh.fetchall()]
                    
                    if 'correlations' not in columns:
                        self.db.dbh.execute("ALTER TABLE tbl_workspaces ADD COLUMN correlations TEXT")
                    if 'workflows' not in columns:
                        self.db.dbh.execute("ALTER TABLE tbl_workspaces ADD COLUMN workflows TEXT")
                    
                    # Insert workspace
                    query = """
                        INSERT INTO tbl_workspaces 
                        (workspace_id, name, description, created_time, modified_time, targets, scans, metadata, correlations, workflows)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    self.db.dbh.execute(query, list(workspace_data.values()))
                    self.db.conn.commit()
                    
                except Exception as e:
                    self.log.error(f"Failed to create workspace table/data: {e}")
                    raise
            
            self.log.info(f"Created workspace {self.workspace_id}: {self.name}")
            
        except Exception as e:
            self.log.error(f"Failed to create workspace: {e}")
            raise

    def load_workspace(self) -> None:
        """Load workspace from database."""
        try:
            query = "SELECT * FROM tbl_workspaces WHERE workspace_id = ?"
            
            with self.db.dbhLock:
                self.db.dbh.execute(query, [self.workspace_id])
                result = self.db.dbh.fetchone()
            
            if not result:
                raise ValueError(f"Workspace {self.workspace_id} not found")
            
            workspace_data = result
            self.name = workspace_data[1]
            self.description = workspace_data[2] or ""
            self.created_time = workspace_data[3]
            self.modified_time = workspace_data[4]
            self.targets = json.loads(workspace_data[5] or "[]")
            self.scans = json.loads(workspace_data[6] or "[]")
            self.metadata = json.loads(workspace_data[7] or "{}")
            
            self.log.info(f"Loaded workspace {self.workspace_id}: {self.name}")
            
        except Exception as e:
            self.log.error(f"Failed to load workspace: {e}")
            raise

    def save_workspace(self) -> None:
        """Save workspace changes to database."""
        try:
            self.modified_time = time.time()
            
            query = """
                UPDATE tbl_workspaces 
                SET name = ?, description = ?, modified_time = ?, 
                    targets = ?, scans = ?, metadata = ?
                WHERE workspace_id = ?
            """
            
            values = [
                self.name, self.description, self.modified_time,
                json.dumps(self.targets), json.dumps(self.scans), 
                json.dumps(self.metadata), self.workspace_id
            ]
            
            with self.db.dbhLock:
                self.db.dbh.execute(query, values)
                self.db.conn.commit()
            self.log.info(f"Saved workspace {self.workspace_id}")
            
        except Exception as e:
            self.log.error(f"Failed to save workspace: {e}")
            raise

    def add_target(self, target: str, target_type: str = None, metadata: dict = None) -> str:
        """Add target to workspace.
        
        Args:
            target: Target value (domain, IP, etc.)
            target_type: Target type (optional, will be auto-detected)
            metadata: Additional target metadata
            
        Returns:
            Target ID
        """
        if not target_type:
            target_type = SpiderFootHelpers.targetTypeFromString(target)
            
        if not target_type:
            raise ValueError(f"Could not determine target type for: {target}")
        
        target_id = f"tgt_{uuid.uuid4().hex[:8]}"
        target_data = {
            'target_id': target_id,
            'value': target,
            'type': target_type,
            'added_time': time.time(),
            'metadata': metadata or {}
        }
        
        self.targets.append(target_data)
        self.save_workspace()
        
        self.log.info(f"Added target {target} ({target_type}) to workspace {self.workspace_id}")
        return target_id

    def add_scan(self, scan_id: str, target_id: str = None, metadata: dict = None) -> None:
        """Add scan to workspace.
        
        Args:
            scan_id: SpiderFoot scan ID
            target_id: Associated target ID (optional)
            metadata: Additional scan metadata
        """
        # Verify scan exists
        scan_info = self.db.scanInstanceGet(scan_id)
        if not scan_info:
            raise ValueError(f"Scan {scan_id} not found")
        
        scan_data = {
            'scan_id': scan_id,
            'target_id': target_id,
            'added_time': time.time(),
            'scan_name': scan_info[1],
            'scan_target': scan_info[2],
            'metadata': metadata or {}
        }
        
        self.scans.append(scan_data)
        self.save_workspace()
        
        self.log.info(f"Added scan {scan_id} to workspace {self.workspace_id}")

    def import_single_scan(self, scan_id: str, metadata: dict = None) -> bool:
        """Import an existing single scan into the workspace.
        
        Args:
            scan_id: SpiderFoot scan ID to import
            metadata: Additional metadata for the imported scan
            
        Returns:
            True if import was successful
        """
        try:
            # Verify scan exists
            scan_info = self.db.scanInstanceGet(scan_id)
            if not scan_info:
                raise ValueError(f"Scan {scan_id} not found")
            
            # Check if scan is already in workspace
            existing_scan = next((s for s in self.scans if s['scan_id'] == scan_id), None)
            if existing_scan:
                self.log.warning(f"Scan {scan_id} already exists in workspace")
                return False            # Extract target information from scan
            # scanInstanceGet returns: [name, seed_target, created, started, ended, status]
            if len(scan_info) < 6:
                raise ValueError(f"Scan info for {scan_id} is incomplete: {scan_info}")
                
            target_value = scan_info[1]  # seed_target is at index 1
            target_type = None
            
            # Ensure target_value is a string and not None
            if target_value is None:
                raise ValueError(f"Scan {scan_id} has no target value")
            target_value = str(target_value).strip()
            
            if not target_value:
                raise ValueError(f"Scan {scan_id} has empty target value")
            
            # Try to determine target type
            from spiderfoot import SpiderFootHelpers
            target_type = SpiderFootHelpers.targetTypeFromString(target_value)
            
            # Add target to workspace if not exists
            target_id = None
            existing_target = next((t for t in self.targets if t['value'] == target_value), None)
            if not existing_target:
                target_id = self.add_target(target_value, target_type, {'imported_with_scan': scan_id})
            else:
                target_id = existing_target['target_id']
            
            # Import scan
            import_metadata = metadata or {}
            import_metadata.update({
                'imported_time': time.time(),
                'import_source': 'single_scan_import',
                'original_scan_target': target_value
            })
            
            self.add_scan(scan_id, target_id, import_metadata)
            
            self.log.info(f"Successfully imported scan {scan_id} into workspace {self.workspace_id}")
            return True
            
        except Exception as e:
            self.log.error(f"Failed to import scan {scan_id}: {e}")
            return False

    def bulk_import_scans(self, scan_ids: List[str], metadata: dict = None) -> Dict[str, bool]:
        """Import multiple scans into the workspace.
        
        Args:
            scan_ids: List of scan IDs to import
            metadata: Additional metadata for imported scans
            
        Returns:
            Dictionary mapping scan_id to import success status
        """
        results = {}
        
        for scan_id in scan_ids:
            try:
                success = self.import_single_scan(scan_id, metadata)
                results[scan_id] = success
            except Exception as e:
                self.log.error(f"Failed to import scan {scan_id}: {e}")
                results[scan_id] = False
        
        return results

    def get_targets(self) -> List[dict]:
        """Get all targets in workspace."""
        return self.targets.copy()

    def get_scans(self) -> List[dict]:
        """Get all scans in workspace."""
        return self.scans.copy()

    def get_scan_ids(self) -> List[str]:
        """Get list of scan IDs in workspace."""
        return [scan['scan_id'] for scan in self.scans]

    def remove_target(self, target_id: str) -> bool:
        """Remove target from workspace.
        
        Args:
            target_id: Target ID to remove
            
        Returns:
            True if target was removed
        """
        original_count = len(self.targets)
        self.targets = [t for t in self.targets if t['target_id'] != target_id]
        
        if len(self.targets) < original_count:
            # Also remove associated scans
            self.scans = [s for s in self.scans if s.get('target_id') != target_id]
            self.save_workspace()
            self.log.info(f"Removed target {target_id} from workspace {self.workspace_id}")
            return True
        
        return False

    def remove_scan(self, scan_id: str) -> bool:
        """Remove scan from workspace.
        
        Args:
            scan_id: Scan ID to remove
            
        Returns:
            True if scan was removed
        """
        original_count = len(self.scans)
        self.scans = [s for s in self.scans if s['scan_id'] != scan_id]
        
        if len(self.scans) < original_count:
            self.save_workspace()
            self.log.info(f"Removed scan {scan_id} from workspace {self.workspace_id}")
            return True
        
        return False

    def delete_workspace(self) -> None:
        """Delete workspace from database."""
        try:
            query = "DELETE FROM tbl_workspaces WHERE workspace_id = ?"
            with self.db.dbhLock:
                self.db.dbh.execute(query, [self.workspace_id])
                self.db.conn.commit()
            self.log.info(f"Deleted workspace {self.workspace_id}")
            
        except Exception as e:
            self.log.error(f"Failed to delete workspace: {e}")
            raise

    @classmethod
    def list_workspaces(cls, config: dict) -> List[dict]:
        """List all workspaces.
        
        Args:
            config: SpiderFoot configuration
            
        Returns:
            List of workspace summaries
        """
        db = SpiderFootDb(config)
        
        try:            # Ensure table exists
            with db.dbhLock:
                db.dbh.execute("""
                    CREATE TABLE IF NOT EXISTS tbl_workspaces (
                        workspace_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        created_time REAL,
                        modified_time REAL,
                        targets TEXT,
                        scans TEXT,
                        metadata TEXT,
                        correlations TEXT,
                        workflows TEXT
                    )
                """)
                
                # Check if we need to add missing columns for existing tables
                db.dbh.execute("PRAGMA table_info(tbl_workspaces)")
                columns = [col[1] for col in db.dbh.fetchall()]
                
                if 'correlations' not in columns:
                    db.dbh.execute("ALTER TABLE tbl_workspaces ADD COLUMN correlations TEXT")
                if 'workflows' not in columns:
                    db.dbh.execute("ALTER TABLE tbl_workspaces ADD COLUMN workflows TEXT")
                
                db.conn.commit()
            
            query = """
                SELECT workspace_id, name, description, created_time, 
                       modified_time, targets, scans 
                FROM tbl_workspaces 
                ORDER BY modified_time DESC
            """
            
            with db.dbhLock:
                db.dbh.execute(query)
                results = db.dbh.fetchall()
            
            workspaces = []
            for row in results:
                targets = json.loads(row[5] or "[]")
                scans = json.loads(row[6] or "[]")
                
                workspaces.append({
                    'workspace_id': row[0],
                    'name': row[1],
                    'description': row[2] or "",
                    'created_time': row[3],
                    'modified_time': row[4],
                    'target_count': len(targets),
                    'scan_count': len(scans)
                })
            
            return workspaces
            
        except Exception as e:
            logging.getLogger("spiderfoot.workspace").error(f"Failed to list workspaces: {e}")
            return []

    def export_data(self, format: str = 'json') -> dict:
        """Export workspace data.
        
        Args:
            format: Export format ('json', 'csv')
            
        Returns:
            Exported data
        """
        export_data = {
            'workspace_info': {
                'workspace_id': self.workspace_id,
                'name': self.name,
                'description': self.description,
                'created_time': self.created_time,
                'modified_time': self.modified_time,
                'metadata': self.metadata
            },
            'targets': self.targets,
            'scans': [],
            'scan_results': {}
        }
        
        # Export scan data
        for scan in self.scans:
            scan_id = scan['scan_id']
            scan_info = self.db.scanInstanceGet(scan_id)
            
            if scan_info:
                scan_data = {
                    'scan_id': scan_id,
                    'name': scan_info[1],
                    'target': scan_info[2],
                    'status': scan_info[5],
                    'created': scan_info[3],
                    'started': scan_info[4],
                    'ended': scan_info[6] if len(scan_info) > 6 else None,
                    'workspace_metadata': scan.get('metadata', {})
                }
                export_data['scans'].append(scan_data)
                
                # Get scan results
                results = self.db.scanResultEvent(scan_id, 'ALL')
                export_data['scan_results'][scan_id] = [
                    {
                        'created': result[0],
                        'data': result[1],
                        'module': result[3],
                        'type': result[4],
                        'confidence': result[6],
                        'visibility': result[7],
                        'risk': result[8]
                    } for result in results
                ]
        
        return export_data

    def get_workspace_summary(self) -> Dict[str, Any]:
        """Get comprehensive workspace summary.
        
        Returns:
            Workspace summary with statistics
        """
        summary = {
            'workspace_info': {
                'workspace_id': self.workspace_id,
                'name': self.name,
                'description': self.description,
                'created_time': self.created_time,
                'modified_time': self.modified_time
            },
            'statistics': {
                'target_count': len(self.targets),
                'scan_count': len(self.scans),
                'total_events': 0,
                'completed_scans': 0,
                'running_scans': 0,
                'failed_scans': 0,
                'correlation_count': len(self.metadata.get('correlations', [])),
                'cti_report_count': len(self.metadata.get('cti_reports', []))
            },
            'targets_by_type': {},
            'scans_by_status': {},
            'recent_activity': []
        }
        
        # Analyze targets
        for target in self.targets:
            target_type = target['type']
            if target_type not in summary['targets_by_type']:
                summary['targets_by_type'][target_type] = 0
            summary['targets_by_type'][target_type] += 1
        
        # Analyze scans
        for scan in self.scans:
            scan_id = scan['scan_id']
            scan_info = self.db.scanInstanceGet(scan_id)
            
            if scan_info:
                status = scan_info[5]
                if status not in summary['scans_by_status']:
                    summary['scans_by_status'][status] = 0
                summary['scans_by_status'][status] += 1
                
                # Count statistics
                if status == 'FINISHED':
                    summary['statistics']['completed_scans'] += 1
                elif status == 'RUNNING':
                    summary['statistics']['running_scans'] += 1
                elif status in ['ERROR-FAILED', 'ABORTED']:
                    summary['statistics']['failed_scans'] += 1
                
                # Count events
                events = self.db.scanResultEvent(scan_id, 'ALL')
                summary['statistics']['total_events'] += len(events)
                
                # Recent activity
                summary['recent_activity'].append({
                    'type': 'scan',
                    'scan_id': scan_id,
                    'target': scan_info[2],
                    'status': status,
                    'time': scan.get('added_time', 0)
                })
        
        # Sort recent activity by time
        summary['recent_activity'].sort(key=lambda x: x['time'], reverse=True)
        summary['recent_activity'] = summary['recent_activity'][:10]  # Keep last 10
        
        return summary

    def search_events(self, query: str, event_types: List[str] = None, 
                     scan_ids: List[str] = None) -> List[dict]:
        """Search events across workspace scans.
        
        Args:
            query: Search query string
            event_types: Filter by specific event types
            scan_ids: Filter by specific scan IDs
            
        Returns:
            List of matching events
        """
        matching_events = []
        
        target_scan_ids = scan_ids or self.get_scan_ids()
        
        for scan_id in target_scan_ids:
            events = self.db.scanResultEvent(scan_id, event_types or 'ALL')
            
            for event in events:
                event_data = event[1]  # event data
                event_type = event[4]  # event type
                
                # Simple text search in event data
                if query.lower() in event_data.lower():
                    matching_events.append({
                        'scan_id': scan_id,
                        'created': event[0],
                        'data': event_data,
                        'module': event[3],
                        'type': event_type,
                        'confidence': event[6],
                        'visibility': event[7],
                        'risk': event[8]
                    })
        
        return matching_events    # def create_workflow(self):
    #     """Create a new workflow for this workspace.
    #     
    #     Returns:
    #         SpiderFootWorkflow instance
    #     """
    #     from spiderfoot.workflow import SpiderFootWorkflow
    #     return SpiderFootWorkflow(self.config, self)

    async def generate_cti_report(self, report_type: str = 'threat_assessment', 
                                 custom_prompt: str = None) -> Dict[str, Any]:
        """Generate CTI report using MCP integration.
        
        Args:
            report_type: Type of report to generate
            custom_prompt: Custom prompt for report generation
            
        Returns:
            Generated CTI report
        """
        from spiderfoot.mcp_integration import SpiderFootMCPClient
        
        mcp_client = SpiderFootMCPClient(self.config)
        return await mcp_client.generate_cti_report(self, report_type, custom_prompt)

    def clone_workspace(self, new_name: str = None) -> 'SpiderFootWorkspace':
        """Clone workspace with all targets but no scans.
        
        Args:
            new_name: Name for cloned workspace
            
        Returns:
            New workspace instance
        """
        clone_name = new_name or f"{self.name}_clone_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create new workspace
        cloned_workspace = SpiderFootWorkspace(self.config, name=clone_name)
        cloned_workspace.description = f"Clone of {self.name}"
        
        # Copy targets
        for target in self.targets:
            cloned_workspace.add_target(
                target['value'], 
                target['type'], 
                target.get('metadata', {})
            )
        
        # Copy metadata (except scans and reports)
        cloned_metadata = self.metadata.copy()
        cloned_metadata.pop('correlations', None)
        cloned_metadata.pop('cti_reports', None)
        
        # Remove any scan-specific metadata
        for key in list(cloned_metadata.keys()):
            if key.startswith('cti_report_'):
                cloned_metadata.pop(key)
        
        cloned_workspace.metadata = cloned_metadata
        cloned_workspace.save_workspace()
        
        self.log.info(f"Cloned workspace {self.workspace_id} to {cloned_workspace.workspace_id}")
        return cloned_workspace

    def merge_workspace(self, other_workspace: 'SpiderFootWorkspace') -> bool:
        """Merge another workspace into this one.
        
        Args:
            other_workspace: Workspace to merge
            
        Returns:
            True if merge was successful
        """
        try:
            # Merge targets (avoid duplicates)
            for target in other_workspace.targets:
                existing = next((t for t in self.targets if t['value'] == target['value']), None)
                if not existing:
                    self.add_target(target['value'], target['type'], target.get('metadata', {}))
            
            # Merge scans
            for scan in other_workspace.scans:
                scan_id = scan['scan_id']
                # Check if scan already exists
                existing = next((s for s in self.scans if s['scan_id'] == scan_id), None)
                if not existing:
                    self.add_scan(scan_id, scan.get('target_id'), scan.get('metadata', {}))
            
            # Merge metadata
            for key, value in other_workspace.metadata.items():
                if key not in self.metadata:
                    self.metadata[key] = value
                elif isinstance(value, list) and isinstance(self.metadata[key], list):
                    self.metadata[key].extend(value)
            
            self.save_workspace()
            self.log.info(f"Successfully merged workspace {other_workspace.workspace_id} into {self.workspace_id}")
            return True
            
        except Exception as e:
            self.log.error(f"Failed to merge workspace: {e}")
            return False

    def update_workspace_metadata(self, workspace_id: str, metadata_updates: dict) -> bool:
        """Update workspace metadata.
        
        Args:
            workspace_id: Workspace ID
            metadata_updates: Dictionary of metadata updates to apply
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            workspace = self.get_workspace(workspace_id)
            if not workspace:
                return False
                
            # Load the workspace object
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            
            # Update metadata
            ws.metadata.update(metadata_updates)
            
            # Save changes
            ws.save_workspace()
            
            return True
            
        except Exception as e:
            self.log.error(f"Failed to update workspace metadata: {e}")
            return False
