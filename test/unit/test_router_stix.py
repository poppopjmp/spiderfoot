"""Tests for spiderfoot.api.routers.stix — STIX 2.1 / TAXII 2.1 API.

Exercises the full round trip: export a STIX bundle (which registers a TAXII
collection), then read it back through the TAXII 2.1 discovery, collection,
and object endpoints. Also covers the supported-event-types listing and the
404 paths for unknown collections/objects. Auth is overridden for isolation.
"""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.stix import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.export.stix_export import _EVENT_TYPE_MAP


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def exported_collection(client):
    """Export a bundle and return (collection_id, response_body)."""
    known_type = next(iter(_EVENT_TYPE_MAP))
    events = [
        {"type": known_type, "data": "8.8.8.8", "module": "sfp_x"},
        {"type": known_type, "data": "1.1.1.1", "module": "sfp_x"},
    ]
    resp = client.post(
        "/stix/export",
        json={"scan_id": "stix-scan-1", "scan_name": "Round Trip",
              "scan_target": "example.com", "events": events},
    )
    assert resp.status_code == 200
    body = resp.json()
    return body["collection_id"], body


class TestStixExport:
    def test_export_produces_bundle_and_collection(self, exported_collection):
        collection_id, body = exported_collection
        assert body["bundle"]["type"] == "bundle"
        assert body["object_count"] >= 1
        assert collection_id  # a collection was registered

    def test_export_empty(self, client):
        resp = client.post("/stix/export", json={"scan_id": "empty"})
        assert resp.status_code == 200
        assert resp.json()["bundle"]["type"] == "bundle"

    def test_export_requires_scan_id(self, client):
        assert client.post("/stix/export", json={}).status_code == 422


class TestEventTypes:
    def test_lists_supported_types(self, client):
        resp = client.get("/stix/event-types")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == len(_EVENT_TYPE_MAP)
        assert len(body["supported_event_types"]) == body["total"]


class TestTaxiiDiscovery:
    def test_discovery(self, client):
        resp = client.get("/taxii2/")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/taxii+json")

    def test_api_root(self, client):
        assert client.get("/taxii2/root/").status_code == 200

    def test_list_collections(self, client):
        resp = client.get("/taxii2/collections/")
        assert resp.status_code == 200


class TestTaxiiCollectionRoundTrip:
    def test_get_collection(self, client, exported_collection):
        collection_id, _ = exported_collection
        resp = client.get(f"/taxii2/collections/{collection_id}/")
        assert resp.status_code == 200

    def test_get_objects(self, client, exported_collection):
        collection_id, _ = exported_collection
        resp = client.get(f"/taxii2/collections/{collection_id}/objects/")
        assert resp.status_code == 200

    def test_unknown_collection_404(self, client):
        resp = client.get("/taxii2/collections/nonexistent/")
        assert resp.status_code == 404

    def test_unknown_objects_collection_404(self, client):
        resp = client.get("/taxii2/collections/nonexistent/objects/")
        assert resp.status_code == 404

    def test_unknown_object_404(self, client, exported_collection):
        collection_id, _ = exported_collection
        resp = client.get(
            f"/taxii2/collections/{collection_id}/objects/no-such-object/")
        assert resp.status_code == 404
