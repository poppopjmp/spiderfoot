"""Tests for spiderfoot.api.routers.frontend_data.

These endpoints transform request-supplied data (module metrics, events, geo
points, scan diffs) via in-process services — no database — so they are tested
directly through a TestClient. Covers the happy paths, the facet registry, and
request validation (422 on missing required fields).
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.frontend_data import router
from spiderfoot.api.dependencies import get_api_key


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


class TestModuleHealth:
    def test_aggregates_metrics(self, client):
        resp = client.post("/frontend/module-health", json={"metrics": [
            {"module_name": "sfp_dns", "events_processed": 10,
             "events_produced": 5, "error_count": 1, "total_duration": 2.0,
             "status": "running"},
        ]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_modules"] == 1
        assert body["total_events_processed"] == 10

    def test_missing_metrics_422(self, client):
        assert client.post("/frontend/module-health", json={}).status_code == 422


class TestTimeline:
    def test_ingests_events(self, client):
        resp = client.post("/frontend/timeline", json={"events": [
            {"timestamp": 1, "event_type": "IP_ADDRESS", "data": "8.8.8.8",
             "module": "m", "scan_id": "s", "severity": "info"},
        ]})
        assert resp.status_code == 200
        assert resp.json()["events_ingested"] == 1


class TestFilter:
    def test_filters_by_event_type(self, client):
        resp = client.post("/frontend/results/filter", json={
            "results": [
                {"event_type": "IP_ADDRESS", "data": "8.8.8.8", "module": "m",
                 "severity": "info", "confidence": 80},
            ],
            "event_types": ["IP_ADDRESS"],
        })
        assert resp.status_code == 200
        assert "results" in resp.json()

    def test_missing_results_422(self, client):
        assert client.post("/frontend/results/filter",
                          json={}).status_code == 422


class TestThreatMap:
    def test_clusters_points(self, client):
        resp = client.post("/frontend/threat-map", json={"points": [
            {"latitude": 1.0, "longitude": 2.0, "label": "x",
             "event_type": "IP", "data": "d", "count": 1, "risk_level": "high"},
        ]})
        assert resp.status_code == 200
        assert resp.json()["total_points"] == 1


class TestScanDiff:
    def test_summarises_diff(self, client):
        resp = client.post("/frontend/scan-diff", json={
            "added": [{"data": "x"}], "removed": [], "changed": [],
            "unchanged_count": 5,
        })
        assert resp.status_code == 200
        stats = resp.json()["stats"]
        assert stats["added"] == 1
        assert stats["total_findings"] == 6


class TestFacets:
    def test_facet_registry(self, client):
        assert client.get("/frontend/facets").status_code == 200
