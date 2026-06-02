"""Structural tests for spiderfoot.api.routers.reports.

Reports are tracked in an in-memory store (`_report_store`) and generated
asynchronously from scan events. These tests seed the store directly and inject
a FakeScanService for the generate endpoint (with the background generator
patched out, so no LLM/report engine runs), covering get/status/list/delete and
the 404 paths without a database.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.reports as rep
from spiderfoot.api.dependencies import get_api_key, get_scan_service
from test.unit.utils.fake_scan_service import FakeScanService, FakeScanRecord


@pytest.fixture
def svc():
    s = FakeScanService()
    s.add_scan(FakeScanRecord("scan-1"))
    return s


@pytest.fixture
def client(svc):
    rep._report_store.clear()
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.dependency_overrides[get_scan_service] = lambda: svc
    app.include_router(rep.router)
    yield TestClient(app)
    rep._report_store.clear()


def _seed(report_id="rid-1", scan_id="scan-1", status="complete"):
    rep.store_report(report_id, {
        "report_id": report_id, "scan_id": scan_id, "title": "T",
        "status": status, "report_type": "full", "sections": [],
        "metadata": {}, "created_at": 1000.0,
    })


class TestRetrieve:
    def test_get(self, client):
        _seed()
        resp = client.get("/reports/rid-1")
        assert resp.status_code == 200
        assert resp.json()["report_id"] == "rid-1"

    def test_get_unknown_404(self, client):
        assert client.get("/reports/nope").status_code == 404

    def test_status(self, client):
        _seed(status="pending")
        resp = client.get("/reports/rid-1/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_status_unknown_404(self, client):
        assert client.get("/reports/nope/status").status_code == 404

    def test_list(self, client):
        _seed("rid-1")
        _seed("rid-2")
        resp = client.get("/reports")
        assert resp.status_code == 200
        ids = {r["report_id"] for r in resp.json()}
        assert {"rid-1", "rid-2"} <= ids


class TestDelete:
    def test_delete(self, client):
        _seed()
        assert client.delete("/reports/rid-1").status_code == 204
        assert client.get("/reports/rid-1").status_code == 404

    def test_delete_unknown_404(self, client):
        assert client.delete("/reports/nope").status_code == 404


class TestGenerate:
    def test_generate_returns_202_and_seeds_store(self, client):
        with patch.object(rep, "_generate_report_background"), \
                patch.object(rep, "_get_scan_events",
                             return_value=([], {"target": "example.com"})):
            resp = client.post("/reports/generate",
                              json={"scan_id": "scan-1", "report_type": "full"})
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        # The new report is now retrievable from the store.
        assert client.get(f"/reports/{body['report_id']}/status").status_code == 200
