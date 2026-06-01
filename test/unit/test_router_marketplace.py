"""Tests for spiderfoot.api.routers.marketplace.

Covers the read endpoints (paginated plugin listing, featured, categories,
stats, installed, updates) and the get-by-id 404 path. Auth is overridden;
the marketplace backend is the module's in-memory catalog.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.marketplace import router
from spiderfoot.api.dependencies import get_api_key


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


class TestReadEndpoints:
    def test_plugins_paginated(self, client):
        resp = client.get("/marketplace/plugins")
        assert resp.status_code == 200
        body = resp.json()
        assert {"plugins", "total", "page", "page_size", "total_pages"} <= set(body)
        assert isinstance(body["plugins"], list)

    def test_featured(self, client):
        resp = client.get("/marketplace/featured")
        assert resp.status_code == 200
        assert "plugins" in resp.json()

    def test_categories(self, client):
        resp = client.get("/marketplace/categories")
        assert resp.status_code == 200
        assert "categories" in resp.json()

    def test_stats(self, client):
        resp = client.get("/marketplace/stats")
        assert resp.status_code == 200
        assert "stats" in resp.json()

    def test_installed(self, client):
        resp = client.get("/marketplace/installed")
        assert resp.status_code == 200
        assert "plugins" in resp.json()

    def test_updates(self, client):
        resp = client.get("/marketplace/updates")
        assert resp.status_code == 200
        assert "updates" in resp.json()


class TestGetPlugin:
    def test_unknown_plugin_404(self, client):
        assert client.get("/marketplace/plugins/nonexistent").status_code == 404
