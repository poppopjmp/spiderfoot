# db_config.py
"""
Configuration management (global and per-scan) for SpiderFootDb.
"""
class ConfigManager:
    def __init__(self, dbh, conn, dbhLock, db_type):
        self.dbh = dbh
        self.conn = conn
        self.dbhLock = dbhLock
        self.db_type = db_type

    def configSet(self, optMap: dict = {}) -> bool:
        if not isinstance(optMap, dict):
            raise TypeError(f"optMap is {type(optMap)}; expected dict()")
        if not optMap:
            raise ValueError("optMap is empty")
        qry = "REPLACE INTO tbl_config (scope, opt, val) VALUES (?, ?, ?)"
        with self.dbhLock:
            for opt in list(optMap.keys()):
                if ":" in opt:
                    parts = opt.split(':')
                    qvals = [parts[0], parts[1], optMap[opt]]
                else:
                    qvals = ["GLOBAL", opt, optMap[opt]]
                try:
                    self.dbh.execute(qry, qvals)
                except Exception as e:
                    raise IOError("SQL error encountered when storing config, aborting") from e
            try:
                self.conn.commit()
            except Exception as e:
                raise IOError("SQL error encountered when storing config, aborting") from e
        return True

    def configGet(self) -> dict:
        qry = "SELECT scope, opt, val FROM tbl_config"
        retval = dict()
        with self.dbhLock:
            try:
                self.dbh.execute(qry)
                for [scope, opt, val] in self.dbh.fetchall():
                    if scope == "GLOBAL":
                        retval[opt] = val
                    else:
                        retval[f"{scope}:{opt}"] = val
                return retval
            except Exception as e:
                raise IOError("SQL error encountered when fetching configuration") from e

    def configClear(self) -> None:
        qry = "DELETE from tbl_config"
        with self.dbhLock:
            try:
                self.dbh.execute(qry)
                self.conn.commit()
            except Exception as e:
                raise IOError("Unable to clear configuration from the database") from e

    def scanConfigSet(self, scan_id, optMap=dict()) -> None:
        if not isinstance(optMap, dict):
            raise TypeError(f"optMap is {type(optMap)}; expected dict()")
        if not optMap:
            raise ValueError("optMap is empty")
        qry = "REPLACE INTO tbl_scan_config (scan_instance_id, component, opt, val) VALUES (?, ?, ?, ?)"
        with self.dbhLock:
            for opt in list(optMap.keys()):
                if ":" in opt:
                    parts = opt.split(':')
                    qvals = [scan_id, parts[0], parts[1], optMap[opt]]
                else:
                    qvals = [scan_id, "GLOBAL", opt, optMap[opt]]
                try:
                    self.dbh.execute(qry, qvals)
                except Exception as e:
                    raise IOError("SQL error encountered when storing config, aborting") from e
            try:
                self.conn.commit()
            except Exception as e:
                raise IOError("SQL error encountered when storing config, aborting") from e

    def scanConfigGet(self, instanceId: str) -> dict:
        qry = "SELECT component, opt, val FROM tbl_scan_config WHERE scan_instance_id = ? ORDER BY component, opt"
        qvars = [instanceId]
        retval = dict()
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                for [component, opt, val] in self.dbh.fetchall():
                    if component == "GLOBAL":
                        retval[opt] = val
                    else:
                        retval[f"{component}:{opt}"] = val
                return retval
            except Exception as e:
                raise IOError("SQL error encountered when fetching configuration") from e

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
