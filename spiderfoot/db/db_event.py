# db_event.py
"""
Event storage, retrieval, search, and event tree navigation for SpiderFootDb.
"""
from threading import RLock
import time
import sqlite3
import psycopg2
from ..event import SpiderFootEvent

class EventManager:
    def __init__(self, dbh, conn, dbhLock, db_type):
        self.dbh = dbh
        self.conn = conn
        self.dbhLock = dbhLock
        self.db_type = db_type

    def scanLogEvents(self, batch: list) -> bool:
        inserts = []
        for item in batch:
            if len(item) != 5:
                continue
            instanceId, classification, message, component, logTime = item
            if not isinstance(instanceId, str):
                continue
            if not isinstance(classification, str):
                continue
            if not isinstance(message, str):
                continue
            if not component:
                component = "SpiderFoot"
            if isinstance(logTime, float):
                logTime = int(logTime * 1000)
            elif isinstance(logTime, int) and logTime < 1000000000000:
                logTime = logTime * 1000
            inserts.append((instanceId, logTime, component, classification, message))
        if not inserts:
            return True
        if self.db_type == 'sqlite':
            qry = "INSERT INTO tbl_scan_log \
                (scan_instance_id, generated, component, type, message) \
                VALUES (?, ?, ?, ?, ?)"
        else:
            qry = "INSERT INTO tbl_scan_log \
                (scan_instance_id, generated, component, type, message) \
                VALUES (%s, %s, %s, %s, %s)"
        with self.dbhLock:
            try:
                if not self.conn:
                    return False
                self.dbh.executemany(qry, inserts)
                self.conn.commit()
                return True
            except (sqlite3.Error, psycopg2.Error) as e:
                if "locked" in str(e).lower() or "thread" in str(e).lower():
                    return False
                try:
                    self.conn.rollback()
                except:
                    pass
                return False
            except Exception:
                return False

    def scanLogEvent(self, instanceId: str, classification: str, message: str, component: str = None) -> None:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(classification, str):
            raise TypeError(f"classification is {type(classification)}; expected str()")
        if not isinstance(message, str):
            raise TypeError(f"message is {type(message)}; expected str()")
        if not component:
            component = "SpiderFoot"
        qry = "INSERT INTO tbl_scan_log \
            (scan_instance_id, generated, component, type, message) \
            VALUES (?, ?, ?, ?, ?)"
        with self.dbhLock:
            try:
                self.dbh.execute(qry, (
                    instanceId, time.time() * 1000, component, classification, message
                ))
                self.conn.commit()
            except (sqlite3.Error, psycopg2.Error) as e:
                if "locked" not in str(e.args[0]) and "thread" not in str(e.args[0]):
                    raise IOError("Unable to log scan event in database") from e
                pass

    def scanLogs(self, instanceId: str, limit: int = None, fromRowId: int = 0, reverse: bool = False) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        qry = "SELECT generated AS generated, component, type, message, rowid FROM tbl_scan_log WHERE scan_instance_id = ?"
        if fromRowId:
            qry += " and rowid > ?"
        qry += " ORDER BY generated "
        if reverse:
            qry += "ASC"
        else:
            qry += "DESC"
        qvars = [instanceId]
        if fromRowId:
            qvars.append(str(fromRowId))
        if limit is not None:
            qry += " LIMIT ?"
            qvars.append(str(limit))
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when fetching scan logs") from e

    def scanErrors(self, instanceId: str, limit: int = 0) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(limit, int):
            raise TypeError(f"limit is {type(limit)}; expected int()")
        qry = "SELECT generated AS generated, component, message FROM tbl_scan_log WHERE scan_instance_id = ? AND type = 'ERROR' ORDER BY generated DESC"
        qvars = [instanceId]
        if limit:
            qry += " LIMIT ?"
            qvars.append(str(limit))
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when fetching scan errors") from e

    def scanResultEvent(self, instanceId: str, eventType: str = 'ALL', srcModule: str = None, data: list = None, sourceId: list = None, correlationId: str = None, filterFp: bool = False) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(eventType, str) and not isinstance(eventType, list):
            raise TypeError(f"eventType is {type(eventType)}; expected str() or list()")
        # Fix: Use LEFT JOIN for parent event, and allow source_event_hash = 'ROOT' to include root events
        # Legacy tuple order: generated, data, module, hash, type, source_event_hash, confidence, visibility, risk
        qry = ("SELECT ROUND(c.generated) AS generated, c.data, c.module, c.hash, c.type, c.source_event_hash, c.confidence, c.visibility, c.risk "
               "FROM tbl_scan_results c "
               "WHERE c.scan_instance_id = ? ")
        qvars = [instanceId]
        if eventType != "ALL":
            if isinstance(eventType, list):
                qry += " AND c.type in (" + ','.join(['?'] * len(eventType)) + ")"
                qvars.extend(eventType)
            else:
                qry += " AND c.type = ?"
                qvars.append(eventType)
        if filterFp:
            qry += " AND c.false_positive <> 1"
        if srcModule:
            if isinstance(srcModule, list):
                qry += " AND c.module in (" + ','.join(['?'] * len(srcModule)) + ")"
                qvars.extend(srcModule)
            else:
                qry += " AND c.module = ?"
                qvars.append(srcModule)
        if data:
            if isinstance(data, list):
                qry += " AND c.data in (" + ','.join(['?'] * len(data)) + ")"
                qvars.extend(data)
            else:
                qry += " AND c.data = ?"
                qvars.append(data)
        if sourceId:
            if isinstance(sourceId, list):
                qry += " AND c.source_event_hash in (" + ','.join(['?'] * len(sourceId)) + ")"
                qvars.extend(sourceId)
            else:
                qry += " AND c.source_event_hash = ?"
                qvars.append(sourceId)
        # Special case: include events where c.source_event_hash = 'ROOT'
        qry += " AND (c.source_event_hash = 'ROOT' OR c.source_event_hash != 'ROOT')"
        qry += " ORDER BY c.data"
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when fetching result events") from e

    def scanResultEventUnique(self, instanceId: str, eventType: str = 'ALL', filterFp: bool = False) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(eventType, str):
            raise TypeError(f"eventType is {type(eventType)}; expected str()")
        qry = "SELECT DISTINCT data, type, COUNT(*) FROM tbl_scan_results WHERE scan_instance_id = ?"
        qvars = [instanceId]
        if eventType != "ALL":
            qry += " AND type = ?"
            qvars.append(eventType)
        if filterFp:
            qry += " AND false_positive <> 1"
        qry += " GROUP BY type, data ORDER BY COUNT(*)"
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when fetching unique result events") from e

    def scanResultSummary(self, instanceId: str, by: str = "type") -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(by, str):
            raise TypeError(f"by is {type(by)}; expected str()")
        if by not in ["type", "module", "entity"]:
            raise ValueError(f"Invalid filter by value: {by}")
        if by == "type":
            qry = "SELECT r.type, e.event_descr, MAX(ROUND(generated)) AS last_in, count(*) AS total, count(DISTINCT r.data) as utotal FROM tbl_scan_results r, tbl_event_types e WHERE e.event = r.type AND r.scan_instance_id = ? GROUP BY r.type ORDER BY e.event_descr"
        if by == "module":
            qry = "SELECT r.module, '', MAX(ROUND(generated)) AS last_in, count(*) AS total, count(DISTINCT r.data) as utotal FROM tbl_scan_results r, tbl_event_types e WHERE e.event = r.type AND r.scan_instance_id = ? GROUP BY r.module ORDER BY r.module DESC"
        if by == "entity":
            qry = "SELECT r.data, e.event_descr, MAX(ROUND(generated)) AS last_in, count(*) AS total, count(DISTINCT r.data) as utotal FROM tbl_scan_results r, tbl_event_types e WHERE e.event = r.type AND r.scan_instance_id = ? AND e.event_type in ('ENTITY') GROUP BY r.data, e.event_descr ORDER BY total DESC limit 50"
        qvars = [instanceId]
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when fetching result summary") from e

    def scanResultHistory(self, instanceId: str) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        qry = "SELECT STRFTIME('%H:%M %w', generated, 'unixepoch') AS hourmin, type, COUNT(*) FROM tbl_scan_results WHERE scan_instance_id = ? GROUP BY hourmin, type"
        qvars = [instanceId]
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError(f"SQL error encountered when fetching history for scan {instanceId}") from e

    def scanResultsUpdateFP(self, instanceId: str, resultHashes: list, fpFlag: int) -> bool:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(resultHashes, list):
            raise TypeError(f"resultHashes is {type(resultHashes)}; expected list()")
        with self.dbhLock:
            for resultHash in resultHashes:
                qry = "UPDATE tbl_scan_results SET false_positive = ? WHERE scan_instance_id = ? AND hash = ?"
                qvars = [fpFlag, instanceId, resultHash]
                try:
                    self.dbh.execute(qry, qvars)
                except (sqlite3.Error, psycopg2.Error) as e:
                    raise IOError("SQL error encountered when updating false-positive") from e
            try:
                self.conn.commit()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when updating false-positive") from e
        return True

    def scanEventStore(self, instanceId: str, sfEvent, truncateSize: int = 0) -> None:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not instanceId:
            raise ValueError("instanceId is empty")
        if not isinstance(sfEvent, SpiderFootEvent):
            raise TypeError(f"sfEvent is {type(sfEvent)}; expected SpiderFootEvent()")
        if not isinstance(sfEvent.generated, (int, float)):
            raise TypeError(f"sfEvent.generated is {type(sfEvent.generated)}; expected int() or float()")
        if not sfEvent.generated:
            raise ValueError("sfEvent.generated is empty")
        if not isinstance(sfEvent.eventType, str):
            raise TypeError(f"sfEvent.eventType is {type(sfEvent.eventType,)}; expected str()")
        if not sfEvent.eventType:
            raise ValueError("sfEvent.eventType is empty")
        if not isinstance(sfEvent.data, str):
            raise TypeError(f"sfEvent.data is {type(sfEvent.data)}; expected str()")
        if not sfEvent.data:
            raise ValueError("sfEvent.data is empty")
        if not isinstance(sfEvent.module, str):
            raise TypeError(f"sfEvent.module is {type(sfEvent.module)}; expected str()")
        if not sfEvent.module and sfEvent.eventType != "ROOT":
            raise ValueError("sfEvent.module is empty")
        if not isinstance(sfEvent.confidence, int):
            raise TypeError(f"sfEvent.confidence is {type(sfEvent.confidence)}; expected int()")
        if not 0 <= sfEvent.confidence <= 100:
            raise ValueError(f"sfEvent.confidence value is {type(sfEvent.confidence)}; expected 0 - 100")
        if not isinstance(sfEvent.visibility, int):
            raise TypeError(f"sfEvent.visibility is {type(sfEvent.visibility)}; expected int()")
        if not 0 <= sfEvent.visibility <= 100:
            raise ValueError(f"sfEvent.visibility value is {type(sfEvent.visibility)}; expected 0 - 100")
        if not isinstance(sfEvent.risk, int):
            raise TypeError(f"sfEvent.risk is {type(sfEvent.risk)}; expected int()")
        if not 0 <= sfEvent.risk <= 100:
            raise ValueError(f"sfEvent.risk value is {type(sfEvent.risk)}; expected 0 - 100")
        if not isinstance(sfEvent.sourceEvent, SpiderFootEvent) and sfEvent.eventType != "ROOT":
            raise TypeError(f"sfEvent.sourceEvent is {type(sfEvent.sourceEvent)}; expected str()")
        if not isinstance(sfEvent.sourceEventHash, str):
            raise TypeError(f"sfEvent.sourceEventHash is {type(sfEvent.sourceEventHash)}; expected str()")
        if not sfEvent.sourceEventHash:
            raise ValueError("sfEvent.sourceEventHash is empty")
        storeData = sfEvent.data
        if isinstance(truncateSize, int) and truncateSize > 0:
            storeData = storeData[0:truncateSize]
        # Always store generated as int (ms)
        generated_ms = int(sfEvent.generated)
        qry = "INSERT INTO tbl_scan_results (scan_instance_id, hash, type, generated, confidence, visibility, risk, module, data, source_event_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        qvals = [instanceId, sfEvent.hash, sfEvent.eventType, generated_ms, sfEvent.confidence, sfEvent.visibility, sfEvent.risk, sfEvent.module, storeData, sfEvent.sourceEventHash]
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvals)
                self.conn.commit()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError(f"SQL error encountered when storing event data ({self.dbh})") from e

    def scanElementSourcesDirect(self, instanceId: str, elementIdList: list) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(elementIdList, list):
            raise TypeError(f"elementIdList is {type(elementIdList)}; expected list()")
        hashIds = []
        for hashId in elementIdList:
            if not hashId:
                continue
            if not hashId.isalnum():
                continue
            hashIds.append(hashId)
        qry = "SELECT ROUND(c.generated) AS generated, c.data, s.data as 'source_data', c.module, c.type, c.confidence, c.visibility, c.risk, c.hash, c.source_event_hash, t.event_descr, t.event_type, s.scan_instance_id, c.false_positive as 'fp', s.false_positive as 'parent_fp', s.type, s.module, st.event_type as 'source_entity_type' FROM tbl_scan_results c, tbl_scan_results s, tbl_event_types t, tbl_event_types st WHERE c.scan_instance_id = ? AND c.source_event_hash = s.hash AND s.scan_instance_id = c.scan_instance_id AND st.event = s.type AND t.event = c.type AND c.hash in ('%s')" % "','".join(hashIds)
        qvars = [instanceId]
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when getting source element IDs") from e

    def scanElementChildrenDirect(self, instanceId: str, elementIdList: list) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(elementIdList, list):
            raise TypeError(f"elementIdList is {type(elementIdList)}; expected list()")
        hashIds = []
        for hashId in elementIdList:
            if not hashId:
                continue
            if not hashId.isalnum():
                continue
            hashIds.append(hashId)
        qry = "SELECT ROUND(c.generated) AS generated, c.data, s.data as 'source_data', c.module, c.type, c.confidence, c.visibility, c.risk, c.hash, c.source_event_hash, t.event_descr, t.event_type, s.scan_instance_id, c.false_positive as 'fp', s.false_positive as 'parent_fp' FROM tbl_scan_results c, tbl_scan_results s, tbl_event_types t WHERE c.scan_instance_id = ? AND c.source_event_hash = s.hash AND s.scan_instance_id = c.scan_instance_id AND t.event = c.type AND s.hash in ('%s')" % "','".join(hashIds)
        qvars = [instanceId]
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when getting child element IDs") from e

    def scanElementSourcesAll(self, instanceId: str, childData: list) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(childData, list):
            raise TypeError(f"childData is {type(childData)}; expected list()")
        if not childData:
            raise ValueError("childData is empty")
        keepGoing = True
        nextIds = list()
        datamap = dict()
        pc = dict()
        for row in childData:
            parentId = row[9]
            childId = row[8]
            datamap[childId] = row
            if parentId in pc:
                if childId not in pc[parentId]:
                    pc[parentId].append(childId)
            else:
                pc[parentId] = [childId]
            if parentId not in nextIds:
                nextIds.append(parentId)
        while keepGoing:
            parentSet = self.scanElementSourcesDirect(instanceId, nextIds)
            nextIds = list()
            keepGoing = False
            for row in parentSet:
                parentId = row[9]
                childId = row[8]
                datamap[childId] = row
                if parentId in pc:
                    if childId not in pc[parentId]:
                        pc[parentId].append(childId)
                else:
                    pc[parentId] = [childId]
                if parentId not in nextIds:
                    nextIds.append(parentId)
                if parentId != "ROOT":
                    keepGoing = True
        datamap[parentId] = row
        return [datamap, pc]

    def scanElementChildrenAll(self, instanceId: str, parentIds: list) -> list:
        if not isinstance(instanceId, str):
            raise TypeError(f"instanceId is {type(instanceId)}; expected str()")
        if not isinstance(parentIds, list):
            raise TypeError(f"parentIds is {type(parentIds)}; expected list()")
        datamap = list()
        keepGoing = True
        nextIds = list()
        nextSet = self.scanElementChildrenDirect(instanceId, parentIds)
        for row in nextSet:
            datamap.append(row[8])
        for row in nextSet:
            if row[8] not in nextIds:
                nextIds.append(row[8])
        while keepGoing:
            nextSet = self.scanElementChildrenDirect(instanceId, nextIds)
            if nextSet is None or len(nextSet) == 0:
                keepGoing = False
                break
            for row in nextSet:
                datamap.append(row[8])
                nextIds = list()
                nextIds.append(row[8])
        return datamap

    def get_sources(self, scan_id: str, event_hash: str) -> list:
        qry = """
            SELECT s.hash, s.type, s.data, s.module, s.generated, s.source_event_hash
            FROM tbl_scan_results c
            JOIN tbl_scan_results s
              ON c.source_event_hash = s.hash
            WHERE c.scan_instance_id = ?
              AND c.hash = ?
              AND c.source_event_hash != 'ROOT'
        """
        qvars = [scan_id, event_hash]
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                rows = self.dbh.fetchall()
                sources = []
                for row in rows:
                    sources.append({
                        'hash': row[0],
                        'type': row[1],
                        'data': row[2],
                        'module': row[3],
                        'generated': row[4],
                        'source_event_hash': row[5]
                    })
                return sources
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when fetching event sources") from e

    def get_entities(self, scan_id: str, event_hash: str) -> list:
        qry = """
            SELECT c.hash, c.type, c.data, c.module, c.generated, c.source_event_hash
            FROM tbl_scan_results c
            WHERE c.scan_instance_id = ?
              AND c.source_event_hash = ?
              AND c.type IN (
                SELECT event FROM tbl_event_types WHERE event_type = 'ENTITY'
              )
        """
        qvars = [scan_id, event_hash]
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                rows = self.dbh.fetchall()
                entities = []
                for row in rows:
                    entities.append({
                        'hash': row[0],
                        'type': row[1],
                        'data': row[2],
                        'module': row[3],
                        'generated': row[4],
                        'source_event_hash': row[5]
                    })
                return entities
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when fetching entity events") from e

    def search(self, criteria: dict, filterFp: bool = False) -> list:
        """
        Search for events in the scan results matching the given criteria dict.
        Supported keys: scan_id (required), type, data, module, start_date, end_date.
        Returns a list of matching rows, similar to the legacy API.
        """
        if not isinstance(criteria, dict):
            raise TypeError("criteria must be a dict")
        if not criteria:
            raise ValueError("criteria must not be empty")
        scan_id = criteria.get('scan_id')
        if not scan_id or not isinstance(scan_id, str):
            raise ValueError("criteria must include a valid 'scan_id' string")
        # Legacy tuple order: generated, data, module, hash, type, source_event_hash, confidence, visibility, risk
        qry = ("SELECT ROUND(generated) AS generated, data, module, hash, type, source_event_hash, confidence, visibility, risk "
               "FROM tbl_scan_results WHERE scan_instance_id = ?")
        qvars = [scan_id]
        if 'type' in criteria and criteria['type']:
            qry += " AND type = ?"
            qvars.append(criteria['type'])
        if 'data' in criteria and criteria['data']:
            qry += " AND data = ?"
            qvars.append(criteria['data'])
        if 'module' in criteria and criteria['module']:
            qry += " AND module = ?"
            qvars.append(criteria['module'])
        if 'start_date' in criteria and criteria['start_date']:
            qry += " AND generated >= ?"
            start = criteria['start_date']
            if start > 1000000000000:  # already ms
                qvars.append(start)
            else:
                qvars.append(int(start * 1000))
        if 'end_date' in criteria and criteria['end_date']:
            qry += " AND generated <= ?"
            end = criteria['end_date']
            if end > 1000000000000:
                qvars.append(end)
            else:
                qvars.append(int(end * 1000))
        if filterFp:
            qry += " AND false_positive <> 1"
        qry += " ORDER BY generated DESC"
        with self.dbhLock:
            try:
                self.dbh.execute(qry, qvars)
                return self.dbh.fetchall()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when searching events") from e

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
