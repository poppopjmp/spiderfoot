"""Structural tests for the core endpoints of spiderfoot.api.routers.scan.

scan.py is the largest router and delegates everything to ScanService (injected
via Depends(get_scan_service)). These tests override that dependency with an
in-memory FakeScanService so the high-traffic read/mutate endpoints — and their
404 paths — are exercised without a database. The full run_scan/iac/export
pipelines are out of scope (integration-tested elsewhere).
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.scan import router
from spiderfoot.api.dependencies import get_api_key, get_scan_service, get_app_config
from test.unit.utils.fake_scan_service import FakeScanService, FakeScanRecord


@pytest.fixture
def svc():
    s = FakeScanService()
    s.add_scan(
        FakeScanRecord("scan-1", name="My Scan", target="example.com",
                       status="FINISHED"),
        events=[
            # (generated, data, module, hash, type, src_hash, conf, vis, risk)
            (1, "8.8.8.8", "sfp_dns", "h1", "IP_ADDRESS", "ROOT", 100, 100, 0),
            (2, "a.example.com", "sfp_dns", "h2", "INTERNET_NAME", "h1", 100, 100, 0),
        ],
        logs=[(1, "INFO", "started", "core")],
    )
    return s


@pytest.fixture
def client(svc):
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.dependency_overrides[get_scan_service] = lambda: svc
    # get_app_config is called directly by a few handlers (e.g. options).
    app.dependency_overrides[get_app_config] = lambda: type(
        "C", (), {"get_config": lambda self: {}})()
    app.include_router(router)
    return TestClient(app)


class TestListAndSearch:
    def test_list(self, client):
        resp = client.get("/scans")
        assert resp.status_code == 200
        # paginate wraps the dicts; our scan should be present.
        assert "scan-1" in resp.text

    def test_search_by_status(self, client):
        resp = client.get("/scans/search", params={"status": "FINISHED"})
        assert resp.status_code == 200

    def test_search_by_status_no_match(self, client):
        resp = client.get("/scans/search", params={"status": "RUNNING"})
        assert resp.status_code == 200


class TestGet:
    def test_get(self, client):
        resp = client.get("/scans/scan-1")
        assert resp.status_code == 200
        assert resp.json()["scan_id"] == "scan-1"

    def test_get_unknown_404(self, client):
        assert client.get("/scans/nope").status_code == 404


class TestEventsAndSummary:
    def test_events(self, client):
        resp = client.get("/scans/scan-1/events")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["events"][0]["type"] == "IP_ADDRESS"

    def test_events_filter_by_type(self, client):
        resp = client.get("/scans/scan-1/events",
                         params={"event_type": "IP_ADDRESS"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_events_unknown_scan_404(self, client):
        assert client.get("/scans/nope/events").status_code == 404

    def test_summary(self, client):
        resp = client.get("/scans/scan-1/summary")
        assert resp.status_code == 200
        assert resp.json()["total_types"] == 2

    def test_summary_unknown_404(self, client):
        assert client.get("/scans/nope/summary").status_code == 404


class TestLogsAndOptions:
    def test_logs(self, client):
        resp = client.get("/scans/scan-1/logs")
        assert resp.status_code == 200

    def test_logs_unknown_404(self, client):
        assert client.get("/scans/nope/logs").status_code == 404

    def test_options(self, client):
        resp = client.get("/scans/scan-1/options")
        assert resp.status_code == 200


class TestMutations:
    def test_stop(self, client):
        resp = client.post("/scans/scan-1/stop")
        assert resp.status_code == 200

    def test_stop_unknown_404(self, client):
        assert client.post("/scans/nope/stop").status_code == 404

    def test_delete(self, client):
        assert client.delete("/scans/scan-1").status_code == 200
        assert client.get("/scans/scan-1").status_code == 404

    def test_delete_unknown_404(self, client):
        assert client.delete("/scans/nope").status_code == 404


class TestTags:
    def test_set_and_replace_tags(self, client):
        resp = client.put("/scans/scan-1/tags", json=["Prod", "  prod ", "web"])
        assert resp.status_code == 200
        tags = resp.json()["tags"]
        # Normalised: lowercased, stripped, deduplicated, sorted.
        assert tags == ["prod", "web"]

    def test_tags_unknown_scan_404(self, client):
        assert client.put("/scans/nope/tags", json=["x"]).status_code == 404
