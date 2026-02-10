"""
Local Data Service implementation.

Wraps the existing SpiderFootDb layer to provide the DataService interface
when running in single-process mode (backward-compatible default).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from spiderfoot.data_service.base import DataService, DataServiceConfig


class LocalDataService(DataService):
    """Data service backed by direct local database access.

    This wraps the existing SpiderFootDb infrastructure (DbCore + managers)
    to provide the DataService interface. Used when running in monolithic
    or single-node mode.
    """

    def __init__(self, config: Optional[DataServiceConfig] = None, db_opts: Optional[dict] = None):
        """Initialize LocalDataService.

        Args:
            config: DataServiceConfig (optional)
            db_opts: Database options dict passed to SpiderFootDb.
                     Must include '__database' and optionally '__dbtype'.
        """
        super().__init__(config)
        self._db_opts = db_opts or {}
        self._dbh = None
        self._initialized = False

    def _ensure_db(self):
        """Lazily initialize the database handle."""
        if self._initialized:
            return

        try:
            from spiderfoot.db import SpiderFootDb
            self._dbh = SpiderFootDb(self._db_opts, init=True)
            self._initialized = True
            self.log.debug("LocalDataService: database initialized")
        except Exception as e:
            self.log.error("Failed to initialize database: %s", e)
            raise

    def set_db_handle(self, dbh):
        """Set an existing database handle directly.

        Useful when integrating with existing code that already
        has a SpiderFootDb instance.

        Args:
            dbh: An existing SpiderFootDb instance
        """
        self._dbh = dbh
        self._initialized = True

    @property
    def dbh(self) -> SpiderFootDb:
        """Get the underlying database handle."""
        self._ensure_db()
        return self._dbh

    # --- Scan Instance Operations ---

    def scan_instance_create(self, scan_id: str, scan_name: str, target: str) -> bool:
        """Create a new scan instance."""
        try:
            self.dbh.scanInstanceCreate(scan_id, scan_name, target)
            return True
        except Exception as e:
            self.log.error("scan_instance_create failed: %s", e)
            return False

    def scan_instance_get(self, scan_id: str) -> Optional[dict[str, Any]]:
        """Get a scan instance by ID."""
        try:
            rows = self.dbh.scanInstanceGet(scan_id)
            if not rows:
                return None

            # scanInstanceGet returns (name, seed_target, created, started, ended, status)
            if isinstance(rows, list) and len(rows) > 0:
                row = rows[0] if isinstance(rows[0], (list, tuple)) else rows
            else:
                row = rows

            return {
                "id": scan_id,
                "name": row[0],
                "target": row[1],
                "created": row[2],
                "started": row[3],
                "ended": row[4],
                "status": row[5],
            }
        except Exception as e:
            self.log.error("scan_instance_get failed: %s", e)
            return None

    def scan_instance_list(self) -> list[dict[str, Any]]:
        """List all scan instances."""
        try:
            rows = self.dbh.scanInstanceList()
            results = []
            for row in rows:
                # (guid, name, seed_target, created, started, ended, status, result_count)
                results.append({
                    "id": row[0],
                    "name": row[1],
                    "target": row[2],
                    "created": row[3],
                    "started": row[4],
                    "ended": row[5],
                    "status": row[6],
                    "result_count": row[7] if len(row) > 7 else 0,
                })
            return results
        except Exception as e:
            self.log.error("scan_instance_list failed: %s", e)
            return []

    def scan_instance_delete(self, scan_id: str) -> bool:
        """Delete a scan instance and all associated data."""
        try:
            self.dbh.scanInstanceDelete(scan_id)
            return True
        except Exception as e:
            self.log.error("scan_instance_delete failed: %s", e)
            return False

    def scan_status_set(self, scan_id: str, status: str,
                        started: Optional[int] = None,
                        ended: Optional[int] = None) -> bool:
        """Update scan status."""
        try:
            self.dbh.scanInstanceSet(
                scan_id,
                started=str(started) if started else None,
                ended=str(ended) if ended else None,
                status=status,
            )
            return True
        except Exception as e:
            self.log.error("scan_status_set failed: %s", e)
            return False

    # --- Event Operations ---

    def event_store(
        self,
        scan_id: str,
        event_hash: str,
        event_type: str,
        module: str,
        data: str,
        source_event_hash: str = "ROOT",
        confidence: int = 100,
        visibility: int = 100,
        risk: int = 0,
    ) -> bool:
        """Store a scan event/result.

        Note: For full SpiderFootEvent integration, callers should use
        scanEventStore() on the underlying dbh. This method provides
        a simplified dict-based interface for new code.
        """
        try:
            # Build a minimal event-like object for the DB layer
            generated = int(time.time() * 1000)

            # Direct insert via the underlying DB, bypassing SpiderFootEvent
            with self.dbh.dbhLock:
                from spiderfoot.db.db_utils import get_placeholder
                ph = get_placeholder(self.dbh.db_type)

                self.dbh.dbh.execute(
                    f"INSERT INTO tbl_scan_results "
                    f"(scan_instance_id, hash, type, module, data, source_event_hash, "
                    f"confidence, visibility, risk, generated, false_positive) "
                    f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                    (scan_id, event_hash, event_type, module, data,
                     source_event_hash, confidence, visibility, risk, generated, 0)
                )
                self.dbh.conn.commit()
            return True
        except Exception as e:
            self.log.error("event_store failed: %s", e)
            return False

    def event_store_obj(self, scan_id: str, sf_event) -> bool:
        """Store a SpiderFootEvent object directly.

        This preserves full compatibility with the existing event system.

        Args:
            scan_id: Scan identifier
            sf_event: A SpiderFootEvent instance

        Returns:
            True if stored
        """
        try:
            self.dbh.scanEventStore(scan_id, sf_event)
            return True
        except Exception as e:
            self.log.error("event_store_obj failed: %s", e)
            return False

    def event_get_by_scan(
        self,
        scan_id: str,
        event_type: Optional[str] = None,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        """Get events for a scan."""
        try:
            et = event_type if event_type else "ALL"
            rows = self.dbh.scanResultEvent(scan_id, eventType=et)

            results = []
            for row in rows:
                # (generated, data, module, hash, type, source_event_hash,
                #  confidence, visibility, risk)
                results.append({
                    "generated": row[0],
                    "data": row[1],
                    "module": row[2],
                    "hash": row[3],
                    "type": row[4],
                    "source_event_hash": row[5],
                    "confidence": row[6],
                    "visibility": row[7],
                    "risk": row[8],
                })

            if limit > 0:
                results = results[:limit]

            return results
        except Exception as e:
            self.log.error("event_get_by_scan failed: %s", e)
            return []

    def event_get_unique(
        self,
        scan_id: str,
        event_type: str,
    ) -> list[str]:
        """Get unique event data values."""
        try:
            rows = self.dbh.scanResultEventUnique(scan_id, eventType=event_type)
            # Returns (data, type, count)
            return [row[0] for row in rows]
        except Exception as e:
            self.log.error("event_get_unique failed: %s", e)
            return []

    def event_exists(
        self,
        scan_id: str,
        event_type: str,
        data: str,
    ) -> bool:
        """Check if an event already exists."""
        try:
            rows = self.dbh.scanResultEvent(
                scan_id, eventType=event_type, data=[data]
            )
            return len(rows) > 0
        except Exception as e:
            self.log.error("event_exists failed: %s", e)
            return False

    # --- Log Operations ---

    def scan_log_event(
        self,
        scan_id: str,
        classification: str,
        message: str,
        component: Optional[str] = None,
    ) -> bool:
        """Log a scan event."""
        try:
            self.dbh.scanLogEvent(
                scan_id, classification, message, component
            )
            return True
        except Exception as e:
            self.log.error("scan_log_event failed: %s", e)
            return False

    def scan_log_get(
        self,
        scan_id: str,
        limit: int = 0,
        offset: int = 0,
        log_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get scan log entries."""
        try:
            rows = self.dbh.scanLogs(
                scan_id,
                limit=limit if limit > 0 else None,
                fromRowId=offset,
            )

            results = []
            for row in rows:
                # (generated, component, type, message, rowid)
                entry = {
                    "generated": row[0],
                    "component": row[1],
                    "type": row[2],
                    "message": row[3],
                    "rowid": row[4],
                }
                if log_type and entry["type"] != log_type:
                    continue
                results.append(entry)

            return results
        except Exception as e:
            self.log.error("scan_log_get failed: %s", e)
            return []

    # --- Config Operations ---

    def config_set(self, config_data: dict[str, str], scope: str = "GLOBAL") -> bool:
        """Set configuration values."""
        try:
            if scope == "GLOBAL":
                self.dbh.configSet(config_data)
            else:
                # Prefix keys with scope for scoped config
                scoped = {f"{scope}:{k}": v for k, v in config_data.items()}
                self.dbh.configSet(scoped)
            return True
        except Exception as e:
            self.log.error("config_set failed: %s", e)
            return False

    def config_get(self, scope: str = "GLOBAL") -> dict[str, str]:
        """Get configuration values."""
        try:
            all_config = self.dbh.configGet()
            if scope == "GLOBAL":
                # Return only GLOBAL entries (keys without ':')
                return {k: v for k, v in all_config.items() if ':' not in k}
            else:
                # Return scoped entries, stripping the scope prefix
                prefix = f"{scope}:"
                return {
                    k[len(prefix):]: v
                    for k, v in all_config.items()
                    if k.startswith(prefix)
                }
        except Exception as e:
            self.log.error("config_get failed: %s", e)
            return {}

    def scan_config_set(self, scan_id: str, config_data: dict[str, str]) -> bool:
        """Save scan-specific configuration."""
        try:
            self.dbh.scanConfigSet(scan_id, config_data)
            return True
        except Exception as e:
            self.log.error("scan_config_set failed: %s", e)
            return False

    # --- Correlation Operations ---

    def correlation_store(
        self,
        correlation_id: str,
        scan_id: str,
        title: str,
        rule_id: str,
        rule_name: str,
        rule_risk: str,
        rule_descr: str,
        rule_logic: str,
        event_hashes: list[str],
    ) -> bool:
        """Store a correlation result."""
        try:
            # The underlying method auto-generates a correlation_id,
            # but we pass ours via the event_hash parameter
            self.dbh.correlationResultCreate(
                instanceId=scan_id,
                event_hash=correlation_id,
                ruleId=rule_id,
                ruleName=rule_name,
                ruleDescr=rule_descr,
                ruleRisk=rule_risk,
                ruleYaml=rule_logic,
                correlationTitle=title,
                eventHashes=event_hashes,
            )
            return True
        except Exception as e:
            self.log.error("correlation_store failed: %s", e)
            return False

    def correlation_get_by_scan(self, scan_id: str) -> list[dict[str, Any]]:
        """Get all correlations for a scan."""
        try:
            rows = self.dbh.scanCorrelationList(scan_id)
            results = []
            for row in rows:
                # (id, title, rule_id, rule_risk, rule_name, rule_descr, rule_logic, event_count)
                results.append({
                    "id": row[0],
                    "title": row[1],
                    "rule_id": row[2],
                    "rule_risk": row[3],
                    "rule_name": row[4],
                    "rule_descr": row[5],
                    "rule_logic": row[6],
                    "event_count": row[7] if len(row) > 7 else 0,
                })
            return results
        except Exception as e:
            self.log.error("correlation_get_by_scan failed: %s", e)
            return []

    # --- Summary Operations ---

    def scan_result_summary(self, scan_id: str) -> dict[str, int]:
        """Get event type counts for a scan."""
        try:
            rows = self.dbh.scanResultSummary(scan_id, by="type")
            # (type, description, last_in, total, unique_total)
            return {row[0]: row[3] for row in rows}
        except Exception as e:
            self.log.error("scan_result_summary failed: %s", e)
            return {}

    def event_types_list(self) -> list[dict[str, str]]:
        """List all registered event types."""
        try:
            rows = self.dbh.eventTypes()
            results = []
            for row in rows:
                # (event_descr, event, event_raw, event_type)
                results.append({
                    "event_descr": row[0],
                    "event": row[1],
                    "event_raw": row[2],
                    "event_type": row[3],
                })
            return results
        except Exception as e:
            self.log.error("event_types_list failed: %s", e)
            return []
