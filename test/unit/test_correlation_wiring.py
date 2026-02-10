"""
Tests for Cycle 26 — Correlation Service Wiring.

Covers:
  - CorrelationService CRUD methods (get_rule, add_rule, update_rule,
    delete_rule, filter_rules)
  - FastAPI Depends provider (get_correlation_svc)
  - Correlations router endpoints via Starlette TestClient
"""
from __future__ import annotations

import time
import threading
from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

# -----------------------------------------------------------------------
# CorrelationService imports
# -----------------------------------------------------------------------
from spiderfoot.correlation_service import (
    CorrelationService,
    CorrelationServiceConfig,
    CorrelationResult,
    CorrelationTrigger,
    get_correlation_service,
)


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _make_svc(rules=None):
    """Create a CorrelationService with pre-loaded rules (no disk I/O)."""
    cfg = CorrelationServiceConfig(
        rules_dir="/nonexistent",
        trigger=CorrelationTrigger.MANUAL,
        subscribe_events=False,
    )
    svc = CorrelationService(cfg)
    if rules:
        svc._rules = list(rules)
    return svc


def _sample_rules():
    return [
        {"id": "r1", "name": "Rule 1", "risk": "HIGH", "enabled": True,
         "tags": ["net"], "logic": "x > 1", "description": "d1"},
        {"id": "r2", "name": "Rule 2", "risk": "MEDIUM", "enabled": False,
         "tags": ["web"], "logic": "x > 2", "description": "d2"},
        {"id": "r3", "name": "Rule 3", "risk": "LOW", "enabled": True,
         "tags": ["net", "web"], "logic": "x > 3", "description": "d3"},
    ]


# ===================================================================
# 1. CorrelationService — rule CRUD
# ===================================================================

class TestCorrelationServiceCRUD:
    """Tests for get_rule / add_rule / update_rule / delete_rule."""

    def test_get_rule_found(self):
        svc = _make_svc(_sample_rules())
        r = svc.get_rule("r2")
        assert r is not None
        assert r["name"] == "Rule 2"

    def test_get_rule_not_found(self):
        svc = _make_svc(_sample_rules())
        assert svc.get_rule("nonexistent") is None

    def test_get_rule_returns_copy(self):
        svc = _make_svc(_sample_rules())
        r = svc.get_rule("r1")
        r["name"] = "CHANGED"
        assert svc.get_rule("r1")["name"] == "Rule 1"

    def test_add_rule_with_id(self):
        svc = _make_svc([])
        rule = svc.add_rule({"id": "new1", "name": "New"})
        assert rule["id"] == "new1"
        assert svc.rule_count == 1

    def test_add_rule_generates_id(self):
        svc = _make_svc([])
        rule = svc.add_rule({"name": "Auto-ID"})
        assert "id" in rule and rule["id"]
        assert svc.rule_count == 1

    def test_add_rule_does_not_mutate_original(self):
        svc = _make_svc([])
        orig = {"name": "Immutable"}
        svc.add_rule(orig)
        assert "id" not in orig  # original dict untouched

    def test_update_rule_merges_fields(self):
        svc = _make_svc(_sample_rules())
        updated = svc.update_rule("r1", {"name": "Updated", "risk": "LOW"})
        assert updated is not None
        assert updated["name"] == "Updated"
        assert updated["risk"] == "LOW"
        # Unchanged fields preserved
        assert updated["logic"] == "x > 1"

    def test_update_rule_prevents_id_overwrite(self):
        svc = _make_svc(_sample_rules())
        updated = svc.update_rule("r1", {"id": "HACKED"})
        assert updated["id"] == "r1"

    def test_update_rule_not_found(self):
        svc = _make_svc(_sample_rules())
        assert svc.update_rule("nope", {"name": "X"}) is None

    def test_delete_rule_removes(self):
        svc = _make_svc(_sample_rules())
        assert svc.delete_rule("r2") is True
        assert svc.rule_count == 2
        assert svc.get_rule("r2") is None

    def test_delete_rule_not_found(self):
        svc = _make_svc(_sample_rules())
        assert svc.delete_rule("nope") is False
        assert svc.rule_count == 3


# ===================================================================
# 2. filter_rules
# ===================================================================

