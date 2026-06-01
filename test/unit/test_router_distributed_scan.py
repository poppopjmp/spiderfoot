"""Tests for spiderfoot.api.routers.distributed_scan — worker pool API.

Worker registration/listing/get, heartbeat, pool stats, and strategy listing,
against a fresh in-memory DistributedScanManager per test.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.distributed_scan as ds_mod
from spiderfoot.api.routers.distributed_scan import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.scan.distributed import DistributedScanManager


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(ds_mod, "_manager", DistributedScanManager())
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _register(client, hostname="worker-1"):
    return client.post("/distributed/workers", json={
        "hostname": hostname, "ip_address": "10.0.0.1",
        "capabilities": ["dns"], "max_concurrent": 4,
    })


class TestWorkers:
    def test_register(self, client):
        resp = _register(client)
        assert resp.status_code in (200, 201)

    def test_register_then_list_and_get(self, client):
        wid = _register(client).json()["worker"]["worker_id"]
        listing = client.get("/distributed/workers")
        assert listing.status_code == 200
        assert client.get(f"/distributed/workers/{wid}").status_code == 200
        # Heartbeat for a known worker should succeed.
        assert client.post(
            f"/distributed/workers/{wid}/heartbeat", json={}).status_code == 200

    def test_heartbeat_unknown_worker_404(self, client):
        assert client.post(
            "/distributed/workers/nonexistent/heartbeat", json={}).status_code == 404

    def test_get_unknown_404(self, client):
        assert client.get("/distributed/workers/nonexistent").status_code == 404


class TestPoolMetadata:
    def test_scans(self, client):
        assert client.get("/distributed/scans").status_code == 200

    def test_pool_stats(self, client):
        assert client.get("/distributed/pool/stats").status_code == 200

    def test_strategies(self, client):
        strategies = client.get("/distributed/strategies").json()["strategies"]
        ids = {s["id"] for s in strategies}
        assert "round_robin" in ids
