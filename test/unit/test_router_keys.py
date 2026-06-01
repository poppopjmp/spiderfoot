"""Tests for spiderfoot.api.routers.keys — API key management.

The key store is Redis-backed; these tests inject the shared in-memory
FakeRedis (see test/unit/utils/fake_redis.py) into a fresh APIKeyManager so the
full create/list/get/update/revoke/delete lifecycle runs without a Redis server.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.auth.api_keys as api_keys_mod
from spiderfoot.api.routers.keys import router
from spiderfoot.api.dependencies import get_api_key
from test.unit.utils.fake_redis import FakeRedis


@pytest.fixture
def client(monkeypatch):
    fake = FakeRedis()
    # Any APIKeyManager created from now resolves to the in-memory fake.
    monkeypatch.setattr(api_keys_mod, "_get_redis", lambda: fake)
    monkeypatch.setattr(api_keys_mod, "_manager", None)  # force fresh singleton
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)  # router already declares prefix="/keys"
    yield TestClient(app)
    monkeypatch.setattr(api_keys_mod, "_manager", None)


def _create(client, name="ci-key", role="viewer"):
    return client.post("/keys", json={"name": name, "role": role})


class TestCreate:
    def test_create_returns_full_key_once(self, client):
        resp = _create(client)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "ci-key"
        assert body["key_id"]
        assert body["full_key"]  # only returned at creation time


class TestLifecycle:
    def test_list_after_create(self, client):
        _create(client, name="listed")
        resp = client.get("/keys")
        assert resp.status_code == 200
        records = resp.json()["keys"] if "keys" in resp.json() else resp.json()
        names = [r.get("name") for r in records] if isinstance(records, list) else []
        assert "listed" in names

    def test_get_by_id(self, client):
        kid = _create(client).json()["key_id"]
        resp = client.get(f"/keys/{kid}")
        assert resp.status_code == 200
        assert resp.json()["key_id"] == kid

    def test_get_unknown_404(self, client):
        assert client.get("/keys/nonexistent").status_code == 404

    def test_revoke(self, client):
        kid = _create(client).json()["key_id"]
        resp = client.post(f"/keys/{kid}/revoke")
        assert resp.status_code == 200

    def test_revoke_unknown_404(self, client):
        assert client.post("/keys/nonexistent/revoke").status_code == 404

    def test_delete(self, client):
        kid = _create(client).json()["key_id"]
        assert client.delete(f"/keys/{kid}").status_code == 204
        assert client.get(f"/keys/{kid}").status_code == 404

    def test_delete_unknown_404(self, client):
        assert client.delete("/keys/nonexistent").status_code == 404
