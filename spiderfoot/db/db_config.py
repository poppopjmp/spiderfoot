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
Configuration management (global and per-scan) for SpiderFootDb.
"""
from .db_utils import get_placeholder, is_transient_error, get_upsert_clause
import time

class ConfigManager:
    def __init__(self, dbh, conn, dbhLock, db_type):
        self.dbh = dbh
        self.conn = conn
        self.dbhLock = dbhLock
        self.db_type = db_type

    def _log_db_error(self, msg, exc):
        print(f"[DB ERROR] {msg}: {exc}")

    def _is_transient_error(self, exc):
        return is_transient_error(exc)

    def configSet(self, optMap: dict = {}) -> bool:
        if not isinstance(optMap, dict):
            raise TypeError(f"optMap is {type(optMap)}; expected dict()")
        if not optMap:
            raise ValueError("optMap is empty")
        ph = get_placeholder(self.db_type)
        upsert_clause = get_upsert_clause(self.db_type, 'tbl_config', ['scope', 'opt'], ['val'])
        qry = f"INSERT INTO tbl_config (scope, opt, val) VALUES ({ph}, {ph}, {ph}) {upsert_clause}"
        with self.dbhLock:
            for opt in list(optMap.keys()):
                if ":" in opt:
                    parts = opt.split(':')
                    qvals = [parts[0], parts[1], optMap[opt]]
                else:
                    qvals = ["GLOBAL", opt, optMap[opt]]
                for attempt in range(3):
                    try:
                        self.dbh.execute(qry, qvals)
                        break
                    except Exception as e:
                        self._log_db_error("SQL error encountered when storing config", e)
                        if self._is_transient_error(e) and attempt < 2:
                            time.sleep(0.2 * (attempt + 1))
                            continue
                        raise IOError("SQL error encountered when storing config, aborting") from e
            for attempt in range(3):
                try:
                    self.conn.commit()
                    return True
                except Exception as e:
                    self._log_db_error("SQL error encountered when storing config (commit)", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise IOError("SQL error encountered when storing config, aborting") from e
        return True

    def configGet(self) -> dict:
        ph = get_placeholder(self.db_type)
        qry = "SELECT scope, opt, val FROM tbl_config"
        retval = dict()
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry)
                    for [scope, opt, val] in self.dbh.fetchall():
                        if scope == "GLOBAL":
                            retval[opt] = val
                        else:
                            retval[f"{scope}:{opt}"] = val
                    return retval
                except Exception as e:
                    self._log_db_error("SQL error encountered when fetching configuration", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise IOError("SQL error encountered when fetching configuration") from e

    def configClear(self) -> None:
        ph = get_placeholder(self.db_type)
        qry = "DELETE from tbl_config"
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry)
                    self.conn.commit()
                    return
                except Exception as e:
                    self._log_db_error("Unable to clear configuration from the database", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise IOError("Unable to clear configuration from the database") from e

    def scanConfigSet(self, scan_id, optMap=dict()) -> None:
        if not isinstance(optMap, dict):
            raise TypeError(f"optMap is {type(optMap)}; expected dict()")
        if not optMap:
            raise ValueError("optMap is empty")
        ph = get_placeholder(self.db_type)
        upsert_clause = get_upsert_clause(self.db_type, 'tbl_scan_config', ['scan_instance_id', 'component', 'opt'], ['val'])
        qry = f"INSERT INTO tbl_scan_config (scan_instance_id, component, opt, val) VALUES ({ph}, {ph}, {ph}, {ph}) {upsert_clause}"
        with self.dbhLock:
            for opt in list(optMap.keys()):
                if ":" in opt:
                    parts = opt.split(':')
                    qvals = [scan_id, parts[0], parts[1], optMap[opt]]
                else:
                    qvals = [scan_id, "GLOBAL", opt, optMap[opt]]
                for attempt in range(3):
                    try:
                        self.dbh.execute(qry, qvals)
                        break
                    except Exception as e:
                        self._log_db_error("SQL error encountered when storing config", e)
                        if self._is_transient_error(e) and attempt < 2:
                            time.sleep(0.2 * (attempt + 1))
                            continue
                        raise IOError("SQL error encountered when storing config, aborting") from e
            for attempt in range(3):
                try:
                    self.conn.commit()
                    return
                except Exception as e:
                    self._log_db_error("SQL error encountered when storing config (commit)", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise IOError("SQL error encountered when storing config, aborting") from e

    def scanConfigGet(self, instanceId: str) -> dict:
        ph = get_placeholder(self.db_type)
        qry = f"SELECT component, opt, val FROM tbl_scan_config WHERE scan_instance_id = {ph} ORDER BY component, opt"
        qvars = [instanceId]
        retval = dict()
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry, qvars)
                    for [component, opt, val] in self.dbh.fetchall():
                        if component == "GLOBAL":
                            retval[opt] = val
                        else:
                            retval[f"{component}:{opt}"] = val
                    return retval
                except Exception as e:
                    self._log_db_error("SQL error encountered when fetching configuration", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise IOError("SQL error encountered when fetching configuration") from e

    def scanConfigClear(self, instanceId: str) -> None:
        ph = get_placeholder(self.db_type)
        qry = f"DELETE from tbl_scan_config WHERE scan_instance_id = {ph}"
        qvars = [instanceId]
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute(qry, qvars)
                    self.conn.commit()
                    return
                except Exception as e:
                    self._log_db_error("Unable to clear scan configuration from the database", e)
                    if self._is_transient_error(e) and attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise IOError("Unable to clear scan configuration from the database") from e

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
