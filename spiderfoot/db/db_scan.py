# db_scan.py
"""
Scan instance management (create, update, delete, list, get) for SpiderFootDb.
"""

import sqlite3
import psycopg2
import time

class ScanManager:
    def __init__(self, dbh, conn, dbhLock, db_type):
        self.dbh = dbh
        self.conn = conn
        self.dbhLock = dbhLock
        self.db_type = db_type

    def scanInstanceCreate(self, instanceId: str, scanName: str, scanTarget: str) -> None:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(scanName, str):
            raise TypeError(f"scanName is {type(scanName)}; expected str()")
        if not isinstance(scanTarget, str):
            raise TypeError(f"scanTarget is {type(scanTarget)}; expected str()")
        qry = "INSERT INTO tbl_scan_instance (guid, name, seed_target, created, status) VALUES (?, ?, ?, ?, ?)"
        with self.dbhLock:
            try:
                self.dbh.execute(qry, (instanceId, scanName, scanTarget, time.time() * 1000, 'CREATED'))
                self.conn.commit()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("Unable to create scan instance in database") from e

    def scanInstanceSet(self, instanceId: str, started: str = None, ended: str = None, status: str = None) -> None:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        qvars = []
        qry = "UPDATE tbl_scan_instance SET "
        if started is not None:
            qry += " started = ?, "
            qvars.append(started)
        if ended is not None:
            qry += " ended = ?, "
            qvars.append(ended)
        if status is not None:
            qry += " status = ?, "
            qvars.append(status)
        qry += " guid = guid WHERE guid = ?"
        qvars.append(instanceId)
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                self.conn.commit()
            except (sqlite3.Error, psycopg2.Error):
                raise IOError("Unable to set information for the scan instance.") from None

    def scanInstanceGet(self, instanceId: str) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        qry = "SELECT name, seed_target, ROUND(created/1000) AS created, ROUND(started/1000) AS started, ROUND(ended/1000) AS ended, status FROM tbl_scan_instance WHERE guid = ?"
        qvars = [instanceId]
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when retrieving scan instance") from e

    def scanInstanceList(self) -> list:
        qry = "SELECT i.guid, i.name, i.seed_target, ROUND(i.created/1000), ROUND(i.started)/1000 as started, ROUND(i.ended)/1000, i.status, COUNT(r.type) FROM tbl_scan_instance i, tbl_scan_results r WHERE i.guid = r.scan_instance_id AND r.type <> 'ROOT' GROUP BY i.guid UNION ALL SELECT i.guid, i.name, i.seed_target, ROUND(i.created/1000), ROUND(i.started)/1000 as started, ROUND(i.ended)/1000, i.status, '0' FROM tbl_scan_instance i  WHERE i.guid NOT IN ( SELECT distinct scan_instance_id FROM tbl_scan_results WHERE type <> 'ROOT') ORDER BY started DESC"
        with self.dbhLock:
            try:
                self.dbh.execute(qry)
                return self.dbh.fetchall()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when fetching scan list") from e

    def scanInstanceDelete(self, instanceId: str) -> bool:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        qry1 = "DELETE FROM tbl_scan_instance WHERE guid = ?"
        qry2 = "DELETE FROM tbl_scan_config WHERE scan_instance_id = ?"
        qry3 = "DELETE FROM tbl_scan_results WHERE scan_instance_id = ?"
        qry4 = "DELETE FROM tbl_scan_log WHERE scan_instance_id = ?"
        qvars = [instanceId]
        with self.dbhLock:
            try:
                self.dbh.execute(qry1, qvars)
                self.dbh.execute(qry2, qvars)
                self.dbh.execute(qry3, qvars)
                self.dbh.execute(qry4, qvars)
                self.conn.commit()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when deleting scan") from e
        return True

    def close(self):
        if hasattr(self, 'dbh') and self.dbh:
            try:
                self.dbh.close()
            except Exception:
                pass
            self.dbh = None
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
