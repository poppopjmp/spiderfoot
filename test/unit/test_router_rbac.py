"""Tests for spiderfoot.api.routers.rbac — role/permission inspection API."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.rbac import router
from spiderfoot.api.dependencies import get_api_key


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


class TestConfig:
    def test_get_rbac_config(self, client):
        assert client.get("/rbac").status_code == 200

    def test_list_roles(self, client):
        resp = client.get("/rbac/roles")
        assert resp.status_code == 200

    def test_me(self, client):
        assert client.get("/rbac/me").status_code == 200


class TestRole:
    def test_known_role(self, client):
        assert client.get("/rbac/roles/admin").status_code == 200

    def test_unknown_role_400(self, client):
        assert client.get("/rbac/roles/nonexistent").status_code == 400


class TestCheck:
    def test_missing_params_422(self, client):
        assert client.get("/rbac/check").status_code == 422

    def test_admin_allowed(self, client):
        resp = client.get("/rbac/check",
                          params={"role": "admin", "permission": "scan:read"})
        assert resp.status_code == 200
        assert resp.json()["allowed"] is True
