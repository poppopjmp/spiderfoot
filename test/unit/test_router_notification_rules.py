"""Tests for spiderfoot.api.routers.notification_rules.

Drives the rule CRUD lifecycle, evaluation, history/stats, and metadata
endpoints against a fresh in-memory NotificationRulesEngine (the module
singleton is replaced per test for isolation).

Includes a regression test for route ordering: the literal sub-paths
(history, stats, operators, channels) must not be shadowed by the
parameterized ``/{rule_id}`` GET route.
"""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.notification_rules as nr_mod
from spiderfoot.api.routers.notification_rules import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.notifications.rules import NotificationRulesEngine


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(nr_mod, "_engine", NotificationRulesEngine())
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _create(client, name="rule-1"):
    return client.post("/notification-rules", json={
        "name": name, "priority": 5, "conditions": [], "logic": "and",
        "channels": [], "severity": "info",
    })


class TestCrud:
    def test_create_returns_201(self, client):
        resp = _create(client)
        assert resp.status_code == 201
        assert resp.json()["rule"]["name"] == "rule-1"

    def test_list_and_get(self, client):
        body = _create(client, name="findme").json()["rule"]
        rid = body.get("id") or body.get("rule_id")
        listed = client.get("/notification-rules").json()["rules"]
        assert any(r["name"] == "findme" for r in listed)
        assert client.get(f"/notification-rules/{rid}").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get("/notification-rules/nope").status_code == 404

    def test_update(self, client):
        body = _create(client).json()["rule"]
        rid = body.get("id") or body.get("rule_id")
        resp = client.patch(f"/notification-rules/{rid}", json={"name": "renamed"})
        assert resp.status_code == 200
        assert resp.json()["updated"]["name"] == "renamed"

    def test_update_unknown_404(self, client):
        assert client.patch("/notification-rules/nope",
                            json={"name": "x"}).status_code == 404

    def test_delete(self, client):
        body = _create(client).json()["rule"]
        rid = body.get("id") or body.get("rule_id")
        resp = client.delete(f"/notification-rules/{rid}")
        assert resp.status_code == 200
        assert client.get(f"/notification-rules/{rid}").status_code == 404

    def test_delete_unknown_404(self, client):
        assert client.delete("/notification-rules/nope").status_code == 404


class TestEvaluate:
    def test_evaluate_returns_triggered_count(self, client):
        resp = client.post("/notification-rules/evaluate", json={
            "event": {"type": "IP_ADDRESS", "data": "8.8.8.8", "module": "m"},
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "triggered" in body and isinstance(body["notifications"], list)


class TestLiteralSubPathsNotShadowed:
    """Regression: these must resolve to their own handlers, not get_rule."""

    @pytest.mark.parametrize("path,key", [
        ("/notification-rules/history", "history"),
        ("/notification-rules/operators", "operators"),
        ("/notification-rules/channels", "channels"),
    ])
    def test_literal_get_paths(self, client, path, key):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} was shadowed by /{{rule_id}}"
        assert key in resp.json()

    def test_stats(self, client):
        resp = client.get("/notification-rules/stats")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)
