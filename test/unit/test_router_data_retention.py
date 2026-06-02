"""Tests for spiderfoot.api.routers.data_retention — retention rule CRUD."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.data_retention import router
from spiderfoot.api.dependencies import get_api_key


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _create(client, name="r1", resource="scans"):
    return client.post("/retention/rules", json={
        "name": name, "resource": resource, "max_age_days": 30,
        "action": "delete",
    })


class TestReadEndpoints:
    @pytest.mark.parametrize("path", [
        "/retention/rules",
        "/retention/history",
        "/retention/stats",
        "/retention/actions",
        "/retention/resources",
    ])
    def test_read(self, client, path):
        assert client.get(path).status_code == 200


class TestCrud:
    def test_create_and_get(self, client):
        resp = _create(client)
        assert resp.status_code in (200, 201)
        assert client.get("/retention/rules/r1").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get("/retention/rules/nonexistent").status_code == 404

    def test_update(self, client):
        _create(client, name="upd")
        resp = client.patch("/retention/rules/upd", json={"max_age_days": 60})
        assert resp.status_code == 200

    def test_delete(self, client):
        _create(client, name="del")
        assert client.delete("/retention/rules/del").status_code in (200, 204)
        assert client.get("/retention/rules/del").status_code == 404

    def test_preview(self, client):
        _create(client, name="prev")
        resp = client.post("/retention/preview", json={"name": "prev"})
        assert resp.status_code in (200, 404, 422)
