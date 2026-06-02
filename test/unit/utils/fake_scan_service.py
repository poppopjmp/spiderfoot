"""In-memory fake ScanService for router unit tests.

A dependency-free stand-in for ``spiderfoot.scan.scan_service_facade.ScanService``
covering the methods the scan/reports routers call, so those endpoints can be
tested via FastAPI ``dependency_overrides[get_scan_service]`` without a database.

Only the surface exercised by the routers is implemented; extend as needed.
"""
from __future__ import annotations


class FakeScanRecord:
    """Minimal scan record with the attributes/`to_dict` the routers use."""

    def __init__(self, scan_id, name="scan", target="example.com",
                 status="FINISHED", started=1000.0, ended=1100.0):
        self.scan_id = scan_id
        self.name = name
        self.target = target
        self.status = status
        self.started = started
        self.ended = ended

    def to_dict(self):
        return {
            "id": self.scan_id,
            "scan_id": self.scan_id,
            "name": self.name,
            "target": self.target,
            "status": self.status,
            "started": self.started,
            "ended": self.ended,
        }


class FakeScanService:
    """In-memory ScanService stand-in."""

    def __init__(self):
        self._scans: dict[str, FakeScanRecord] = {}
        self._events: dict[str, list] = {}
        self._metadata: dict[str, dict] = {}
        self._logs: dict[str, list] = {}
        self.dbh = object()  # truthy placeholder; not used by mocked paths

    # -- seeding helpers (test-only) ---------------------------------------
    def add_scan(self, record: FakeScanRecord, events=None, logs=None):
        self._scans[record.scan_id] = record
        self._events[record.scan_id] = events or []
        self._logs[record.scan_id] = logs or []
        return record

    # -- read --------------------------------------------------------------
    def list_scans(self):
        return list(self._scans.values())

    def get_scan(self, scan_id):
        return self._scans.get(scan_id)

    def get_scan_state(self, scan_id):
        return {"state": self._scans[scan_id].status} if scan_id in self._scans else {}

    def get_events(self, scan_id, event_type="ALL", filter_fp=False):
        rows = self._events.get(scan_id, [])
        if event_type and event_type != "ALL":
            rows = [r for r in rows if len(r) > 4 and r[4] == event_type]
        return rows

    def get_result_summary(self, scan_id, by="type"):
        # (key, descr, last_in, total, utotal)
        rows = self._events.get(scan_id, [])
        counts: dict[str, int] = {}
        for r in rows:
            key = r[4] if len(r) > 4 else "UNKNOWN"
            counts[key] = counts.get(key, 0) + 1
        return [(k, k, 0, n, n) for k, n in counts.items()]

    def get_scan_logs(self, scan_id, limit=None, offset=0, **kwargs):
        return self._logs.get(scan_id, [])

    def get_scan_options(self, scan_id, config):
        return {"scan_id": scan_id, "options": {}}

    def get_metadata(self, scan_id):
        return self._metadata.get(scan_id, {})

    def set_metadata(self, scan_id, meta):
        self._metadata[scan_id] = meta
        return True

    # -- mutate ------------------------------------------------------------
    def delete_scan(self, scan_id):
        self._scans.pop(scan_id, None)
        return True

    def delete_scan_full(self, scan_id):
        return self.delete_scan(scan_id)

    def stop_scan(self, scan_id):
        if scan_id in self._scans:
            self._scans[scan_id].status = "ABORT-REQUESTED"
        return "ABORT-REQUESTED"

    def close(self):
        pass
