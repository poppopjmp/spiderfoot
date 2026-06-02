"""Tests for spiderfoot.api.routers.rate_limits.

Covers the configuration view, statistics, and the stats-reset endpoint.
Auth is overridden; the rate-limit backend is the in-process limiter state.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.rate_limits import router
from spiderfoot.api.dependencies import get_api_key


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


class TestConfig:
    def test_get_config(self, client):
        resp = client.get("/rate-limits")
        assert resp.status_code == 200
        body = resp.json()
        assert {"enabled", "tiers"} <= set(body)
        assert isinstance(body["tiers"], dict)


class TestStats:
    def test_get_stats(self, client):
        resp = client.get("/rate-limits/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert {"total_allowed", "total_rejected", "rejection_rate"} <= set(body)

    def test_reset_stats(self, client):
        resp = client.post("/rate-limits/stats/reset")
        assert resp.status_code == 200
        # After reset, counters should be zeroed.
        stats = client.get("/rate-limits/stats").json()
        assert stats["total_rejected"] == 0
        assert stats["total_allowed"] == 0
