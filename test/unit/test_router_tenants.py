"""Tests for spiderfoot.api.routers.tenants — multi-tenancy CRUD API.

Drives the router through a TestClient against a fresh in-memory TenantManager
(the module singleton is replaced per test for isolation). Covers create
(success / invalid plan / duplicate), list, get, update, delete, usage, and
the plan-info endpoint, including the 404 paths.
"""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.tenants as tenants_mod
from spiderfoot.api.routers.tenants import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.auth.tenancy import TenantManager


@pytest.fixture
def client(monkeypatch):
    # Fresh manager per test so tenant state never leaks between tests.
    monkeypatch.setattr(tenants_mod, "_manager", TenantManager())
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _create(client, slug="acme", name="Acme", plan="free"):
    return client.post("/tenants", json={"name": name, "slug": slug,
                                         "plan": plan, "owner_email": "a@b.c"})


class TestCreate:
    def test_create_success(self, client):
        resp = _create(client)
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Acme"
        assert "tenant_id" in body

    def test_invalid_plan_400(self, client):
        resp = client.post("/tenants", json={"name": "X", "slug": "x",
                                             "plan": "platinum"})
        assert resp.status_code == 400
        assert "Invalid plan" in resp.json()["detail"]

    def test_duplicate_slug_409(self, client):
        assert _create(client, slug="dup").status_code == 200
        resp = _create(client, slug="dup")
        assert resp.status_code == 409


class TestRead:
    def test_list_includes_created(self, client):
        _create(client, slug="one")
        resp = client.get("/tenants")
        assert resp.status_code == 200
        slugs = [t["slug"] for t in resp.json()["tenants"]]
        assert "one" in slugs

    def test_get_by_id(self, client):
        tid = _create(client, slug="getme").json()["tenant_id"]
        resp = client.get(f"/tenants/{tid}")
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == tid

    def test_get_unknown_404(self, client):
        assert client.get("/tenants/nonexistent").status_code == 404

    def test_usage(self, client):
        tid = _create(client, slug="use").json()["tenant_id"]
        resp = client.get(f"/tenants/{tid}/usage")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_usage_unknown_404(self, client):
        assert client.get("/tenants/nope/usage").status_code == 404


class TestUpdate:
    def test_update_name(self, client):
        tid = _create(client, slug="upd").json()["tenant_id"]
        resp = client.put(f"/tenants/{tid}", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    def test_update_unknown_404(self, client):
        assert client.put("/tenants/nope", json={"name": "x"}).status_code == 404


class TestDelete:
    def test_delete(self, client):
        tid = _create(client, slug="del").json()["tenant_id"]
        resp = client.delete(f"/tenants/{tid}")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}
        # Gone afterwards.
        assert client.get(f"/tenants/{tid}").status_code == 404

    def test_delete_unknown_404(self, client):
        assert client.delete("/tenants/nope").status_code == 404


class TestPlanInfo:
    def test_plan_info(self, client):
        resp = client.get("/tenants/plans/info")
        assert resp.status_code == 200
        plans = {p["name"] for p in resp.json()["plans"]}
        assert {"free", "enterprise"} <= plans
