"""
Tests for Cycle 28 — Visualization Service Facade + Router Wiring.

Covers:
  - VisualizationService data aggregation (graph, multi-graph, summary,
    timeline, heatmap)
  - Error handling (missing scans, empty results)
  - Router endpoints via Starlette TestClient with dependency override
"""

from __future__ import annotations

from datetime import datetime, timedelta
from dataclasses import dataclass, field

import pytest
from starlette.testclient import TestClient

from spiderfoot.visualization_service import (
    VisualizationService,
    VisualizationServiceError,
)


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

@dataclass
class FakeScanRecord:
    scan_id: str = "scan-1"
    name: str = "Test Scan"
    target: str = "example.com"
    status: str = "COMPLETED"

    def to_dict(self):
        return {
            "scan_id": self.scan_id,
            "name": self.name,
            "target": self.target,
            "status": self.status,
        }


class FakeRepo:
    """Minimal ScanRepository stand-in."""

    __bool__ = True

    def __init__(self):
        self._scans = {}

    def add(self, record: FakeScanRecord):
        self._scans[record.scan_id] = record

    def get_scan(self, scan_id):
        return self._scans.get(scan_id)

    def close(self):
        pass


class FakeDbh:
    """Minimal SpiderFootDb stand-in."""

    __bool__ = True

    def __init__(self):
        self._results = {}  # scan_id -> list of event rows
        self._summaries = {}  # scan_id -> list of summary rows
        self._scans = {}  # scan_id -> tuple row

    def scanInstanceGet(self, scan_id):
        return self._scans.get(scan_id)

    def scanResultEvent(self, scan_id, event_type=None):
        rows = self._results.get(scan_id, [])
        if event_type:
            return [r for r in rows if len(r) > 3 and r[3] == event_type]
        return rows

    def scanResultSummary(self, scan_id, group_by="type"):
        return self._summaries.get(scan_id, [])


def _make_service(scans=None, results=None, summaries=None):
    """Helper to create a VisualizationService with test data."""
    repo = FakeRepo()
    dbh = FakeDbh()

    for rec in (scans or []):
        repo.add(rec)

    for scan_id, rows in (results or {}).items():
        dbh._results[scan_id] = rows

    for scan_id, rows in (summaries or {}).items():
        dbh._summaries[scan_id] = rows

    return VisualizationService(scan_repo=repo, dbh=dbh)


# -----------------------------------------------------------------------
# VisualizationService Unit Tests
# -----------------------------------------------------------------------

class TestVisualizationServiceGraph:
    """get_graph_data()"""

    def test_returns_info_and_results(self):
        rec = FakeScanRecord(scan_id="s1")
        results = {"s1": [("ts1", "data1", "mod1", "IP_ADDRESS")]}
        svc = _make_service(scans=[rec], results=results)
        info, rows = svc.get_graph_data("s1")
        assert info["scan_id"] == "s1"
        assert len(rows) == 1

    def test_not_found_raises(self):
        svc = _make_service()
        with pytest.raises(VisualizationServiceError, match="not found"):
            svc.get_graph_data("missing")

    def test_filter_type(self):
        rec = FakeScanRecord(scan_id="s1")
        results = {
            "s1": [
                ("ts1", "d1", "mod1", "IP_ADDRESS"),
                ("ts2", "d2", "mod1", "DOMAIN"),
            ]
        }
        svc = _make_service(scans=[rec], results=results)
        _info, rows = svc.get_graph_data("s1", event_type="DOMAIN")
        assert len(rows) == 1
        assert rows[0][3] == "DOMAIN"

    def test_empty_results(self):
        rec = FakeScanRecord(scan_id="s1")
        svc = _make_service(scans=[rec])
        info, rows = svc.get_graph_data("s1")
        assert rows == []


