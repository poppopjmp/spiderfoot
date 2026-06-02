"""Structural tests for spiderfoot.api.routers.visualization.

VisualizationService is injected via Depends(get_visualization_service); these
tests override it with a fake that returns canned data (or raises
VisualizationServiceError for unknown scans) so the graph/summary/timeline/
heatmap endpoints and their 404 paths run without a database.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.visualization import router
from spiderfoot.api.dependencies import get_api_key, get_visualization_service
from spiderfoot.reporting.visualization_service import VisualizationServiceError


class _FakeVizService:
    def __init__(self, known=("scan-1",)):
        self._known = set(known)

    def _check(self, scan_id):
        if scan_id not in self._known:
            raise VisualizationServiceError(f"Scan {scan_id} not found")

    def get_graph_data(self, scan_id, event_type=None):
        self._check(scan_id)
        # (scan_info, results) — results keyed by hash; empty graph is fine.
        return ({"id": scan_id}, {})

    def get_summary_data(self, scan_id, group_by="type"):
        self._check(scan_id)
        return {"scan_id": scan_id, "group_by": group_by, "groups": {}}

    def get_timeline_data(self, scan_id, interval="hour", event_type=None):
        self._check(scan_id)
        return {"scan_id": scan_id, "buckets": []}

    def get_heatmap_data(self, scan_id, **kwargs):
        self._check(scan_id)
        return {"scan_id": scan_id, "cells": []}


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.dependency_overrides[get_visualization_service] = lambda: _FakeVizService()
    app.include_router(router)
    return TestClient(app)


class TestGraph:
    def test_graph_json(self, client):
        resp = client.get("/visualization/graph/scan-1")
        assert resp.status_code == 200

    def test_graph_unknown_404(self, client):
        assert client.get("/visualization/graph/nope").status_code == 404


class TestSummary:
    def test_summary(self, client):
        resp = client.get("/visualization/summary/scan-1")
        assert resp.status_code == 200
        assert resp.json()["scan_id"] == "scan-1"

    def test_summary_unknown_404(self, client):
        assert client.get("/visualization/summary/nope").status_code == 404


class TestTimeline:
    def test_timeline(self, client):
        assert client.get("/visualization/timeline/scan-1").status_code == 200

    def test_timeline_unknown_404(self, client):
        assert client.get("/visualization/timeline/nope").status_code == 404


class TestHeatmap:
    def test_heatmap(self, client):
        assert client.get("/visualization/heatmap/scan-1").status_code == 200

    def test_heatmap_unknown_404(self, client):
        assert client.get("/visualization/heatmap/nope").status_code == 404
