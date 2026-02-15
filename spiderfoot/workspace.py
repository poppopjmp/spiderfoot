"""SpiderFoot Workspace Management.

This module provides workspace functionality for managing multiple scans,
targets, and cross-correlations within a unified context.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from spiderfoot import SpiderFootDb, SpiderFootHelpers
from spiderfoot.db.db_utils import get_placeholder


class SpiderFootWorkspace:
    """Manages SpiderFoot workspaces for multi-target, multi-scan operations."""

    def __init__(self, config: dict, workspace_id: str = None, name: str = None, scan_db=None) -> None:
        """Initialize workspace.

        Args:
            config: SpiderFoot configuration
            workspace_id: Existing workspace ID to load
            name: Name for new workspace
            scan_db: Optional DB handle for scan operations (e.g. ApiClient in proxy mode).
                     If not provided, falls back to self.db (direct SQLite).
        """
        self.config = config
        self.db = SpiderFootDb(config, init=True)
        # scan_db is used for scan-related queries (scanInstanceGet, etc.)
        # In API proxy mode (webui), this should be the ApiClient so scan
        # data is fetched from the FastAPI backend rather than the local SQLite.
        self._scan_db = scan_db
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
                self._add_missing_columns(self.db)

                self.db.conn.commit()

        except Exception as e:
            self.log.error("Failed to ensure workspace table: %s", e)
            raise

    @staticmethod
    def _add_missing_columns(db) -> None:
        """Add missing columns to workspace table (works with both SQLite and PostgreSQL)."""
        db_type = getattr(db, 'db_type', 'sqlite')
        if db_type == 'postgresql':
            # PostgreSQL: query information_schema
            db.dbh.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'tbl_workspaces'
            """)
        else:
            # SQLite: use PRAGMA
            db.dbh.execute("PRAGMA table_info(tbl_workspaces)")
        raw_cols = db.dbh.fetchall()
        if db_type == 'postgresql':
            columns = [col[0] for col in raw_cols]
        else:
            columns = [col[1] for col in raw_cols]

        if 'correlations' not in columns:
            db.dbh.execute("ALTER TABLE tbl_workspaces ADD COLUMN correlations TEXT")
        if 'workflows' not in columns:
            db.dbh.execute("ALTER TABLE tbl_workspaces ADD COLUMN workflows TEXT")

    @property
    def scan_db(self):
        """DB handle for scan-related queries.

        Returns the injected scan_db (ApiClient in proxy mode) if available,
        otherwise falls back to self.db (direct SQLite).
        """
        return self._scan_db if self._scan_db is not None else self.db

    def _get_scan_row(self, scan_id: str):
        """Get a single scan info row, normalizing across DB and ApiClient.

        SpiderFootDb.scanInstanceGet returns a single row (DictRow or tuple):
            (guid, name, seed_target, created, started, ended, status, result_count)
        ApiClient.scanInstanceGet returns a single tuple:
            (name, target, created, started, ended, status)

        This method always returns a normalized 6-element tuple:
            (name, seed_target, created, started, ended, status)
        or None.
        """
        result = self.scan_db.scanInstanceGet(scan_id)
        if not result:
            return None

        row = result

        # DictRow (psycopg2) extends list, so don't unwrap via isinstance(list).
        # Instead, check if it's a nested list-of-rows (plain list of tuples).
        if isinstance(result, list) and not hasattr(result, 'keys'):
            # Plain list (e.g. raw fetchall result not yet unwrapped)
            if len(result) == 0:
                return None
            row = result[0]

        # Convert DictRow / namedtuple to plain tuple for safe indexing
        if hasattr(row, 'keys'):
            row = tuple(row)

        # Normalize: SpiderFootDb returns 8 cols starting with guid;
        # strip guid prefix and result_count suffix → 6-element tuple
        if len(row) >= 8 and str(row[0]) == scan_id:
            # (guid, name, seed_target, created, started, ended, status, result_count)
            row = tuple(row[1:7])  # → (name, seed_target, created, started, ended, status)

        return row

    def _generate_workspace_id(self) -> str:
        """Generate unique workspace ID."""
        return f"ws_{uuid.uuid4().hex[:12]}"

    def _create_workspace(self) -> None:
        """Create workspace in database."""
        try:
            ph = get_placeholder(getattr(self.db, 'db_type', 'sqlite'))
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

            with self.db.dbhLock:
                try:
                    # Table should already exist via _ensure_workspace_table
                    self._add_missing_columns(self.db)

                    # Insert workspace
                    placeholders = ', '.join([ph] * 10)
                    query = f"""
                        INSERT INTO tbl_workspaces
                        (workspace_id, name, description, created_time, modified_time, targets, scans, metadata, correlations, workflows)
                        VALUES ({placeholders})
                    """
                    self.db.dbh.execute(query, list(workspace_data.values()))
                    self.db.conn.commit()

                except Exception as e:
                    self.log.error("Failed to create workspace table/data: %s", e)
                    raise

            self.log.info("Created workspace %s: %s", self.workspace_id, self.name)

        except Exception as e:
            self.log.error("Failed to create workspace: %s", e)
            raise

    def load_workspace(self) -> None:
        """Load workspace from database."""
        try:
            ph = get_placeholder(getattr(self.db, 'db_type', 'sqlite'))
            query = f"SELECT * FROM tbl_workspaces WHERE workspace_id = {ph}"

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
            self.correlations = json.loads(workspace_data[8] or "[]") if len(workspace_data) > 8 else []
            self.workflows = json.loads(workspace_data[9] or "[]") if len(workspace_data) > 9 else []

            self.log.info("Loaded workspace %s: %s", self.workspace_id, self.name)

        except Exception as e:
            self.log.error("Failed to load workspace: %s", e)
            raise

    def save_workspace(self) -> None:
        """Save workspace changes to database."""
        try:
            self.modified_time = time.time()
            ph = get_placeholder(getattr(self.db, 'db_type', 'sqlite'))

            query = f"""
                UPDATE tbl_workspaces
                SET name = {ph}, description = {ph}, modified_time = {ph},
                    targets = {ph}, scans = {ph}, metadata = {ph},
                    correlations = {ph}, workflows = {ph}
                WHERE workspace_id = {ph}
            """

            values = [
                self.name, self.description, self.modified_time,
                json.dumps(self.targets), json.dumps(self.scans),
                json.dumps(self.metadata),
                json.dumps(getattr(self, 'correlations', [])),
                json.dumps(getattr(self, 'workflows', [])),
                self.workspace_id
            ]

            with self.db.dbhLock:
                self.db.dbh.execute(query, values)
                self.db.conn.commit()
            self.log.info("Saved workspace %s", self.workspace_id)

        except Exception as e:
            self.log.error("Failed to save workspace: %s", e)
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

        self.log.info("Added target %s (%s) to workspace %s", target, target_type, self.workspace_id)
        return target_id

    def add_scan(self, scan_id: str, target_id: str = None, metadata: dict = None) -> None:
        """Add scan to workspace.

        Args:
            scan_id: SpiderFoot scan ID
            target_id: Associated target ID (optional)
            metadata: Additional scan metadata
        """
        # Verify scan exists — normalize across DB and ApiClient
        row = self._get_scan_row(scan_id)
        if not row:
            raise ValueError(f"Scan {scan_id} not found")

        # Row format: (name, seed_target, created, started, ended, status)
        scan_data = {
            'scan_id': scan_id,
            'target_id': target_id,
            'added_time': time.time(),
            'name': row[0] if len(row) > 0 else '',
            'target': row[1] if len(row) > 1 else '',
            'status': row[5] if len(row) > 5 else 'UNKNOWN',
            'created': row[2] if len(row) > 2 else 0,
            'metadata': metadata or {}
        }

        self.scans.append(scan_data)
        self.save_workspace()

        self.log.info("Added scan %s to workspace %s", scan_id, self.workspace_id)

    def import_single_scan(self, scan_id: str, metadata: dict = None) -> bool:
        """Import an existing single scan into the workspace.

        Args:
            scan_id: SpiderFoot scan ID to import
            metadata: Additional metadata for the imported scan

        Returns:
            True if import was successful
        """
        try:
            # Verify scan exists — normalize across DB and ApiClient
            row = self._get_scan_row(scan_id)
            if not row:
                raise ValueError(f"Scan {scan_id} not found")

            # Check if scan is already in workspace
            existing_scan = next((s for s in self.scans if s['scan_id'] == scan_id), None)
            if existing_scan:
                self.log.warning("Scan %s already exists in workspace", scan_id)
                return False

            # Row format: (name, seed_target, created, started, ended, status)
            if len(row) < 6:
                raise ValueError(f"Scan info for {scan_id} is incomplete: {row}")

            target_value = row[1]  # seed_target is at index 1
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

            self.log.info("Successfully imported scan %s into workspace %s", scan_id, self.workspace_id)
            return True

        except Exception as e:
            self.log.error("Failed to import scan %s: %s", scan_id, e)
            return False

    def bulk_import_scans(self, scan_ids: list[str], metadata: dict = None) -> dict[str, bool]:
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
                self.log.error("Failed to import scan %s: %s", scan_id, e)
                results[scan_id] = False

        return results

    def get_targets(self) -> list[dict]:
        """Get all targets in workspace."""
        return self.targets.copy()

    def get_scans(self) -> list[dict]:
        """Get all scans in workspace."""
        return self.scans.copy()

    def get_scan_ids(self) -> list[str]:
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
            self.log.info("Removed target %s from workspace %s", target_id, self.workspace_id)
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
            self.log.info("Removed scan %s from workspace %s", scan_id, self.workspace_id)
            return True

        return False

    def delete_workspace(self) -> None:
        """Delete workspace from database."""
        try:
            ph = get_placeholder(getattr(self.db, 'db_type', 'sqlite'))
            query = f"DELETE FROM tbl_workspaces WHERE workspace_id = {ph}"
            with self.db.dbhLock:
                self.db.dbh.execute(query, [self.workspace_id])
                self.db.conn.commit()
            self.log.info("Deleted workspace %s", self.workspace_id)

        except Exception as e:
            self.log.error("Failed to delete workspace: %s", e)
            raise

    @classmethod
    def list_workspaces(cls, config: dict) -> list[dict]:
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
                cls._add_missing_columns(db)

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
            scan_info = self._get_scan_row(scan_id)

            if scan_info:
                # Row: (name, seed_target, created, started, ended, status)
                scan_data = {
                    'scan_id': scan_id,
                    'name': scan_info[0],
                    'target': scan_info[1],
                    'status': scan_info[5],
                    'created': scan_info[2],
                    'started': scan_info[3],
                    'ended': scan_info[4],
                    'workspace_metadata': scan.get('metadata', {})
                }
                export_data['scans'].append(scan_data)

                # Get scan results
                results = self.scan_db.scanResultEvent(scan_id, 'ALL')
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

    def get_workspace_summary(self) -> dict[str, Any]:
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
                'correlation_count': 0,
                'critical_count': 0,
                'high_count': 0,
                'medium_count': 0,
                'low_count': 0,
                'info_count': 0,
                'cti_report_count': len(self.metadata.get('cti_reports', []))
            },
            'targets_by_type': {},
            'scans_by_status': {},
            'recent_activity': [],
            'correlations': [],
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
            scan_info = self._get_scan_row(scan_id)

            if scan_info:
                # Row: (name, seed_target, created, started, ended, status)
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
                events = self.scan_db.scanResultEvent(scan_id, 'ALL')
                summary['statistics']['total_events'] += len(events)

                # Aggregate correlations from this scan
                try:
                    corr_by_risk = self.scan_db.scanCorrelationSummary(scan_id, by='risk')
                    for row in (corr_by_risk or []):
                        risk = str(row[0]).upper() if row[0] else 'INFO'
                        count = int(row[1]) if row[1] else 0
                        summary['statistics']['correlation_count'] += count
                        if risk == 'CRITICAL':
                            summary['statistics']['critical_count'] += count
                        elif risk == 'HIGH':
                            summary['statistics']['high_count'] += count
                        elif risk == 'MEDIUM':
                            summary['statistics']['medium_count'] += count
                        elif risk == 'LOW':
                            summary['statistics']['low_count'] += count
                        else:
                            summary['statistics']['info_count'] += count

                    corr_list = self.scan_db.scanCorrelationList(scan_id)
                    for row in (corr_list or []):
                        summary['correlations'].append({
                            'id': row[0],
                            'title': row[1],
                            'rule_id': row[2],
                            'rule_risk': row[3],
                            'rule_name': row[4],
                            'scan_id': scan_id,
                            'event_count': row[7] if len(row) > 7 else 0,
                        })
                except Exception as e:
                    self.log.debug("Could not aggregate correlations for scan %s: %s", scan_id, e)

                # Recent activity
                summary['recent_activity'].append({
                    'type': 'scan',
                    'scan_id': scan_id,
                    'target': scan_info[1],
                    'status': status,
                    'time': scan.get('added_time', 0)
                })

        # Sort recent activity by time
        summary['recent_activity'].sort(key=lambda x: x['time'], reverse=True)
        summary['recent_activity'] = summary['recent_activity'][:10]  # Keep last 10

        return summary

    def search_events(self, query: str, event_types: list[str] = None,
                     scan_ids: list[str] = None) -> list[dict]:
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
            events = self.scan_db.scanResultEvent(scan_id, event_types or 'ALL')

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

        return matching_events

    async def generate_cti_report(self, report_type: str = 'threat_assessment',
                                 custom_prompt: str = None) -> dict[str, Any]:
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

        self.log.info("Cloned workspace %s to %s", self.workspace_id, cloned_workspace.workspace_id)
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
            self.log.info("Successfully merged workspace %s into %s", other_workspace.workspace_id, self.workspace_id)
            return True

        except Exception as e:
            self.log.error("Failed to merge workspace: %s", e)
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
            self.log.error("Failed to update workspace metadata: %s", e)
            return False

    def start_multiscan(
        self,
        target_list: list[str],
        module_list: list[str],
        scan_name_prefix: str,
        enable_correlation: str | bool = False,
    ) -> list[dict]:
        """Launch scans against multiple targets in the workspace.

        Args:
            target_list: List of targets to scan.
            module_list: List of module names to use.
            scan_name_prefix: Prefix for generated scan names.
            enable_correlation: Whether to run correlations after all scans.

        Returns:
            List of dicts with scan_id and target for each launched scan.
        """
        results: list[dict] = []

        if not target_list:
            raise ValueError("No targets provided for multi-scan")
        if not module_list:
            raise ValueError("No modules provided for multi-scan")

        # Ensure sfp__stor_db is included
        if "sfp__stor_db" not in module_list:
            module_list.append("sfp__stor_db")

        for target in target_list:
            target = target.strip()
            if not target:
                continue

            target_type = SpiderFootHelpers.targetTypeFromString(target)
            if target_type is None:
                self.log.warning("Skipping invalid target: %s", target)
                results.append({"target": target, "error": "Invalid target type"})
                continue

            scan_name = f"{scan_name_prefix}_{target}"
            scan_id = SpiderFootHelpers.genScanInstanceId()

            try:
                # If using API proxy, delegate to API
                if hasattr(self.scan_db, 'startScan'):
                    resp = self.scan_db.startScan(
                        scan_name=scan_name,
                        target=target,
                        modules=module_list,
                    )
                    scan_id = resp.get("id", scan_id)
                else:
                    # Direct mode — create scan instance and start scanner
                    self.scan_db.scanInstanceCreate(scan_id, scan_name, target)
                    from spiderfoot import SpiderFoot
                    cfg = self.config.copy()
                    import multiprocessing as mp
                    from sflib import startSpiderFootScanner
                    lq = mp.Queue()
                    startSpiderFootScanner(
                        lq, scan_name, scan_id, target, target_type,
                        sorted(module_list), cfg,
                    )

                # Add target + scan to workspace
                existing_target = next(
                    (t for t in self.targets if t['value'] == target), None
                )
                if not existing_target:
                    target_id = self.add_target(target, target_type)
                else:
                    target_id = existing_target['target_id']

                self.add_scan(scan_id, target_id, {
                    'launched_via': 'multiscan',
                    'scan_name_prefix': scan_name_prefix,
                })

                results.append({
                    "target": target,
                    "scan_id": scan_id,
                    "scan_name": scan_name,
                    "status": "started",
                })
                self.log.info(
                    "Multi-scan started scan %s for target %s",
                    scan_id, target,
                )

            except Exception as e:
                self.log.error("Failed to start scan for target %s: %s", target, e)
                results.append({"target": target, "error": str(e)})

        self.save_workspace()
        return results

    def get_scan_results(
        self,
        scan_id: str | None = None,
        event_type: str | None = None,
        limit: str | int = 100,
    ) -> list[dict]:
        """Retrieve scan results for the workspace.

        Args:
            scan_id: Optional scan ID filter. If None, returns results from all workspace scans.
            event_type: Optional event type filter.
            limit: Maximum number of results.

        Returns:
            List of result dicts.
        """
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 100

        target_scans = [scan_id] if scan_id else self.get_scan_ids()
        all_results: list[dict] = []

        for sid in target_scans:
            try:
                ev_type = event_type or 'ALL'
                events = self.scan_db.scanResultEvent(sid, ev_type)
                for event in (events or []):
                    # scanResultEvent SELECT order:
                    #   0:generated, 1:data, 2:module, 3:hash, 4:type,
                    #   5:source_event_hash, 6:confidence, 7:visibility, 8:risk
                    all_results.append({
                        'scan_id': sid,
                        'created': event[0],
                        'data': event[1],
                        'module': event[2] if len(event) > 2 else '',
                        'hash': event[3] if len(event) > 3 else '',
                        'type': event[4] if len(event) > 4 else '',
                        'source_event_hash': event[5] if len(event) > 5 else '',
                        'confidence': event[6] if len(event) > 6 else 0,
                        'visibility': event[7] if len(event) > 7 else 0,
                        'risk': event[8] if len(event) > 8 else 0,
                    })
                    if len(all_results) >= limit:
                        break
            except Exception as e:
                self.log.warning("Failed to get results for scan %s: %s", sid, e)

            if len(all_results) >= limit:
                break

        return all_results[:limit]

    def get_cross_scan_correlations(self) -> list[dict]:
        """Retrieve cross-scan correlation results for the workspace.

        Returns:
            List of correlation result dicts.
        """
        scan_ids = self.get_scan_ids()
        if not scan_ids:
            return []

        correlations: list[dict] = []

        # Try to query the correlation results table
        try:
            ph = get_placeholder(getattr(self.db, 'db_type', 'sqlite'))
            placeholders = ','.join([ph for _ in scan_ids])
            query = f"""
                SELECT cr.id, cr.scan_instance_id, cr.rule_id, cr.title,
                       cr.rule_risk, cr.rule_name, cr.rule_descr
                FROM tbl_scan_correlation_results cr
                WHERE cr.scan_instance_id IN ({placeholders})
                ORDER BY CASE cr.rule_risk
                    WHEN 'CRITICAL' THEN 5 WHEN 'HIGH' THEN 4
                    WHEN 'MEDIUM' THEN 3 WHEN 'LOW' THEN 2
                    ELSE 1 END DESC
            """
            with self.db.dbhLock:
                self.db.dbh.execute(query, scan_ids)
                rows = self.db.dbh.fetchall()

            for row in (rows or []):
                correlations.append({
                    'id': row[0],
                    'scan_id': row[1],
                    'rule_id': row[2],
                    'title': row[3],
                    'risk': row[4],
                    'rule_name': row[5],
                    'rule_descr': row[6],
                })

        except Exception as e:
            self.log.warning("Could not query correlation results: %s", e)

        # Also include any cached metadata correlations
        stored = self.metadata.get('correlations', [])
        if stored:
            correlations.extend(stored)

        return correlations

    def generate_mcp_report(
        self,
        report_type: str,
        format: str = 'json',
        include_correlations: str | bool = True,
        include_threat_intel: str | bool = True,
        include_recommendations: str | bool = True,
        tlp_level: str = 'amber',
    ) -> dict:
        """Generate an MCP-format intelligence report for the workspace.

        Args:
            report_type: Type of report (e.g. 'threat_assessment', 'executive', 'technical').
            format: Output format ('json', 'pdf', 'html').
            include_correlations: Whether to include correlation findings.
            include_threat_intel: Whether to include threat intelligence data.
            include_recommendations: Whether to include remediation recommendations.
            tlp_level: TLP marking level.

        Returns:
            Dict with report data and download_url.
        """
        inc_corr = str(include_correlations).lower() in ('true', '1', 'yes')
        inc_ti = str(include_threat_intel).lower() in ('true', '1', 'yes')
        inc_rec = str(include_recommendations).lower() in ('true', '1', 'yes')

        report_id = f"rpt_{uuid.uuid4().hex[:12]}"
        summary = self.get_workspace_summary()
        scan_results = self.get_scan_results(limit=500)

        report: dict[str, Any] = {
            'report_id': report_id,
            'report_type': report_type,
            'format': format,
            'tlp_level': tlp_level,
            'workspace_id': self.workspace_id,
            'workspace_name': self.name,
            'generated_at': datetime.utcnow().isoformat(),
            'summary': summary.get('statistics', {}),
            'targets': summary.get('targets_by_type', {}),
            'scans': summary.get('scans_by_status', {}),
        }

        if inc_corr:
            report['correlations'] = self.get_cross_scan_correlations()

        if inc_ti:
            # Gather threat-relevant event types from scan results
            threat_types = [
                'MALICIOUS_IPADDR', 'MALICIOUS_AFFILIATE_IPADDR',
                'MALICIOUS_COHOST', 'BLACKLISTED_IPADDR',
                'BLACKLISTED_AFFILIATE_IPADDR', 'BLACKLISTED_SUBNET',
                'BLACKLISTED_NETBLOCK', 'VULNERABILITY_CVE_CRITICAL',
                'VULNERABILITY_CVE_HIGH',
            ]
            threat_events = [
                r for r in scan_results if r.get('type') in threat_types
            ]
            report['threat_intelligence'] = {
                'event_count': len(threat_events),
                'events': threat_events[:50],
            }

        if inc_rec:
            report['recommendations'] = self._generate_recommendations(scan_results)

        # Store report reference in workspace metadata
        reports = self.metadata.setdefault('mcp_reports', [])
        reports.append({
            'report_id': report_id,
            'report_type': report_type,
            'generated_at': report['generated_at'],
        })
        self.save_workspace()

        return report

    def _generate_recommendations(self, scan_results: list[dict]) -> list[dict]:
        """Generate basic recommendations from scan results."""
        recs: list[dict] = []
        high_risk = [r for r in scan_results if r.get('risk', 0) >= 3]
        if high_risk:
            recs.append({
                'priority': 'HIGH',
                'finding': f"{len(high_risk)} high-risk events detected",
                'recommendation': 'Review and remediate high-risk findings immediately.',
            })
        malicious = [r for r in scan_results if 'MALICIOUS' in str(r.get('type', ''))]
        if malicious:
            recs.append({
                'priority': 'CRITICAL',
                'finding': f"{len(malicious)} malicious indicators found",
                'recommendation': 'Block identified malicious IPs/domains and investigate exposure.',
            })
        return recs

    def update_timing_config(
        self,
        timezone: str | None = None,
        default_start_time: str | None = None,
        retention_period: str | None = None,
        auto_scheduling: str | None = None,
        business_hours_only: str | None = None,
        enable_throttling: str | None = None,
        business_start: str | None = None,
        business_end: str | None = None,
    ) -> dict:
        """Update scan timing and scheduling config for the workspace.

        Returns:
            Updated timing configuration dict.
        """
        timing = self.metadata.setdefault('timing_config', {})

        if timezone is not None:
            timing['timezone'] = timezone
        if default_start_time is not None:
            timing['default_start_time'] = default_start_time
        if retention_period is not None:
            timing['retention_period'] = retention_period
        if auto_scheduling is not None:
            timing['auto_scheduling'] = str(auto_scheduling).lower() in ('true', '1', 'yes')
        if business_hours_only is not None:
            timing['business_hours_only'] = str(business_hours_only).lower() in ('true', '1', 'yes')
        if enable_throttling is not None:
            timing['enable_throttling'] = str(enable_throttling).lower() in ('true', '1', 'yes')
        if business_start is not None:
            timing['business_start'] = business_start
        if business_end is not None:
            timing['business_end'] = business_end

        timing['last_updated'] = time.time()
        self.save_workspace()

        self.log.info("Updated timing config for workspace %s", self.workspace_id)
        return timing