class TestVisualizationServiceMultiGraph:
    """get_multi_scan_graph_data()"""

    def test_merges_results(self):
        r1 = FakeScanRecord(scan_id="s1")
        r2 = FakeScanRecord(scan_id="s2", name="Scan 2")
        results = {
            "s1": [("t1", "d", "m", "IP_ADDRESS")],
            "s2": [("t2", "d", "m", "DOMAIN"), ("t3", "d", "m", "DOMAIN")],
        }
        svc = _make_service(scans=[r1, r2], results=results)
        valid_ids, all_rows = svc.get_multi_scan_graph_data(["s1", "s2"])
        assert valid_ids == ["s1", "s2"]
        assert len(all_rows) == 3

    def test_skips_invalid(self):
        r1 = FakeScanRecord(scan_id="s1")
        results = {"s1": [("t", "d", "m", "T")]}
        svc = _make_service(scans=[r1], results=results)
        valid_ids, rows = svc.get_multi_scan_graph_data(["s1", "missing"])
        assert valid_ids == ["s1"]
        assert len(rows) == 1

    def test_all_invalid_returns_empty(self):
        svc = _make_service()
        valid_ids, rows = svc.get_multi_scan_graph_data(["x", "y"])
        assert valid_ids == []
        assert rows == []


class TestVisualizationServiceSummary:
    """get_summary_data()"""

    def test_group_by_type(self):
        rec = FakeScanRecord(scan_id="s1")
        summaries = {
            "s1": [
                ("IP_ADDRESS", "mod1", "x", "INFO", 5),
                ("DOMAIN", "mod2", "x", "INFO", 3),
            ]
        }
        svc = _make_service(scans=[rec], summaries=summaries)
        result = svc.get_summary_data("s1", group_by="type")
        assert result["data"]["labels"] == ["IP_ADDRESS", "DOMAIN"]
        assert result["data"]["values"] == [5, 3]
        assert result["data"]["total"] == 8

    def test_group_by_module(self):
        rec = FakeScanRecord(scan_id="s1")
        summaries = {"s1": [("T", "sfp_dns", "x", "LOW", 10)]}
        svc = _make_service(scans=[rec], summaries=summaries)
        result = svc.get_summary_data("s1", group_by="module")
        assert result["data"]["labels"] == ["sfp_dns"]
        assert result["data"]["values"] == [10]

    def test_not_found(self):
        svc = _make_service()
        with pytest.raises(VisualizationServiceError):
            svc.get_summary_data("nope")

    def test_empty_summary(self):
        rec = FakeScanRecord(scan_id="s1")
        svc = _make_service(scans=[rec])
        result = svc.get_summary_data("s1")
        assert result["data"]["total"] == 0
        assert result["data"]["labels"] == []


class TestVisualizationServiceTimeline:
    """get_timeline_data()"""

    def test_hourly_buckets(self):
        rec = FakeScanRecord(scan_id="s1")
        ts1 = datetime(2025, 1, 15, 10, 5, 0)
        ts2 = datetime(2025, 1, 15, 10, 30, 0)
        ts3 = datetime(2025, 1, 15, 11, 0, 0)
        results = {
            "s1": [
                (ts1, "d", "m", "T"),
                (ts2, "d", "m", "T"),
                (ts3, "d", "m", "T"),
            ]
        }
        svc = _make_service(scans=[rec], results=results)
        out = svc.get_timeline_data("s1", interval="hour")
        assert "2025-01-15 10:00" in out["timeline"]["timestamps"]
        assert "2025-01-15 11:00" in out["timeline"]["timestamps"]
        assert out["total_events"] == 3

    def test_daily_buckets(self):
        rec = FakeScanRecord(scan_id="s1")
        ts1 = datetime(2025, 1, 15, 10, 0)
        ts2 = datetime(2025, 1, 16, 12, 0)
        results = {"s1": [(ts1, "d", "m", "T"), (ts2, "d", "m", "T")]}
        svc = _make_service(scans=[rec], results=results)
        out = svc.get_timeline_data("s1", interval="day")
        assert out["timeline"]["timestamps"] == ["2025-01-15", "2025-01-16"]
        assert out["timeline"]["counts"] == [1, 1]

    def test_weekly_buckets(self):
        rec = FakeScanRecord(scan_id="s1")
        # 2025-01-15 is a Wednesday → week starts Mon 2025-01-13
        ts1 = datetime(2025, 1, 15, 10, 0)
        results = {"s1": [(ts1, "d", "m", "T")]}
        svc = _make_service(scans=[rec], results=results)
        out = svc.get_timeline_data("s1", interval="week")
        assert out["timeline"]["timestamps"] == ["2025-01-13"]

    def test_not_found(self):
        svc = _make_service()
        with pytest.raises(VisualizationServiceError):
            svc.get_timeline_data("nope")

    def test_empty_results(self):
        rec = FakeScanRecord(scan_id="s1")
        svc = _make_service(scans=[rec])
        out = svc.get_timeline_data("s1")
        assert out["total_events"] == 0


