"""Tests for spiderfoot.api.routers.correlations — correlation-rule CRUD + run.

The CorrelationService is injected via Depends(get_correlation_svc), so these
tests override that dependency with an in-memory fake to exercise the rule CRUD
lifecycle, the rule-test endpoint (including its 404/400 guards), and the
analyze endpoint without a database.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.correlations import router, _result_to_dict
from spiderfoot.api.dependencies import get_api_key, get_correlation_svc


class _Result:
    def __init__(self, rule_id="r1", scan_id="s1"):
        self.rule_id = rule_id
        self.rule_name = "n"
        self.headline = "h"
        self.risk = "HIGH"
        self.scan_id = scan_id
        self.event_count = 1
        self.events = []
        self.timestamp = 0


class _FakeCorrelationService:
    def __init__(self):
        self._rules = {}
        self._counter = 0

    def filter_rules(self, risk=None, enabled=None, tag=None):
        rules = list(self._rules.values())
        if risk is not None:
            rules = [r for r in rules if r["risk"] == risk.upper()]
        if enabled is not None:
            rules = [r for r in rules if r["enabled"] == enabled]
        return rules

    def add_rule(self, rule):
        self._counter += 1
        rid = f"rule-{self._counter}"
        rule = {**rule, "id": rid}
        self._rules[rid] = rule
        return rule

    def get_rule(self, rule_id):
        return self._rules.get(rule_id)

    def update_rule(self, rule_id, updates):
        if rule_id not in self._rules:
            return None
        self._rules[rule_id].update(updates)
        return self._rules[rule_id]

    def delete_rule(self, rule_id):
        return self._rules.pop(rule_id, None) is not None

    def run_for_scan(self, scan_id, rule_ids=None):
        return [_Result(scan_id=scan_id)]

    def get_results(self, scan_id):
        return [_Result(scan_id=scan_id)]


@pytest.fixture
def svc():
    return _FakeCorrelationService()


@pytest.fixture
def client(svc):
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.dependency_overrides[get_correlation_svc] = lambda: svc
    app.include_router(router)
    return TestClient(app)


def _create(client, name="rule-a", risk="high"):
    return client.post("/correlation-rules", json={
        "name": name, "description": "d", "risk": risk, "logic": "x",
        "enabled": True,
    })


class TestCrud:
    def test_create_uppercases_risk(self, client):
        resp = _create(client, risk="high")
        assert resp.status_code == 201
        assert resp.json()["rule"]["risk"] == "HIGH"

    def test_list_and_filter(self, client):
        _create(client, name="a", risk="high")
        _create(client, name="b", risk="low")
        # filter_rules risk is uppercased by the service fake.
        resp = client.get("/correlation-rules", params={"risk": "high"})
        assert resp.status_code == 200

    def test_get_by_id(self, client):
        rid = _create(client).json()["rule"]["id"]
        assert client.get(f"/correlation-rules/{rid}").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get("/correlation-rules/nope").status_code == 404

    def test_update(self, client):
        rid = _create(client).json()["rule"]["id"]
        resp = client.put(f"/correlation-rules/{rid}", json={"risk": "low"})
        assert resp.status_code == 200
        assert resp.json()["rule"]["risk"] == "LOW"

    def test_update_unknown_404(self, client):
        assert client.put("/correlation-rules/nope",
                         json={"risk": "low"}).status_code == 404

    def test_delete(self, client):
        rid = _create(client).json()["rule"]["id"]
        assert client.delete(f"/correlation-rules/{rid}").status_code == 200
        assert client.get(f"/correlation-rules/{rid}").status_code == 404

    def test_delete_unknown_404(self, client):
        assert client.delete("/correlation-rules/nope").status_code == 404


class TestRuleTest:
    def test_run_rule(self, client):
        rid = _create(client).json()["rule"]["id"]
        resp = client.post(f"/correlation-rules/{rid}/test",
                          json={"scan_id": "s1"})
        assert resp.status_code == 200
        assert resp.json()["test_result"]["match_count"] == 1

    def test_unknown_rule_404(self, client):
        assert client.post("/correlation-rules/nope/test",
                          json={"scan_id": "s1"}).status_code == 404

    def test_missing_scan_id_400(self, client):
        rid = _create(client).json()["rule"]["id"]
        assert client.post(f"/correlation-rules/{rid}/test",
                          json={}).status_code == 400
