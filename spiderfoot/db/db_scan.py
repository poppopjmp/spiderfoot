# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot Database Module
# Purpose:      Common functions for working with the database back-end.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
"""
Scan instance management (create, update, delete, list, get) for SpiderFootDb.
"""

from __future__ import annotations

import psycopg2
import logging
import time
from threading import RLock
from typing import Any
from .db_utils import get_placeholder, is_transient_error
from spiderfoot.config.constants import DB_RETRY_BACKOFF_BASE

log = logging.getLogger(__name__)

class ScanManager:
    """Manages scan instance lifecycle operations in the database."""
    def __init__(self, dbh: Any, conn: Any, dbhLock: RLock, db_type: str) -> None:
        """Initialize the ScanManager."""
        self.dbh = dbh
        self.conn = conn
        self.dbhLock = dbhLock
        self.db_type = db_type

    def _log_db_error(self, msg, exc):
        log.error("[DB] %s: %s", msg, exc)

    def _is_transient_error(self, exc):
        return is_transient_error(exc)

    def scanInstanceCreate(self, instanceId: str, scanName: str, scanTarget: str) -> None:
        """Create a new scan instance in the database."""
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(scanName, str):
            raise TypeError(f"scanName is {type(scanName)}; expected str()")
        if not isinstance(scanTarget, str):
            raise TypeError(f"scanTarget is {type(scanTarget)}; expected str()")
        ph = get_placeholder(self.db_type)
        qry = f"INSERT INTO tbl_scan_instance (guid, name, seed_target, created, status) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})"
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry, (instanceId, scanName, scanTarget, time.time() * 1000, 'CREATED'))
                    self.conn.commit()
                    return
                except psycopg2.Error as e:
                    self._log_db_error("Unable to create scan instance in database", e)
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("Unable to create scan instance in database") from e

    def scanInstanceSet(self, instanceId: str, started: str = None, ended: str = None, status: str = None) -> None:
        """Update fields on an existing scan instance."""
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        ph = get_placeholder(self.db_type)
        qvars = []
        qry = "UPDATE tbl_scan_instance SET "
        set_clauses = []
        if started is not None:
            set_clauses.append(f"started = {ph}")
            qvars.append(started)
        if ended is not None:
            set_clauses.append(f"ended = {ph}")
            qvars.append(ended)
        if status is not None:
            set_clauses.append(f"status = {ph}")
            qvars.append(status)
        if not set_clauses:
            return  # Nothing to update
        qry += ", ".join(set_clauses)
        qry += f" WHERE guid = {ph}"
        qvars.append(instanceId)
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry, qvars)
                    self.conn.commit()
                    return
                except psycopg2.Error as e:
                    self._log_db_error("Unable to set information for the scan instance.", e)
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("Unable to set information for the scan instance.") from e

    def scanInstanceGet(self, instanceId: str) -> list:
        """Retrieve a scan instance by its ID, including result count."""
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        ph = get_placeholder(self.db_type)
        qry = (
            f"SELECT i.guid, i.name, i.seed_target, "
            f"ROUND(i.created/1000) AS created, "
            f"ROUND(i.started/1000) AS started, "
            f"ROUND(i.ended/1000) AS ended, "
            f"i.status, "
            f"(SELECT COUNT(*) FROM tbl_scan_results r "
            f" WHERE r.scan_instance_id = i.guid AND r.type <> 'ROOT') AS result_count "
            f"FROM tbl_scan_instance i WHERE i.guid = {ph}"
        )
        qvars = [instanceId]
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry, qvars)
                    return self.dbh.fetchall()
                except psycopg2.Error as e:
                    self._log_db_error("SQL error encountered when retrieving scan instance", e)
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("SQL error encountered when retrieving scan instance") from e

    def scanInstanceList(self) -> list:
        """List all scan instances with result counts."""
        qry = "SELECT i.guid, i.name, i.seed_target, ROUND(i.created/1000), ROUND(i.started)/1000 as started, ROUND(i.ended)/1000, i.status, COUNT(r.type) FROM tbl_scan_instance i, tbl_scan_results r WHERE i.guid = r.scan_instance_id AND r.type <> 'ROOT' GROUP BY i.guid, i.name, i.seed_target, i.created, i.started, i.ended, i.status UNION ALL SELECT i.guid, i.name, i.seed_target, ROUND(i.created/1000), ROUND(i.started)/1000 as started, ROUND(i.ended)/1000, i.status, '0' FROM tbl_scan_instance i  WHERE i.guid NOT IN ( SELECT distinct scan_instance_id FROM tbl_scan_results WHERE type <> 'ROOT') ORDER BY started DESC"
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry)
                    return self.dbh.fetchall()
                except psycopg2.Error as e:
                    self._log_db_error("SQL error encountered when fetching scan list", e)
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("SQL error encountered when fetching scan list") from e

    def scanInstanceDelete(self, instanceId: str) -> bool:
        """Delete a scan instance and all related records.

        Delete order respects FK constraints:
        1. tbl_scan_correlation_results_events (FK → tbl_scan_correlation_results)
        2. tbl_scan_correlation_results        (FK → tbl_scan_instance)
        3. tbl_scan_config                     (FK → tbl_scan_instance)
        4. tbl_scan_results                    (FK → tbl_scan_instance)
        5. tbl_scan_log                        (FK → tbl_scan_instance)
        6. tbl_scan_instance                   (parent — deleted last)
        """
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        ph = get_placeholder(self.db_type)

        # Child tables first (respecting FK dependency order)
        qry_corr_events = (
            f"DELETE FROM tbl_scan_correlation_results_events "
            f"WHERE correlation_id IN ("
            f"  SELECT id FROM tbl_scan_correlation_results WHERE scan_instance_id = {ph}"
            f")"
        )
        qry_corr = f"DELETE FROM tbl_scan_correlation_results WHERE scan_instance_id = {ph}"
        qry_config = f"DELETE FROM tbl_scan_config WHERE scan_instance_id = {ph}"
        qry_results = f"DELETE FROM tbl_scan_results WHERE scan_instance_id = {ph}"
        qry_log = f"DELETE FROM tbl_scan_log WHERE scan_instance_id = {ph}"
        # Parent table last
        qry_instance = f"DELETE FROM tbl_scan_instance WHERE guid = {ph}"

        qvars = [instanceId]
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry_corr_events, qvars)
                    self.dbh.execute(qry_corr, qvars)
                    self.dbh.execute(qry_config, qvars)
                    self.dbh.execute(qry_results, qvars)
                    self.dbh.execute(qry_log, qvars)
                    self.dbh.execute(qry_instance, qvars)
                    self.conn.commit()
                    return True
                except psycopg2.Error as e:
                    self._log_db_error("SQL error encountered when deleting scan", e)
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("SQL error encountered when deleting scan") from e
        return True

    def close(self) -> None:
        """Close the database cursor and connection."""
        if hasattr(self, 'dbh') and self.dbh:
            try:
                self.dbh.close()
            except Exception as e:
                self._log_db_error("Error closing DB cursor", e)
            self.dbh = None
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
            except Exception as e:
                self._log_db_error("Error closing DB connection", e)
            self.conn = None