class TestVisualizationServiceHeatmap:
    """get_heatmap_data()"""

    def test_builds_matrix(self):
        rec = FakeScanRecord(scan_id="s1")
        results = {
            "s1": [
                ("t", "d", "mod1", "IP_ADDRESS"),
                ("t", "d", "mod1", "DOMAIN"),
                ("t", "d", "mod2", "IP_ADDRESS"),
            ]
        }
        svc = _make_service(scans=[rec], results=results)
        out = svc.get_heatmap_data("s1", dimension_x="module", dimension_y="type")
        assert sorted(out["heatmap"]["x_labels"]) == ["mod1", "mod2"]
        assert sorted(out["heatmap"]["y_labels"]) == ["DOMAIN", "IP_ADDRESS"]
        # Matrix should have correct counts
        assert out["dimensions"]["x"] == "module"
        assert out["dimensions"]["y"] == "type"

    def test_not_found(self):
        svc = _make_service()
        with pytest.raises(VisualizationServiceError):
            svc.get_heatmap_data("nope")

    def test_empty(self):
        rec = FakeScanRecord(scan_id="s1")
        svc = _make_service(scans=[rec])
        out = svc.get_heatmap_data("s1")
        assert out["heatmap"]["matrix"] == []


class TestVisualizationServiceEdgeCases:
    """Edge cases and close()."""

    def test_no_datasource(self):
        svc = VisualizationService()
        with pytest.raises(VisualizationServiceError, match="No data source"):
            svc.get_graph_data("x")

    def test_close_without_repo(self):
        svc = VisualizationService()
        svc.close()  # should not raise

    def test_close_with_repo(self):
        repo = FakeRepo()
        svc = VisualizationService(scan_repo=repo)
        svc.close()  # calls repo.close()

    def test_epoch_timestamps(self):
        """Timeline should handle float-epoch timestamps."""
        rec = FakeScanRecord(scan_id="s1")
        ts = datetime(2025, 1, 15, 10, 0).timestamp()
        results = {"s1": [(ts, "d", "m", "T")]}
        svc = _make_service(scans=[rec], results=results)
        out = svc.get_timeline_data("s1")
        assert out["total_events"] == 1


# -----------------------------------------------------------------------
# Router Integration Tests
# -----------------------------------------------------------------------

def _build_test_app(svc):
    """Build a minimal FastAPI app with dependency overrides."""
    from fastapi import FastAPI
    from spiderfoot.api.routers.visualization import router
    from spiderfoot.api.dependencies import get_visualization_service, optional_auth

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_visualization_service] = lambda: svc
    app.dependency_overrides[optional_auth] = lambda: None
    return app