class TestFilterRules:
    def test_no_filters(self):
        svc = _make_svc(_sample_rules())
        assert len(svc.filter_rules()) == 3

    def test_filter_by_risk(self):
        svc = _make_svc(_sample_rules())
        assert len(svc.filter_rules(risk="high")) == 1

    def test_filter_by_enabled(self):
        svc = _make_svc(_sample_rules())
        assert len(svc.filter_rules(enabled=True)) == 2

    def test_filter_by_tag(self):
        svc = _make_svc(_sample_rules())
        assert len(svc.filter_rules(tag="web")) == 2

    def test_filter_combined(self):
        svc = _make_svc(_sample_rules())
        assert len(svc.filter_rules(risk="low", tag="net")) == 1

    def test_filter_no_match(self):
        svc = _make_svc(_sample_rules())
        assert len(svc.filter_rules(risk="CRITICAL")) == 0


# ===================================================================
# 3. Singleton accessor
# ===================================================================

class TestSingleton:
    def test_get_correlation_service_creates_instance(self):
        import spiderfoot.correlation_service as mod
        old = mod._instance
        try:
            mod._instance = None
            svc = get_correlation_service({})
            assert isinstance(svc, CorrelationService)
        finally:
            mod._instance = old

    def test_get_correlation_service_returns_same(self):
        import spiderfoot.correlation_service as mod
        old = mod._instance
        try:
            mod._instance = None
            svc1 = get_correlation_service({})
            svc2 = get_correlation_service({})
            assert svc1 is svc2
        finally:
            mod._instance = old


# ===================================================================
# 4. FastAPI Depends provider
# ===================================================================

class TestDependsProvider:
    def test_get_correlation_svc_returns_service(self):
        import spiderfoot.correlation_service as mod
        old = mod._instance
        try:
            mod._instance = None
            fake_config = MagicMock()
            fake_config.get_config.return_value = {}
            with patch("spiderfoot.api.dependencies.get_app_config", return_value=fake_config):
                from spiderfoot.api.dependencies import get_correlation_svc
                svc = get_correlation_svc()
                assert isinstance(svc, CorrelationService)
        finally:
            mod._instance = old


# ===================================================================
# 5. Router endpoint tests (via TestClient)
# ===================================================================

