# -*- coding: utf-8 -*-
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

import sqlite3
import psycopg2
import time
from .db_utils import get_placeholder, is_transient_error

class ScanManager:
    def __init__(self, dbh, conn, dbhLock, db_type):
        self.dbh = dbh
        self.conn = conn
        self.dbhLock = dbhLock
        self.db_type = db_type

    def _log_db_error(self, msg, exc):
        print(f"[DB ERROR] {msg}: {exc}")

    def _is_transient_error(self, exc):
        return is_transient_error(exc)

    def scanInstanceCreate(self, instanceId: str, scanName: str, scanTarget: str) -> None:
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
                except (sqlite3.Error, psycopg2.Error) as e:
                    self._log_db_error("Unable to create scan instance in database", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise IOError("Unable to create scan instance in database") from e

    def scanInstanceSet(self, instanceId: str, started: str = None, ended: str = None, status: str = None) -> None:
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
                except (sqlite3.Error, psycopg2.Error) as e:
                    self._log_db_error("Unable to set information for the scan instance.", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise IOError("Unable to set information for the scan instance.") from e

    def scanInstanceGet(self, instanceId: str) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        ph = get_placeholder(self.db_type)
        qry = f"SELECT name, seed_target, ROUND(created/1000) AS created, ROUND(started/1000) AS started, ROUND(ended/1000) AS ended, status FROM tbl_scan_instance WHERE guid = {ph}"
        qvars = [instanceId]
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry, qvars)
                    return self.dbh.fetchall()
                except (sqlite3.Error, psycopg2.Error) as e:
                    self._log_db_error("SQL error encountered when retrieving scan instance", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise IOError("SQL error encountered when retrieving scan instance") from e

    def scanInstanceList(self) -> list:
        qry = "SELECT i.guid, i.name, i.seed_target, ROUND(i.created/1000), ROUND(i.started)/1000 as started, ROUND(i.ended)/1000, i.status, COUNT(r.type) FROM tbl_scan_instance i, tbl_scan_results r WHERE i.guid = r.scan_instance_id AND r.type <> 'ROOT' GROUP BY i.guid UNION ALL SELECT i.guid, i.name, i.seed_target, ROUND(i.created/1000), ROUND(i.started)/1000 as started, ROUND(i.ended)/1000, i.status, '0' FROM tbl_scan_instance i  WHERE i.guid NOT IN ( SELECT distinct scan_instance_id FROM tbl_scan_results WHERE type <> 'ROOT') ORDER BY started DESC"
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry)
                    return self.dbh.fetchall()
                except (sqlite3.Error, psycopg2.Error) as e:
                    self._log_db_error("SQL error encountered when fetching scan list", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise IOError("SQL error encountered when fetching scan list") from e

    def scanInstanceDelete(self, instanceId: str) -> bool:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        ph = get_placeholder(self.db_type)
        qry1 = f"DELETE FROM tbl_scan_instance WHERE guid = {ph}"
        qry2 = f"DELETE FROM tbl_scan_config WHERE scan_instance_id = {ph}"
        qry3 = f"DELETE FROM tbl_scan_results WHERE scan_instance_id = {ph}"
        qry4 = f"DELETE FROM tbl_scan_log WHERE scan_instance_id = {ph}"
        qvars = [instanceId]
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry1, qvars)
                    self.dbh.execute(qry2, qvars)
                    self.dbh.execute(qry3, qvars)
                    self.dbh.execute(qry4, qvars)
                    self.conn.commit()
                    return True
                except (sqlite3.Error, psycopg2.Error) as e:
                    self._log_db_error("SQL error encountered when deleting scan", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise IOError("SQL error encountered when deleting scan") from e
        return True

    def close(self):
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
