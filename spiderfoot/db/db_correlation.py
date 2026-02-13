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
Correlation result management and queries for SpiderFootDb.
"""
from __future__ import annotations

import logging
import time
from threading import RLock
from typing import Any
from .db_utils import get_placeholder, is_transient_error
from spiderfoot.config.constants import DB_RETRY_BACKOFF_BASE

log = logging.getLogger(__name__)

class CorrelationManager:
    """Manages correlation result storage and queries in the database."""
    def __init__(self, dbh: Any, conn: Any, dbhLock: RLock, db_type: str) -> None:
        """Initialize the CorrelationManager."""
        self.dbh = dbh
        self.conn = conn
        self.dbhLock = dbhLock
        self.db_type = db_type

    def _log_db_error(self, msg, exc):
        log.error("[DB] %s: %s", msg, exc)

    def _is_transient_error(self, exc):
        return is_transient_error(exc)

    def correlationResultCreate(self, instanceId: str, event_hash: str, ruleId: str,
        ruleName: str, ruleDescr: str, ruleRisk: str, ruleYaml: str, correlationTitle: str, eventHashes: list) -> str:
        """Create a new correlation result and associate event hashes."""
        import uuid
        correlation_id = str(uuid.uuid4())
        ph = get_placeholder(self.db_type)
        with self.dbhLock:
            qry = f"INSERT INTO tbl_scan_correlation_results (id, scan_instance_id, title, rule_id, rule_risk, rule_name, rule_descr, rule_logic) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})"
            qvars = [correlation_id, instanceId, correlationTitle, ruleId, ruleRisk, ruleName, ruleDescr, ruleYaml]
            for attempt in range(3):
                try:
                    self.dbh.execute(qry, qvars)
                    self.conn.commit()
                    break
                except Exception as e:
                    self._log_db_error("Unable to create correlation result in database", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("Unable to create correlation result in database") from e
            correlationId = correlation_id
            if isinstance(eventHashes, str):
                eventHashes = [eventHashes]
            for eventHash in eventHashes:
                qry = f"INSERT INTO tbl_scan_correlation_results_events (correlation_id, event_hash) VALUES ({ph}, {ph})"
                qvars = [correlationId, eventHash]
                for attempt in range(3):
                    try:
                        self.dbh.execute(qry, qvars)
                        break
                    except Exception as e:
                        self._log_db_error("Unable to create correlation result events in database", e)
                        if self._is_transient_error(e) and attempt < 2:
                            time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                            continue
                        raise OSError("Unable to create correlation result events in database") from e
            for attempt in range(3):
                try:
                    self.conn.commit()
                    break
                except Exception as e:
                    self._log_db_error("Unable to commit correlation result events", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("Unable to commit correlation result events") from e
        return str(correlationId)

    def scanCorrelationSummary(self, instanceId: str, by: str = "rule") -> list:
        """Return a summary of correlation results grouped by rule or risk."""
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(by, str):
            raise TypeError(f"by is {type(by)}; expected str()")
        if by not in ["rule", "risk"]:
            raise ValueError(f"Invalid filter by value: {by}")
        ph = get_placeholder(self.db_type)
        if by == "risk":
            qry = f"SELECT rule_risk, count(*) AS total FROM tbl_scan_correlation_results WHERE scan_instance_id = {ph} GROUP BY rule_risk ORDER BY rule_risk"
        elif by == "rule":
            qry = f"SELECT rule_id, rule_name, rule_risk, rule_descr, count(*) AS total FROM tbl_scan_correlation_results WHERE scan_instance_id = {ph} GROUP BY rule_id, rule_name, rule_risk, rule_descr ORDER BY rule_id"
        qvars = [instanceId]
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry, qvars)
                    return self.dbh.fetchall()
                except Exception as e:
                    self._log_db_error("SQL error encountered when fetching correlation summary", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("SQL error encountered when fetching correlation summary") from e

    def scanCorrelationList(self, instanceId: str) -> list:
        """Return the list of correlation results for a scan."""
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        ph = get_placeholder(self.db_type)
        qry = f"SELECT c.id, c.title, c.rule_id, c.rule_risk, c.rule_name, c.rule_descr, c.rule_logic, count(e.event_hash) AS event_count FROM tbl_scan_correlation_results c LEFT JOIN tbl_scan_correlation_results_events e ON c.id = e.correlation_id WHERE c.scan_instance_id = {ph} GROUP BY c.id, c.title, c.rule_id, c.rule_risk, c.rule_name, c.rule_descr, c.rule_logic ORDER BY c.title, c.rule_risk"
        qvars = [instanceId]
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry, qvars)
                    return self.dbh.fetchall()
                except Exception as e:
                    self._log_db_error("SQL error encountered when fetching correlation list", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("SQL error encountered when fetching correlation list") from e

    def close(self) -> None:
        """Release references to the shared database cursor and connection.

        Note: Does NOT call .close() on dbh/conn since they are shared
        with the parent SpiderFootDb instance which owns their lifecycle.
        """
        self.dbh = None
        self.conn = None