class TestVisualizationRouter:
    """Router endpoint integration tests using TestClient."""

    def _client(self, svc):
        app = _build_test_app(svc)
        return TestClient(app)

    # -- graph --

    def test_graph_ok(self):
        rec = FakeScanRecord(scan_id="s1")
        results = {"s1": [("ts", "d", "mod", "T")]}
        svc = _make_service(scans=[rec], results=results)

        # Patch SpiderFootHelpers to avoid real graph building
        import spiderfoot.api.routers.visualization as viz_mod
        orig = viz_mod.SpiderFootHelpers

        class FakeHelpers:
            @staticmethod
            def buildGraphJson(*a, **kw):
                return '{"nodes":[],"edges":[]}'

            @staticmethod
            def buildGraphGexf(*a, **kw):
                return "<gexf/>"

        viz_mod.SpiderFootHelpers = FakeHelpers
        try:
            client = self._client(svc)
            resp = client.get("/visualization/graph/s1")
            assert resp.status_code == 200
            assert "nodes" in resp.json()
        finally:
            viz_mod.SpiderFootHelpers = orig

    def test_graph_404(self):
        svc = _make_service()
        client = self._client(svc)
        resp = client.get("/visualization/graph/missing")
        assert resp.status_code == 404

    def test_graph_gexf(self):
        rec = FakeScanRecord(scan_id="s1")
        svc = _make_service(scans=[rec], results={"s1": [("t", "d", "m", "T")]})

        import spiderfoot.api.routers.visualization as viz_mod
        orig = viz_mod.SpiderFootHelpers

        class FakeHelpers:
            @staticmethod
            def buildGraphGexf(*a, **kw):
                return "<gexf/>"

            @staticmethod
            def buildGraphJson(*a, **kw):
                return "{}"

        viz_mod.SpiderFootHelpers = FakeHelpers
        try:
            client = self._client(svc)
            resp = client.get("/visualization/graph/s1?format=gexf")
            assert resp.status_code == 200
            assert "gexf" in resp.text
        finally:
            viz_mod.SpiderFootHelpers = orig

    # -- multi graph --

    def test_multi_graph_ok(self):
        r1 = FakeScanRecord(scan_id="s1")
        r2 = FakeScanRecord(scan_id="s2")
        svc = _make_service(
            scans=[r1, r2],
            results={"s1": [("t", "d", "m", "T")], "s2": [("t", "d", "m", "T")]},
        )

        import spiderfoot.api.routers.visualization as viz_mod
        orig = viz_mod.SpiderFootHelpers

        class FakeHelpers:
            @staticmethod
            def buildGraphGexf(*a, **kw):
                return "<gexf/>"

            @staticmethod
            def buildGraphJson(*a, **kw):
                return '{"merged": true}'

        viz_mod.SpiderFootHelpers = FakeHelpers
        try:
            client = self._client(svc)
            resp = client.get("/visualization/graph/multi?scan_ids=s1,s2&format=json")
            assert resp.status_code == 200
        finally:
            viz_mod.SpiderFootHelpers = orig

    def test_multi_graph_no_valid(self):
        svc = _make_service()
        client = self._client(svc)
        resp = client.get("/visualization/graph/multi?scan_ids=x,y")
        assert resp.status_code == 404

    def test_multi_graph_no_ids(self):
        svc = _make_service()
        client = self._client(svc)
        resp = client.get("/visualization/graph/multi?scan_ids=")
        assert resp.status_code == 400

    # -- summary --

    def test_summary_ok(self):
        rec = FakeScanRecord(scan_id="s1")
        summaries = {"s1": [("IP_ADDRESS", "mod1", "x", "INFO", 5)]}
        svc = _make_service(scans=[rec], summaries=summaries)
        client = self._client(svc)
        resp = client.get("/visualization/summary/s1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 5

    def test_summary_404(self):
        svc = _make_service()
        client = self._client(svc)
        resp = client.get("/visualization/summary/missing")
        assert resp.status_code == 404

    # -- timeline --

    def test_timeline_ok(self):
        rec = FakeScanRecord(scan_id="s1")
        ts = datetime(2025, 1, 15, 10, 5)
        results = {"s1": [(ts, "d", "m", "T")]}
        svc = _make_service(scans=[rec], results=results)
        client = self._client(svc)
        resp = client.get("/visualization/timeline/s1")
        assert resp.status_code == 200
        assert resp.json()["total_events"] == 1

    def test_timeline_404(self):
        svc = _make_service()
        client = self._client(svc)
        resp = client.get("/visualization/timeline/missing")
        assert resp.status_code == 404

    # -- heatmap --

    def test_heatmap_ok(self):
        rec = FakeScanRecord(scan_id="s1")
        results = {"s1": [("t", "d", "mod1", "IP_ADDRESS")]}
        svc = _make_service(scans=[rec], results=results)
        client = self._client(svc)
        resp = client.get("/visualization/heatmap/s1")
        assert resp.status_code == 200
        body = resp.json()
        assert "matrix" in body["heatmap"]

    def test_heatmap_404(self):
        svc = _make_service()
        client = self._client(svc)
        resp = client.get("/visualization/heatmap/missing")
        assert resp.status_code == 404
