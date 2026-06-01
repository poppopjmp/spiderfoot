"""Tests for spiderfoot.api.routers.sarif — SARIF v2.1.0 export API.

Covers the three endpoints (export, rules listing, schema info) end-to-end
through a TestClient, plus the event-conversion accounting in /sarif/export.
The API-key dependency is overridden so these tests exercise the router logic
without coupling to global auth configuration.
"""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.sarif import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.export.sarif_export import _SARIF_RULE_MAP


@pytest.fixture
def client():
    app = FastAPI()
    # Bypass auth so we test router behaviour, not credential plumbing.
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


class TestSarifExport:
    def test_export_empty_events_is_valid_sarif(self, client):
        resp = client.post("/sarif/export", json={"scan_id": "scan-1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["result_count"] == 0
        assert body["rule_count"] == 0
        # A SARIF document must carry version + runs.
        assert body["sarif"]["version"] == "2.1.0"
        assert isinstance(body["sarif"]["runs"], list)

    def test_export_counts_converted_events(self, client):
        # Pick a known mappable event type from the live rule map.
        known_type = next(iter(_SARIF_RULE_MAP))
        events = [
            {"type": known_type, "data": "example.com", "module": "sfp_x"},
            {"type": known_type, "data": "other.com", "module": "sfp_x"},
            {"type": "DEFINITELY_NOT_A_REAL_TYPE", "data": "x"},
        ]
        resp = client.post(
            "/sarif/export",
            json={"scan_id": "scan-2", "scan_name": "My Scan",
                  "scan_target": "example.com", "events": events},
        )
        assert resp.status_code == 200
        body = resp.json()
        # The two mappable events should produce results; the unknown one
        # should not raise and should not inflate the rule count.
        assert body["result_count"] >= 2
        assert body["rule_count"] >= 1
        assert isinstance(body["summary"], dict)

    def test_export_requires_scan_id(self, client):
        resp = client.post("/sarif/export", json={})
        assert resp.status_code == 422  # pydantic validation error


class TestSarifRules:
    def test_lists_all_rules(self, client):
        resp = client.get("/sarif/rules")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == len(_SARIF_RULE_MAP)
        assert len(body["rules"]) == body["total"]
        # Each rule entry exposes the documented contract fields.
        for rule in body["rules"]:
            assert {"ruleId", "name", "description", "level",
                    "tags", "eventType"} <= set(rule)
        # Rules are returned sorted by event type.
        event_types = [r["eventType"] for r in body["rules"]]
        assert event_types == sorted(event_types)


class TestSarifSchema:
    def test_schema_info(self, client):
        resp = client.get("/sarif/schema")
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == "2.1.0"
        assert body["tool"] == "SpiderFoot"
        assert "GitHub Code Scanning API" in body["supported_uploads"]
