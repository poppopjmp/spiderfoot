"""Tests for spiderfoot.api.routers.asm — attack-surface asset inventory.

Covers event ingestion (single + batch), asset retrieval, tagging, linking,
removal, summary, and the type/risk enumerations, against a fresh in-memory
AssetInventory per test.

Includes a regression test for a ternary-precedence bug in
``AssetInventory.ingest_event`` that set ``asset.risk = None`` for non-risk
events, which then crashed ``Asset.to_dict()`` with AttributeError — so
``POST /asm/ingest`` previously 500'd for ordinary events like DOMAIN_NAME.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.asm as asm_mod
from spiderfoot.api.routers.asm import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.scan.asm import AssetInventory


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(asm_mod, "_inventory", AssetInventory())
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _ingest(client, event_type="IP_ADDRESS", data="8.8.8.8"):
    return client.post("/asm/ingest", json={"event_type": event_type, "data": data})


class TestIngestRegression:
    def test_non_risk_event_does_not_crash(self, client):
        # Regression: this used to 500 (AttributeError: NoneType has no .value).
        resp = _ingest(client, event_type="DOMAIN_NAME", data="example.com")
        assert resp.status_code == 200
        assert resp.json()["asset"]["risk"] == "unknown"

    def test_unmapped_event_ignored(self, client):
        # Event types with no asset mapping are ignored, not errors.
        resp = _ingest(client, event_type="SOME_RANDOM_EVENT", data="x")
        assert resp.status_code == 200


class TestIngestAndRetrieve:
    def test_ingest_creates_asset(self, client):
        resp = _ingest(client)
        assert resp.status_code == 200
        asset = resp.json()["asset"]
        assert asset["value"] == "8.8.8.8"
        assert asset["asset_type"] == "ip_address"

    def test_batch_ingest(self, client):
        resp = client.post("/asm/ingest/batch", json={"events": [
            {"event_type": "DOMAIN_NAME", "data": "a.com"},
            {"event_type": "EMAILADDR", "data": "x@a.com"},
        ]})
        assert resp.status_code == 200
        # Both mapped events should have produced assets.
        assert client.get("/asm/summary").status_code == 200

    def test_get_asset(self, client):
        aid = _ingest(client).json()["asset"]["asset_id"]
        assert client.get(f"/asm/assets/{aid}").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get("/asm/assets/deadbeefdeadbeef").status_code == 404

    def test_list_and_summary(self, client):
        _ingest(client)
        assert client.get("/asm/assets").status_code == 200
        assert client.get("/asm/summary").status_code == 200


class TestMutations:
    def test_add_tag(self, client):
        aid = _ingest(client).json()["asset"]["asset_id"]
        resp = client.post(f"/asm/assets/{aid}/tags",
                           json={"key": "env", "value": "prod"})
        assert resp.status_code == 200

    def test_link_assets(self, client):
        a1 = _ingest(client, data="8.8.8.8").json()["asset"]["asset_id"]
        a2 = _ingest(client, data="1.1.1.1").json()["asset"]["asset_id"]
        resp = client.post("/asm/link",
                           json={"asset_id_1": a1, "asset_id_2": a2})
        assert resp.status_code == 200

    def test_delete_asset(self, client):
        aid = _ingest(client).json()["asset"]["asset_id"]
        assert client.delete(f"/asm/assets/{aid}").status_code == 200


class TestEnumerations:
    def test_types(self, client):
        types = client.get("/asm/types").json()["types"]
        assert any(t["name"] == "IP_ADDRESS" for t in types)

    def test_risks(self, client):
        risks = client.get("/asm/risks").json()["risks"]
        names = {r["name"] for r in risks}
        assert {"CRITICAL", "UNKNOWN"} <= names
