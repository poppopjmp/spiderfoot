"""
Tests for Cycle 29 — Scan Service Facade Phase 2.

Covers:
  - New ScanService methods (events, search, correlations, logs,
    metadata/notes/archive, false-positive, clear, scan_options)
  - All 25 router endpoints via TestClient with dependency override
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import pytest
from starlette.testclient import TestClient

from spiderfoot.scan.scan_service_facade import ScanService, ScanServiceError
from spiderfoot.db.repositories.scan_repository import ScanRecord


# -----------------------------------------------------------------------
# Fake doubles
# -----------------------------------------------------------------------

class FakeDbh:
    """Minimal SpiderFootDb stand-in."""
    __bool__ = True

    def __init__(self):
        self._events = {}  # scan_id -> list of rows
        self._summaries = {}
        self._scans = {}  # scan_id -> tuple row
        self._configs = {}  # scan_id -> dict
        self._logs = {}
        self._correlations = {}
        self._metadata = {}
        self._notes = {}
        self._fp_results = {}
        self._deleted_results = set()

    def scanInstanceGet(self, scan_id):
        return self._scans.get(scan_id)

    def scanResultEvent(self, scan_id, event_type=None, filterFp=False):
        rows = self._events.get(scan_id, [])
        if event_type and event_type != "ALL":
            return [r for r in rows if len(r) > 4 and r[4] == event_type]
        return rows

    def scanResultSummary(self, scan_id, group_by="type"):
        return self._summaries.get(scan_id, [])

    def search(self, criteria):
        scan_id = criteria.get("scan_id", "")
        return self._events.get(scan_id, [])

    def scanConfigGet(self, scan_id):
        return self._configs.get(scan_id, {})

    def scanConfigSet(self, scan_id, config):
        self._configs[scan_id] = config

    def scanConfigDelete(self, scan_id):
        self._configs.pop(scan_id, None)

    def scanInstanceCreate(self, scan_id, name, target):
        self._scans[scan_id] = (name, target, "CREATED", 0, 0, "CREATED")

    def scanInstanceDelete(self, scan_id):
        self._scans.pop(scan_id, None)

    def scanResultDelete(self, scan_id):
        self._deleted_results.add(scan_id)

    def scanLogs(self, scan_id, limit=None, from_row_id=0, reverse=False):
        return self._logs.get(scan_id, [])

    def scanCorrelationList(self, scan_id):
        return self._correlations.get(scan_id, [])

    def scanMetadataGet(self, scan_id):
        return self._metadata.get(scan_id, {})

    def scanMetadataSet(self, scan_id, meta):
        self._metadata[scan_id] = meta

    def scanNotesGet(self, scan_id):
        return self._notes.get(scan_id, "")

    def scanNotesSet(self, scan_id, notes):
        self._notes[scan_id] = notes

    def scanElementSourcesDirect(self, scan_id, result_ids):
        return []

    def scanElementChildrenAll(self, scan_id, result_ids):
        return []

    def scanResultsUpdateFP(self, scan_id, all_ids, fp):
        self._fp_results[scan_id] = (all_ids, fp)
        return True


class FakeRepo:
    __bool__ = True

    def __init__(self, dbh=None):
        self._scans: dict[str, ScanRecord] = {}
        self._dbh = dbh if dbh is not None else FakeDbh()

    def list_scans(self):
        return list(self._scans.values())

    def get_scan(self, scan_id):
        return self._scans.get(scan_id)

    def create_scan(self, scan_id, name, target):
        self._scans[scan_id] = ScanRecord(
            scan_id=scan_id, name=name, target=target, status="CREATED",
        )

    def delete_scan(self, scan_id):
        return self._scans.pop(scan_id, None) is not None

    def update_status(self, scan_id, status, *, started=None, ended=None):
        if scan_id in self._scans:
            self._scans[scan_id].status = status

    def get_config(self, scan_id):
        return self._dbh.scanConfigGet(scan_id)

    def set_config(self, scan_id, config_data):
        self._dbh.scanConfigSet(scan_id, config_data)

    def get_scan_log(self, scan_id, **kw):
        return self._dbh.scanLogs(scan_id)

    def get_scan_errors(self, scan_id, limit=0):
        return []

    def close(self):
        pass


def _make_svc(scans=None, events=None, configs=None, logs=None,
              correlations=None, metadata=None, notes=None):
    """Build a ScanService with pre-populated test data."""
    dbh = FakeDbh()
    repo = FakeRepo(dbh=dbh)

    for rec in (scans or []):
        repo._scans[rec.scan_id] = rec
        dbh._scans[rec.scan_id] = (
            rec.name, rec.target, rec.status, 0, 0, rec.status,
        )

    for sid, rows in (events or {}).items():
        dbh._events[sid] = rows

    for sid, cfg in (configs or {}).items():
        dbh._configs[sid] = cfg

    for sid, log_rows in (logs or {}).items():
        dbh._logs[sid] = log_rows

    for sid, corr_rows in (correlations or {}).items():
        dbh._correlations[sid] = corr_rows

    for sid, meta in (metadata or {}).items():
        dbh._metadata[sid] = meta

    for sid, note in (notes or {}).items():
        dbh._notes[sid] = note

    return ScanService(repo, dbh=dbh)


REC = ScanRecord(scan_id="s1", name="Test", target="example.com", status="COMPLETED")


# -----------------------------------------------------------------------
# ScanService — new method unit tests  (Cycle 29)
# -----------------------------------------------------------------------

class TestScanServiceEvents:

    def test_get_events(self):
        svc = _make_svc(scans=[REC], events={"s1": [
            (1, "d", "mod", "IP", "IP_ADDRESS", 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ]})
        rows = svc.get_events("s1")
        assert len(rows) == 1

    def test_get_events_with_type_filter(self):
        svc = _make_svc(scans=[REC], events={"s1": [
            (1, "d1", "m", "s", "IP_ADDRESS", 0, 0, 0, 0, 0, 0, 0, 0, 0),
            (2, "d2", "m", "s", "DOMAIN", 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ]})
        rows = svc.get_events("s1", "DOMAIN")
        assert len(rows) == 1

    def test_search_events(self):
        svc = _make_svc(scans=[REC], events={"s1": [(1, "data", "m", "s")]})
        rows = svc.search_events("s1", event_type="T")
        assert isinstance(rows, list)

    def test_get_correlations(self):
        svc = _make_svc(scans=[REC], correlations={"s1": [("rule1", "corr", "HIGH", "desc")]})
        rows = svc.get_correlations("s1")
        assert rows[0][0] == "rule1"

    def test_get_scan_logs(self):
        svc = _make_svc(scans=[REC], logs={"s1": [("2025-01-01", "mod", "INFO", "msg", "e1")]})
        rows = svc.get_scan_logs("s1")
        assert len(rows) == 1


class TestScanServiceMetadata:

    def test_get_metadata(self):
        svc = _make_svc(scans=[REC], metadata={"s1": {"key": "val"}})
        assert svc.get_metadata("s1") == {"key": "val"}

    def test_set_metadata(self):
        svc = _make_svc(scans=[REC])
        svc.set_metadata("s1", {"x": 1})
        assert svc.get_metadata("s1") == {"x": 1}

    def test_get_notes(self):
        svc = _make_svc(scans=[REC], notes={"s1": "my note"})
        assert svc.get_notes("s1") == "my note"

    def test_set_notes(self):
        svc = _make_svc(scans=[REC])
        svc.set_notes("s1", "hello")
        assert svc.get_notes("s1") == "hello"

    def test_archive(self):
        svc = _make_svc(scans=[REC])
        svc.archive("s1")
        assert svc.get_metadata("s1")["archived"] is True

    def test_unarchive(self):
        svc = _make_svc(scans=[REC], metadata={"s1": {"archived": True}})
        svc.unarchive("s1")
        assert svc.get_metadata("s1")["archived"] is False


class TestScanServiceResults:

    def test_clear_results(self):
        svc = _make_svc(scans=[REC])
        svc.clear_results("s1")
        assert "s1" in svc._dbh._deleted_results

    def test_set_false_positive_success(self):
        rec = ScanRecord(scan_id="s1", name="T", target="t", status="FINISHED")
        dbh = FakeDbh()
        dbh._scans["s1"] = ("T", "t", "FINISHED", 0, 0, "FINISHED")
        repo = FakeRepo(dbh=dbh)
        repo._scans["s1"] = rec
        svc = ScanService(repo, dbh=dbh)
        result = svc.set_false_positive("s1", ["r1"], "1")
        assert result["status"] == "SUCCESS"

    def test_set_false_positive_not_finished(self):
        rec = ScanRecord(scan_id="s1", name="T", target="t", status="RUNNING")
        dbh = FakeDbh()
        dbh._scans["s1"] = ("T", "t", "RUNNING", 0, 0, "RUNNING")
        repo = FakeRepo(dbh=dbh)
        repo._scans["s1"] = rec
        svc = ScanService(repo, dbh=dbh)
        result = svc.set_false_positive("s1", ["r1"], "1")
        assert result["status"] == "WARNING"


class TestScanServiceOptions:

    def test_get_scan_options(self):
        svc = _make_svc(
            scans=[REC],
            configs={"s1": {"_modulesenabled": "sfp_dns,sfp_http", "opt1": "val1"}},
        )
        opts = svc.get_scan_options("s1", {"__globaloptdescs__": {"opt1": "Option 1"}})
        assert opts["meta"][0] == "Test"
        assert opts["configdesc"]["opt1"] == "Option 1"

    def test_scan_options_not_found(self):
        svc = _make_svc()
        assert svc.get_scan_options("nope", {}) == {}


# -----------------------------------------------------------------------
# Router integration tests
# -----------------------------------------------------------------------

def _build_test_app(svc):
    from fastapi import FastAPI
    from spiderfoot.api.routers.scan import router
    from spiderfoot.api.dependencies import get_scan_service, optional_auth, get_api_key, get_app_config

    class FakeConfig:
        __bool__ = True
        def get_config(self):
            return {"__modules__": {}, "__globaloptdescs__": {}}

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_scan_service] = lambda: svc
    app.dependency_overrides[optional_auth] = lambda: None
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.dependency_overrides[get_app_config] = lambda: FakeConfig()
    return app


class TestScanRouterPhase2:

    def _client(self, svc):
        return TestClient(_build_test_app(svc))

    # -- list / get --

    def test_list_scans(self):
        svc = _make_svc(scans=[REC])
        resp = self._client(svc).get("/scans")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_get_scan(self):
        svc = _make_svc(scans=[REC])
        resp = self._client(svc).get("/scans/s1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test"

    def test_get_scan_404(self):
        svc = _make_svc()
        resp = self._client(svc).get("/scans/missing")
        assert resp.status_code == 404

    # -- delete --

    def test_delete_scan(self):
        svc = _make_svc(scans=[REC])
        resp = self._client(svc).delete("/scans/s1")
        assert resp.status_code == 200

    def test_delete_scan_full(self):
        svc = _make_svc(scans=[REC])
        resp = self._client(svc).delete("/scans/s1/full")
        assert resp.status_code == 200

    # -- export events --

    def test_export_events_csv(self):
        svc = _make_svc(scans=[REC], events={
            "s1": [(time.time(), "data", "src", "mod", "IP_ADDRESS",
                    0, 0, 0, 0, 0, 0, 0, 0, 0)]
        })
        resp = self._client(svc).get("/scans/s1/events/export?filetype=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_export_events_404(self):
        svc = _make_svc()
        resp = self._client(svc).get("/scans/nope/events/export")
        assert resp.status_code == 404

    def test_export_events_bad_type(self):
        svc = _make_svc(scans=[REC])
        resp = self._client(svc).get("/scans/s1/events/export?filetype=pdf")
        assert resp.status_code == 400

    # -- export multi --

    def test_export_multi(self):
        svc = _make_svc(scans=[REC], events={
            "s1": [(time.time(), "data", "src", "mod", "IP_ADDRESS",
                    0, 0, 0, 0, 0, 0, 0, 0, 0)]
        })
        resp = self._client(svc).get("/scans/export-multi?ids=s1")
        assert resp.status_code == 200

    # -- viz --

    def test_viz_json(self):
        svc = _make_svc(scans=[REC], events={"s1": []})
        import spiderfoot.api.routers.scan as scan_mod
        orig = scan_mod.SpiderFootHelpers

        class FakeHelpers:
            @staticmethod
            def buildGraphJson(*a, **kw):
                return '{"nodes":[]}'
            @staticmethod
            def buildGraphGexf(*a, **kw):
                return "<gexf/>"
            @staticmethod
            def genScanInstanceId():
                return "new-id"
            @staticmethod
            def targetTypeFromString(t):
                return "INTERNET_NAME"

        scan_mod.SpiderFootHelpers = FakeHelpers
        try:
            resp = self._client(svc).get("/scans/s1/viz?gexf=0")
            assert resp.status_code == 200
        finally:
            scan_mod.SpiderFootHelpers = orig

    def test_viz_404(self):
        svc = _make_svc()
        resp = self._client(svc).get("/scans/missing/viz")
        assert resp.status_code == 404

    # -- logs export --

    def test_export_logs(self):
        svc = _make_svc(scans=[REC], logs={
            "s1": [("2025-01-01", "mod", "INFO", "msg", "e1")]
        })
        resp = self._client(svc).get("/scans/s1/logs/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_export_logs_empty(self):
        svc = _make_svc(scans=[REC])
        resp = self._client(svc).get("/scans/s1/logs/export")
        assert resp.status_code == 404

    # -- correlations export --

    def test_export_correlations_csv(self):
        svc = _make_svc(scans=[REC], correlations={
            "s1": [("rule", "corr", "HIGH", "desc")]
        })
        resp = self._client(svc).get("/scans/s1/correlations/export?filetype=csv")
        assert resp.status_code == 200

    def test_export_correlations_404(self):
        svc = _make_svc()
        resp = self._client(svc).get("/scans/missing/correlations/export")
        assert resp.status_code == 404

    # -- scan options --

    def test_scan_options(self):
        svc = _make_svc(scans=[REC], configs={
            "s1": {"_modulesenabled": "sfp_dns", "opt": "v"}
        })
        resp = self._client(svc).get("/scans/s1/options")
        assert resp.status_code == 200
        assert "meta" in resp.json()

    # -- metadata --

    def test_get_metadata(self):
        svc = _make_svc(scans=[REC], metadata={"s1": {"k": "v"}})
        resp = self._client(svc).get("/scans/s1/metadata")
        assert resp.status_code == 200
        assert resp.json()["metadata"]["k"] == "v"

    def test_update_metadata(self):
        svc = _make_svc(scans=[REC])
        resp = self._client(svc).patch(
            "/scans/s1/metadata",
            json={"new_key": "new_val"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_metadata_404(self):
        svc = _make_svc()
        resp = self._client(svc).get("/scans/missing/metadata")
        assert resp.status_code == 404

    # -- notes --

    def test_get_notes(self):
        svc = _make_svc(scans=[REC], notes={"s1": "my note"})
        resp = self._client(svc).get("/scans/s1/notes")
        assert resp.status_code == 200
        assert resp.json()["notes"] == "my note"

    def test_update_notes(self):
        svc = _make_svc(scans=[REC])
        resp = self._client(svc).patch(
            "/scans/s1/notes",
            json="new note",
        )
        assert resp.status_code == 200

    def test_notes_404(self):
        svc = _make_svc()
        resp = self._client(svc).get("/scans/missing/notes")
        assert resp.status_code == 404

    # -- archive --

    def test_archive(self):
        svc = _make_svc(scans=[REC])
        resp = self._client(svc).post("/scans/s1/archive")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_unarchive(self):
        svc = _make_svc(scans=[REC], metadata={"s1": {"archived": True}})
        resp = self._client(svc).post("/scans/s1/unarchive")
        assert resp.status_code == 200

    def test_archive_404(self):
        svc = _make_svc()
        resp = self._client(svc).post("/scans/missing/archive")
        assert resp.status_code == 404

    # -- false positive --

    def test_false_positive(self):
        rec = ScanRecord(scan_id="s1", name="T", target="t", status="FINISHED")
        svc = _make_svc(scans=[rec])
        # The FakeDbh has status FINISHED in _scans
        resp = self._client(svc).post(
            "/scans/s1/results/falsepositive",
            json={"resultids": ["r1"], "fp": "1"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUCCESS"

    def test_false_positive_bad_flag(self):
        svc = _make_svc(scans=[REC])
        resp = self._client(svc).post(
            "/scans/s1/results/falsepositive",
            json={"resultids": ["r1"], "fp": "2"},
        )
        assert resp.status_code == 400

    # -- clear --

    def test_clear_scan(self):
        svc = _make_svc(scans=[REC])
        resp = self._client(svc).post("/scans/s1/clear")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_clear_404(self):
        svc = _make_svc()
        resp = self._client(svc).post("/scans/missing/clear")
        assert resp.status_code == 404
