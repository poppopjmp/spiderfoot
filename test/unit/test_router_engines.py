"""Tests for spiderfoot.api.routers.engines.

Covers listing engines, the get-by-name 404 path, and the validate endpoint
(both the empty-body 422 and the semantic validation of a well-formed but
incomplete engine definition). Create/update/delete are intentionally not
exercised here because they persist engine definitions to disk.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.engines import router
from spiderfoot.api.dependencies import get_api_key


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


class TestList:
    def test_list_engines(self, client):
        resp = client.get("/engines")
        assert resp.status_code == 200
        body = resp.json()
        assert "engines" in body and "total" in body
        assert isinstance(body["engines"], list)
        assert body["total"] == len(body["engines"])


class TestGet:
    def test_unknown_engine_404(self, client):
        assert client.get("/engines/nonexistent").status_code == 404


class TestValidate:
    def test_empty_body_422(self, client):
        assert client.post("/engines/validate", json={}).status_code == 422

    def test_incomplete_engine_reports_errors(self, client):
        resp = client.post("/engines/validate", json={
            "engine": {"name": "my-test-engine", "description": "d"},
        })
        assert resp.status_code == 200
        body = resp.json()
        # No modules specified -> invalid with a descriptive error.
        assert body["valid"] is False
        assert any("module" in e.lower() for e in body["errors"])
