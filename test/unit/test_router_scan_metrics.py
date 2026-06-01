"""Tests for spiderfoot.api.routers.scan_metrics.

Covers the Prometheus text endpoint, the JSON metrics endpoint (shape of
counters/gauges/distributions/breakdowns), the reset endpoint, and the
internal ``_summarize_list`` percentile helper. The metrics backend is the
real observability store, reset between tests for determinism.
"""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.scan_metrics import router, _summarize_list
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.observability.scan_metrics import reset_metrics


@pytest.fixture
def client():
    reset_metrics()
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


class TestPrometheusEndpoint:
    def test_returns_text_exposition(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        # Prometheus exposition format starts each metric family with # HELP.
        assert "# HELP" in resp.text
        assert "sf_scans_started_total" in resp.text


class TestScanMetricsJson:
    def test_shape_after_reset(self, client):
        resp = client.get("/scan-metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"counters", "gauges", "distributions", "breakdowns"}
        # Freshly reset: all counters zero.
        assert body["counters"]["scans_started"] == 0
        assert body["counters"]["scans_completed"] == 0
        # Distributions summarise empty lists with a zeroed structure.
        assert body["distributions"]["scan_durations"]["count"] == 0
        assert isinstance(body["breakdowns"]["events_by_type"], dict)


class TestReset:
    def test_reset_returns_status(self, client):
        resp = client.post("/scan-metrics/reset")
        assert resp.status_code == 200
        assert resp.json() == {"status": "reset"}


class TestSummarizeList:
    def test_empty_list(self):
        out = _summarize_list([])
        assert out == {"count": 0, "min": 0, "max": 0, "avg": 0,
                       "p50": 0, "p90": 0, "p99": 0}

    def test_numeric_percentiles(self):
        out = _summarize_list(list(range(1, 101)))  # 1..100
        assert out["count"] == 100
        assert out["min"] == 1
        assert out["max"] == 100
        assert out["avg"] == 50.5
        # p50 index = int(100*0.5)=50 -> value 51; p90 -> 91; p99 -> 100.
        assert out["p50"] == 51
        assert out["p90"] == 91
        assert out["p99"] == 100

    def test_non_numeric_falls_back_to_count(self):
        out = _summarize_list(["a", "b", "c"])
        assert out == {"count": 3}
