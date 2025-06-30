# db_correlation.py
"""
Correlation result management and queries for SpiderFootDb.
"""
class CorrelationManager:
    def __init__(self, dbh, conn, dbhLock, db_type):
        self.dbh = dbh
        self.conn = conn
        self.dbhLock = dbhLock
        self.db_type = db_type

    def correlationResultCreate(self, instanceId: str, event_hash: str, ruleId: str,
        ruleName: str, ruleDescr: str, ruleRisk: str, ruleYaml: str, correlationTitle: str, eventHashes: list) -> str:
        import uuid
        correlation_id = str(uuid.uuid4())
        with self.dbhLock:
            qry = "INSERT INTO tbl_scan_correlation_results \
                (id, scan_instance_id, title, rule_id, rule_risk, rule_name, \
                rule_descr, rule_logic) \
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            qvars = [correlation_id, instanceId, correlationTitle, ruleId, ruleRisk, ruleName, ruleDescr, ruleYaml]
            try:
                self.dbh.execute(qry, qvars)
                self.conn.commit()
            except Exception as e:
                raise IOError("Unable to create correlation result in database") from e
            correlationId = correlation_id
            if isinstance(eventHashes, str):
                eventHashes = [eventHashes]
            for eventHash in eventHashes:
                qry = "INSERT INTO tbl_scan_correlation_results_events (correlation_id, event_hash) VALUES (?, ?)"
                qvars = [correlationId, eventHash]
                try:
                    self.dbh.execute(qry, qvars)
                except Exception as e:
                    raise IOError("Unable to create correlation result events in database") from e
            self.conn.commit()
        return str(correlationId)

    def scanCorrelationSummary(self, instanceId: str, by: str = "rule") -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(by, str):
            raise TypeError(f"by is {type(by)}; expected str()")
        if by not in ["rule", "risk"]:
            raise ValueError(f"Invalid filter by value: {by}")
        if by == "risk":
            qry = "SELECT rule_risk, count(*) AS total FROM \
                tbl_scan_correlation_results \
                WHERE scan_instance_id = ? GROUP BY rule_risk ORDER BY rule_id"
        if by == "rule":
            qry = "SELECT rule_id, rule_name, rule_risk, rule_descr, \
                count(*) AS total FROM \
                tbl_scan_correlation_results \
                WHERE scan_instance_id = ? GROUP BY rule_id ORDER BY rule_id"
        qvars = [instanceId]
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except Exception as e:
                raise IOError("SQL error encountered when fetching correlation summary") from e

    def scanCorrelationList(self, instanceId: str) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        qry = "SELECT c.id, c.title, c.rule_id, c.rule_risk, c.rule_name, \
            c.rule_descr, c.rule_logic, count(e.event_hash) AS event_count FROM \
            tbl_scan_correlation_results c, tbl_scan_correlation_results_events e \
            WHERE scan_instance_id = ? AND c.id = e.correlation_id \
            GROUP BY c.id ORDER BY c.title, c.rule_risk"
        qvars = [instanceId]
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except Exception as e:
                raise IOError("SQL error encountered when fetching correlation list") from e

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