class TestCorrelationsRouter:
    """Integration tests using Starlette TestClient."""

    @staticmethod
    def _make_app():
        """Build a minimal FastAPI app with the correlations router."""
        from fastapi import FastAPI
        from spiderfoot.api.routers.correlations import router

        app = FastAPI()
        app.include_router(router)
        return app

    @staticmethod
    def _make_client(svc=None):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from spiderfoot.api.routers.correlations import router

        app = FastAPI()
        app.include_router(router)

        if svc is None:
            svc = _make_svc(_sample_rules())

        # Override dependency
        from spiderfoot.api.dependencies import get_correlation_svc
        app.dependency_overrides[get_correlation_svc] = lambda: svc
        # Disable auth
        from spiderfoot.api.dependencies import optional_auth
        app.dependency_overrides[optional_auth] = lambda: None

        return TestClient(app), svc

    # --- list ---
    def test_list_rules(self):
        client, _ = self._make_client()
        resp = client.get("/correlation-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_rules_filter_risk(self):
        client, _ = self._make_client()
        resp = client.get("/correlation-rules?risk=HIGH")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_rules_filter_enabled(self):
        client, _ = self._make_client()
        resp = client.get("/correlation-rules?enabled=false")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_rules_pagination(self):
        client, _ = self._make_client()
        resp = client.get("/correlation-rules?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["has_next"] is True

    # --- create ---
    def test_create_rule(self):
        client, svc = self._make_client()
        resp = client.post("/correlation-rules", json={
            "name": "New Rule",
            "description": "Desc",
            "risk": "high",
            "logic": "a == b",
        })
        assert resp.status_code == 201
        assert "rule" in resp.json()
        assert svc.rule_count == 4

    # --- get ---
    def test_get_rule(self):
        client, _ = self._make_client()
        resp = client.get("/correlation-rules/r1")
        assert resp.status_code == 200
        assert resp.json()["rule"]["name"] == "Rule 1"

    def test_get_rule_not_found(self):
        client, _ = self._make_client()
        resp = client.get("/correlation-rules/nonexistent")
        assert resp.status_code == 404

    # --- update ---
    def test_update_rule(self):
        client, svc = self._make_client()
        resp = client.put("/correlation-rules/r1", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["rule"]["name"] == "Renamed"
        assert svc.get_rule("r1")["name"] == "Renamed"

    def test_update_rule_not_found(self):
        client, _ = self._make_client()
        resp = client.put("/correlation-rules/nope", json={"name": "X"})
        assert resp.status_code == 404

    # --- delete ---
    def test_delete_rule(self):
        client, svc = self._make_client()
        resp = client.delete("/correlation-rules/r2")
        assert resp.status_code == 200
        assert svc.rule_count == 2

    def test_delete_rule_not_found(self):
        client, _ = self._make_client()
        resp = client.delete("/correlation-rules/nope")
        assert resp.status_code == 404

    # --- test endpoint ---
    def test_test_rule_missing_scan_id(self):
        client, _ = self._make_client()
        resp = client.post("/correlation-rules/r1/test", json={"foo": "bar"})
        assert resp.status_code == 400

    def test_test_rule_not_found(self):
        client, _ = self._make_client()
        resp = client.post("/correlation-rules/nope/test",
                           json={"scan_id": "s1"})
        assert resp.status_code == 404

    def test_test_rule_executes(self):
        svc = _make_svc(_sample_rules())
        # Patch run_for_scan to return empty (no correlations)
        svc.run_for_scan = MagicMock(return_value=[])
        client, _ = self._make_client(svc)
        resp = client.post("/correlation-rules/r1/test",
                           json={"scan_id": "s1"})
        assert resp.status_code == 200
        tr = resp.json()["test_result"]
        assert tr["test_passed"] is True
        assert tr["match_count"] == 0
        svc.run_for_scan.assert_called_once_with("s1", rule_ids=["r1"])

    # --- detailed scan correlations ---
    def test_detailed_correlations_empty(self):
        svc = _make_svc(_sample_rules())
        svc.run_for_scan = MagicMock(return_value=[])
        client, _ = self._make_client(svc)
        resp = client.get("/scans/s1/correlations/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scan_id"] == "s1"
        assert data["total"] == 0

    def test_detailed_correlations_with_results(self):
        svc = _make_svc(_sample_rules())
        results = [
            CorrelationResult(
                rule_id="r1", rule_name="Rule 1", headline="H1",
                risk="HIGH", scan_id="s1", event_count=3,
            ),
            CorrelationResult(
                rule_id="r2", rule_name="Rule 2", headline="H2",
                risk="MEDIUM", scan_id="s1", event_count=1,
            ),
        ]
        svc.run_for_scan = MagicMock(return_value=results)
        client, _ = self._make_client(svc)
        resp = client.get("/scans/s1/correlations/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["summary"]["high_risk_count"] == 1

    def test_detailed_correlations_risk_filter(self):
        svc = _make_svc(_sample_rules())
        results = [
            CorrelationResult(
                rule_id="r1", rule_name="Rule 1", headline="H1",
                risk="HIGH", scan_id="s1", event_count=3,
            ),
            CorrelationResult(
                rule_id="r2", rule_name="Rule 2", headline="H2",
                risk="LOW", scan_id="s1", event_count=1,
            ),
        ]
        svc.run_for_scan = MagicMock(return_value=results)
        client, _ = self._make_client(svc)
        resp = client.get("/scans/s1/correlations/detailed?risk=HIGH")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    # --- analyze ---
    def test_analyze_no_scan_ids(self):
        client, _ = self._make_client()
        resp = client.post("/correlations/analyze", json={"scan_ids": []})
        assert resp.status_code == 400

    def test_analyze_multi_scan(self):
        svc = _make_svc(_sample_rules())
        svc.run_for_scan = MagicMock(return_value=[
            CorrelationResult(
                rule_id="r1", rule_name="Rule 1", headline="H",
                risk="HIGH", scan_id="sx", event_count=1,
            ),
        ])
        client, _ = self._make_client(svc)
        resp = client.post("/correlations/analyze", json={
            "scan_ids": ["s1", "s2"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["scan_count"] == 2
        assert data["total_correlations_analyzed"] == 2
        assert len(data["patterns"]["common_correlations"]) == 1
        assert svc.run_for_scan.call_count == 2
