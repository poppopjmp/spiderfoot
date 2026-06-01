"""Tests for spiderfoot.api.routers.scan_comparison.

Focuses on the metadata and history endpoints and the get-by-id 404 path
(the compare endpoints require populated scan data / a DB). Includes
regression coverage for /scan-comparison/categories and /severity-levels,
which were previously shadowed by /scan-comparison/{comparison_id}.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.scan_comparison as sc_mod
from spiderfoot.api.routers.scan_comparison import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.scan.comparison import ScanComparator


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(sc_mod, "_comparator", ScanComparator())
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


class TestGetById:
    def test_unknown_comparison_404(self, client):
        resp = client.get("/scan-comparison/does-not-exist")
        assert resp.status_code == 404


class TestLiteralSubPathsNotShadowed:
    def test_categories(self, client):
        resp = client.get("/scan-comparison/categories")
        assert resp.status_code == 200, "shadowed by /{comparison_id}"
        assert isinstance(resp.json(), dict)

    def test_severity_levels(self, client):
        resp = client.get("/scan-comparison/severity-levels")
        assert resp.status_code == 200, "shadowed by /{comparison_id}"
        body = resp.json()
        assert "levels" in body
        assert "event_mappings" in body
