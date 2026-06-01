"""Tests for spiderfoot.api.routers.webhook_delivery — delivery queue API."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.webhook_delivery import router
from spiderfoot.api.dependencies import get_api_key


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _create(client):
    return client.post("/webhook-delivery/deliveries", json={
        "endpoint_id": "e1",
        "endpoint_url": "https://hooks.example.com/h",
        "event_type": "scan.completed",
        "payload": {"scan_id": "s1"},
    })


class TestReadEndpoints:
    @pytest.mark.parametrize("path", [
        "/webhook-delivery/deliveries",
        "/webhook-delivery/retries",
        "/webhook-delivery/dead-letter",
        "/webhook-delivery/stats",
        "/webhook-delivery/event-types",
    ])
    def test_read(self, client, path):
        assert client.get(path).status_code == 200


class TestCreateAndRetrieve:
    def test_create(self, client):
        resp = _create(client)
        assert resp.status_code in (200, 201)

    def test_create_then_get(self, client):
        body = _create(client).json()
        did = body.get("delivery_id") or body.get("id") or \
            (body.get("delivery") or {}).get("id")
        if did:
            assert client.get(
                f"/webhook-delivery/deliveries/{did}").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get(
            "/webhook-delivery/deliveries/nonexistent").status_code == 404
