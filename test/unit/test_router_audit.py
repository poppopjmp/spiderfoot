"""Tests for spiderfoot.api.routers.audit — audit-event query API.

The audit store is a Redis ring buffer; rather than require Redis, these tests
patch ``query_audit_events`` (imported lazily inside the handlers) with
synthetic AuditEvent objects so the router's filtering passthrough and the
/stats aggregation (counts by action/severity/actor, time range) are exercised
deterministically. /actions is tested against the live Actions constants.
"""
from __future__ import annotations

import time

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.audit import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.observability.audit_events import AuditEvent


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _event(action="auth.login", actor="alice", severity="info", ts=None):
    return AuditEvent(
        event_id="e-" + action,
        timestamp=ts if ts is not None else time.time(),
        action=action, actor=actor, actor_ip="1.2.3.4",
        resource="r", resource_type="api_key", details={},
        severity=severity, request_id="",
    )


class TestQuery:
    def test_empty(self, monkeypatch):
        monkeypatch.setattr(
            "spiderfoot.observability.audit_events.query_audit_events",
            lambda **kw: [])
        app = FastAPI()
        app.dependency_overrides[get_api_key] = lambda: "k"
        app.include_router(router)
        c = TestClient(app)
        resp = c.get("/audit")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["events"] == []

    def test_returns_events_and_echoes_params(self, monkeypatch):
        events = [_event(), _event(action="auth.logout")]
        captured = {}

        def fake_query(**kw):
            captured.update(kw)
            return events

        monkeypatch.setattr(
            "spiderfoot.observability.audit_events.query_audit_events",
            fake_query)
        app = FastAPI()
        app.dependency_overrides[get_api_key] = lambda: "k"
        app.include_router(router)
        c = TestClient(app)
        resp = c.get("/audit", params={"actor": "alice", "limit": 50})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["query_params"]["actor"] == "alice"
        assert body["query_params"]["limit"] == 50
        # The handler passed our filters through to the backend.
        assert captured["actor"] == "alice"
        assert captured["limit"] == 50


class TestActions:
    def test_lists_actions_grouped(self, client):
        resp = client.get("/audit/actions")
        assert resp.status_code == 200
        actions = resp.json()["actions"]
        # Actions are grouped by their dotted prefix (e.g. "auth").
        assert "auth" in actions
        assert any(a.startswith("auth.") for a in actions["auth"])


class TestStats:
    def test_aggregation(self, monkeypatch):
        now = time.time()
        events = [
            _event(action="auth.login", actor="alice", severity="info", ts=now - 10),
            _event(action="auth.login", actor="bob", severity="info", ts=now - 5),
            _event(action="auth.failed", actor="alice", severity="warning", ts=now),
        ]
        monkeypatch.setattr(
            "spiderfoot.observability.audit_events.query_audit_events",
            lambda **kw: events)
        app = FastAPI()
        app.dependency_overrides[get_api_key] = lambda: "k"
        app.include_router(router)
        c = TestClient(app)
        resp = c.get("/audit/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_events"] == 3
        assert body["events_by_action"]["auth.login"] == 2
        assert body["events_by_severity"]["warning"] == 1
        assert body["events_by_actor"]["alice"] == 2
        assert body["time_range"]["oldest"] == pytest.approx(now - 10, abs=1)
        assert body["time_range"]["newest"] == pytest.approx(now, abs=1)

    def test_stats_empty(self, monkeypatch):
        monkeypatch.setattr(
            "spiderfoot.observability.audit_events.query_audit_events",
            lambda **kw: [])
        app = FastAPI()
        app.dependency_overrides[get_api_key] = lambda: "k"
        app.include_router(router)
        c = TestClient(app)
        resp = c.get("/audit/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_events"] == 0
        # Empty range collapses to zeros rather than infinity.
        assert body["time_range"]["oldest"] == 0
