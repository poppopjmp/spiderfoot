"""Tests for spiderfoot.api.routers.webhooks.

Covers webhook registration/list/get/delete against a fresh in-memory
NotificationManager, the SSRF URL guard on registration, and a regression
check that /webhooks/event-types resolves to its own handler rather than being
shadowed by /webhooks/{webhook_id}.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.webhooks import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.notifications.manager import reset_notification_manager


@pytest.fixture
def client():
    reset_notification_manager()  # fresh singleton per test
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    yield TestClient(app)
    reset_notification_manager()


def _create(client, url="https://hooks.example.com/endpoint"):
    return client.post("/webhooks", json={"url": url, "event_types": ["scan.*"]})


class TestRegistration:
    def test_create_201(self, client):
        resp = _create(client)
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "registered"
        assert body["webhook_id"]

    def test_ssrf_private_ip_rejected(self, client):
        # The field_validator must reject loopback/private targets (422).
        resp = client.post("/webhooks", json={"url": "http://127.0.0.1/steal"})
        assert resp.status_code == 422

    def test_ssrf_non_http_scheme_rejected(self, client):
        resp = client.post("/webhooks", json={"url": "ftp://example.com/x"})
        assert resp.status_code == 422


class TestReadDelete:
    def test_list_then_get(self, client):
        wid = _create(client).json()["webhook_id"]
        listing = client.get("/webhooks")
        assert listing.status_code == 200
        assert listing.json()["count"] >= 1
        assert client.get(f"/webhooks/{wid}").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get("/webhooks/nonexistent").status_code == 404

    def test_delete(self, client):
        wid = _create(client).json()["webhook_id"]
        assert client.delete(f"/webhooks/{wid}").status_code in (200, 204)
        assert client.get(f"/webhooks/{wid}").status_code == 404


class TestLiteralSubPathsNotShadowed:
    def test_event_types(self, client):
        resp = client.get("/webhooks/event-types")
        assert resp.status_code == 200, "shadowed by /webhooks/{webhook_id}"
        body = resp.json()
        assert "event_types" in body and "total" in body

    def test_stats(self, client):
        assert client.get("/webhooks/stats").status_code == 200

    def test_history(self, client):
        resp = client.get("/webhooks/history")
        assert resp.status_code == 200
        assert "deliveries" in resp.json()
