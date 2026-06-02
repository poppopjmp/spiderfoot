"""Tests for spiderfoot.api.routers.sso — SSO provider management API.

Provider CRUD, listing, sessions/stats/protocols, and the get-by-id 404 path,
against a fresh in-memory SSOManager per test.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.sso as sso_mod
from spiderfoot.api.routers.sso import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.auth.sso import SSOManager


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(sso_mod, "_manager", SSOManager())
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _create(client, name="okta"):
    return client.post("/sso/providers", json={
        "name": name, "protocol": "oidc",
        "client_id": "abc", "client_secret": "xyz", "metadata": {},
    })


class TestProviderCrud:
    def test_create_201(self, client):
        resp = _create(client)
        assert resp.status_code == 201
        assert resp.json()["provider"]["name"] == "okta"

    def test_list_and_get(self, client):
        pid = _create(client).json()["provider"]["provider_id"]
        listed = client.get("/sso/providers")
        assert listed.status_code == 200
        assert client.get(f"/sso/providers/{pid}").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get("/sso/providers/nonexistent").status_code == 404

    def test_delete(self, client):
        pid = _create(client).json()["provider"]["provider_id"]
        assert client.delete(f"/sso/providers/{pid}").status_code in (200, 204)
        assert client.get(f"/sso/providers/{pid}").status_code == 404


class TestMetadataEndpoints:
    def test_protocols(self, client):
        protos = client.get("/sso/protocols").json()["protocols"]
        ids = {p["id"] for p in protos}
        assert {"oidc", "saml2"} <= ids

    def test_sessions(self, client):
        assert client.get("/sso/sessions").status_code == 200

    def test_stats(self, client):
        assert client.get("/sso/stats").status_code == 200
