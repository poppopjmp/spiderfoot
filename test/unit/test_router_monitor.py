"""Tests for spiderfoot.api.routers.monitor — subdomain monitoring API.

The monitor store is Redis-backed (via SubdomainMonitor); the shared in-memory
FakeRedis is injected through subdomain_monitor._get_redis and a reset singleton
so the add/list/get/delete lifecycle runs without a Redis server.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.scan.subdomain_monitor as sm_mod
from spiderfoot.api.routers.monitor import router
from spiderfoot.api.dependencies import get_api_key
from test.unit.utils.fake_redis import FakeRedis


@pytest.fixture
def client(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(sm_mod, "_get_redis", lambda: fake)
    monkeypatch.setattr(sm_mod, "_monitor", None)  # fresh singleton on the fake
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)  # router already declares prefix="/monitor"
    yield TestClient(app)
    monkeypatch.setattr(sm_mod, "_monitor", None)


def _add(client, domain="example.com"):
    return client.post("/monitor/domains", json={"domain": domain})


class TestDomainLifecycle:
    def test_list_empty(self, client):
        resp = client.get("/monitor/domains")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_add_201(self, client):
        resp = _add(client)
        assert resp.status_code == 201
        assert resp.json()["domain"] == "example.com"

    def test_add_then_list_and_get(self, client):
        _add(client, "findme.com")
        listing = client.get("/monitor/domains").json()
        assert listing["total"] == 1
        assert client.get("/monitor/domains/findme.com").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get("/monitor/domains/nonexistent.com").status_code == 404

    def test_delete(self, client):
        _add(client)
        assert client.delete("/monitor/domains/example.com").status_code == 204
        assert client.get("/monitor/domains/example.com").status_code == 404
