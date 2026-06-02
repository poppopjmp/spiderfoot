"""Tests for spiderfoot.api.routers.schedules — scheduled scan management.

The schedule store is Redis-backed; the shared in-memory FakeRedis is injected
via the module's _get_redis so the create/list/get/update/delete lifecycle runs
without a Redis server.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.schedules as sched_mod
from spiderfoot.api.routers.schedules import router
from spiderfoot.api.dependencies import get_api_key
from test.unit.utils.fake_redis import FakeRedis


@pytest.fixture
def client(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(sched_mod, "_get_redis", lambda: fake)
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)  # router already declares prefix="/schedules"
    return TestClient(app)


def _create(client, name="daily", target="example.com"):
    return client.post("/schedules", json={
        "name": name, "target": target, "interval_hours": 24,
    })


class TestCrud:
    def test_list_empty(self, client):
        resp = client.get("/schedules")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_create_201(self, client):
        resp = _create(client)
        assert resp.status_code == 201
        assert resp.json()["name"] == "daily"
        assert resp.json()["id"]

    def test_create_then_list_and_get(self, client):
        sid = _create(client, name="findme").json()["id"]
        listing = client.get("/schedules").json()
        assert listing["total"] == 1
        assert any(s["name"] == "findme" for s in listing["schedules"])
        assert client.get(f"/schedules/{sid}").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get("/schedules/nonexistent").status_code == 404

    def test_update(self, client):
        sid = _create(client).json()["id"]
        resp = client.patch(f"/schedules/{sid}", json={"interval_hours": 48})
        assert resp.status_code == 200
        assert resp.json()["interval_hours"] == 48

    def test_update_unknown_404(self, client):
        assert client.patch("/schedules/nope",
                            json={"interval_hours": 48}).status_code == 404

    def test_delete(self, client):
        sid = _create(client).json()["id"]
        assert client.delete(f"/schedules/{sid}").status_code == 204
        assert client.get(f"/schedules/{sid}").status_code == 404

    def test_delete_unknown_404(self, client):
        assert client.delete("/schedules/nonexistent").status_code == 404


class TestTrigger:
    def test_trigger_reachable_for_known_schedule(self, client):
        # The trigger endpoint resolves to its own handler (not a 404); whether
        # the run launches depends on the scan backend, which is absent here.
        sid = _create(client).json()["id"]
        assert client.post(f"/schedules/{sid}/trigger").status_code != 404

    def test_trigger_unknown_404(self, client):
        assert client.post("/schedules/nonexistent/trigger").status_code == 404
