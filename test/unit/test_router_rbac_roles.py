"""Tests for spiderfoot.api.routers.rbac_roles — enhanced RBAC v2 API.

Role CRUD, permission listing, role bindings, per-user role/permission queries,
and permission checks, against a fresh in-memory EnhancedRBACManager per test.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.rbac_roles as rr_mod
from spiderfoot.api.routers.rbac_roles import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.auth.rbac import EnhancedRBACManager


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(rr_mod, "_manager", EnhancedRBACManager())
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _create_role(client, name="role1", perms=("scan:read",)):
    return client.post("/rbac/v2/roles",
                       json={"name": name, "permissions": list(perms)})


class TestRoleCrud:
    def test_create_and_get(self, client):
        resp = _create_role(client)
        assert resp.status_code == 200
        rid = resp.json()["role_id"]
        assert client.get(f"/rbac/v2/roles/{rid}").status_code == 200

    def test_list_roles(self, client):
        _create_role(client, name="findme")
        names = [r["name"] for r in client.get("/rbac/v2/roles").json()["roles"]]
        assert "findme" in names

    def test_get_unknown_404(self, client):
        assert client.get("/rbac/v2/roles/nonexistent").status_code == 404

    def test_update(self, client):
        rid = _create_role(client).json()["role_id"]
        resp = client.put(f"/rbac/v2/roles/{rid}",
                          json={"permissions": ["scan:read", "scan:create"]})
        assert resp.status_code == 200

    def test_delete(self, client):
        rid = _create_role(client).json()["role_id"]
        assert client.delete(f"/rbac/v2/roles/{rid}").status_code in (200, 204)
        assert client.get(f"/rbac/v2/roles/{rid}").status_code == 404


class TestPermissions:
    def test_list_permissions(self, client):
        resp = client.get("/rbac/v2/permissions")
        assert resp.status_code == 200

    def test_check_permission(self, client):
        resp = client.post("/rbac/v2/check",
                          json={"user_id": "u1", "permission": "scan:read"})
        assert resp.status_code == 200
        assert "allowed" in resp.json()


class TestBindings:
    def test_bind_then_query_user(self, client):
        rid = _create_role(client).json()["role_id"]
        bind = client.post("/rbac/v2/bindings",
                          json={"user_id": "u1", "role_id": rid})
        assert bind.status_code == 200
        assert client.get("/rbac/v2/users/u1/roles").status_code == 200
        perms = client.get("/rbac/v2/users/u1/permissions")
        assert perms.status_code == 200
