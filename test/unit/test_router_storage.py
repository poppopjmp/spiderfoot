"""Tests for spiderfoot.api.routers.storage — MinIO/object-storage API.

Substitutes a fake storage manager for the MinIO-backed one (via _get_storage)
so health, bucket init, report listing, backup listing, snapshot listing, and
the error path are exercised without a running MinIO server.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.storage as storage_mod
from spiderfoot.api.routers.storage import router
from spiderfoot.api.dependencies import get_api_key


class _FakeStorage:
    def __init__(self, health=None, buckets_fail=False):
        self._health = health or {
            "status": "ok", "endpoint": "minio:9000",
            "buckets_found": 3, "missing_buckets": [], "latency_ms": 1.2,
        }
        self._buckets_fail = buckets_fail

    def health_check(self):
        return self._health

    def ensure_buckets(self):
        if self._buckets_fail:
            raise RuntimeError("minio down")
        return ["sf-reports", "sf-backups"]

    def list_reports(self, scan_id):
        return [{"key": f"{scan_id}/r1.json", "size": 10}]

    def list_pg_backups(self):
        return [{"key": "backups/db-2026.sql", "size": 1024}]

    def list_qdrant_snapshots(self, collection):
        return [{"key": f"snapshots/{collection}.snap", "size": 50}]


@pytest.fixture
def make_client(monkeypatch):
    def _make(storage):
        monkeypatch.setattr(storage_mod, "_get_storage", lambda: storage)
        app = FastAPI()
        app.dependency_overrides[get_api_key] = lambda: "test-key"
        app.include_router(router)
        return TestClient(app)
    return _make


class TestHealth:
    def test_ok(self, make_client):
        client = make_client(_FakeStorage())
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["buckets_found"] == 3


class TestBuckets:
    def test_ensure_buckets(self, make_client):
        client = make_client(_FakeStorage())
        resp = client.post("/buckets")
        assert resp.status_code == 200
        assert "sf-reports" in resp.json()["created"]

    def test_ensure_buckets_failure_500(self, make_client):
        client = make_client(_FakeStorage(buckets_fail=True))
        assert client.post("/buckets").status_code == 500


class TestListings:
    def test_list_reports(self, make_client):
        client = make_client(_FakeStorage())
        resp = client.get("/reports/scan-1")
        assert resp.status_code == 200
        assert resp.json()[0]["key"] == "scan-1/r1.json"

    def test_list_backups(self, make_client):
        client = make_client(_FakeStorage())
        resp = client.get("/backups")
        assert resp.status_code == 200

    def test_list_snapshots(self, make_client):
        client = make_client(_FakeStorage())
        resp = client.get("/snapshots", params={"collection": "events"})
        assert resp.status_code == 200
