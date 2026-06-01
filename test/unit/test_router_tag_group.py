"""Tests for spiderfoot.api.routers.tag_group.

Tag and group CRUD, assignment, and metadata endpoints, plus regression
coverage for /tags/stats and /tags/colors which were previously shadowed by
/tags/{tag_id}. Runs against a fresh in-memory TagGroupManager per test.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.tag_group as tg_mod
from spiderfoot.api.routers.tag_group import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.core.tag_group import TagGroupManager


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(tg_mod, "_manager", TagGroupManager())
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _tag(client, name="t1", color="blue"):
    return client.post("/tags", json={"name": name, "color": color})


def _group(client, name="g1"):
    return client.post("/groups", json={"name": name})


class TestTagCrud:
    def test_create_201(self, client):
        resp = _tag(client)
        assert resp.status_code == 201
        assert resp.json()["tag"]["name"] == "t1"

    def test_list_and_get(self, client):
        tid = _tag(client, name="findme").json()["tag"]["tag_id"]
        names = [t["name"] for t in client.get("/tags").json()["tags"]]
        assert "findme" in names
        assert client.get(f"/tags/{tid}").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get("/tags/nope").status_code == 404

    def test_update(self, client):
        tid = _tag(client).json()["tag"]["tag_id"]
        resp = client.patch(f"/tags/{tid}", json={"name": "renamed"})
        assert resp.status_code == 200
        assert resp.json()["updated"]["name"] == "renamed"

    def test_delete(self, client):
        tid = _tag(client).json()["tag"]["tag_id"]
        assert client.delete(f"/tags/{tid}").status_code == 200
        assert client.get(f"/tags/{tid}").status_code == 404

    def test_tree(self, client):
        _tag(client)
        assert client.get("/tags/tree").status_code == 200


class TestGroupCrud:
    def test_create_and_get(self, client):
        gid = _group(client).json()["group"]["group_id"]
        assert client.get(f"/groups/{gid}").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get("/groups/nope").status_code == 404

    def test_add_and_remove_member(self, client):
        gid = _group(client).json()["group"]["group_id"]
        assert client.post(f"/groups/{gid}/members",
                           json={"member": "host-1"}).status_code == 200
        assert client.delete(f"/groups/{gid}/members/host-1").status_code == 200


class TestAssignment:
    def test_assign_and_unassign(self, client):
        tid = _tag(client).json()["tag"]["tag_id"]
        assign = {"tag_id": tid, "resource_type": "scan", "resource_id": "scan-1"}
        assert client.post("/tags/assign", json=assign).status_code == 200
        assert client.post("/tags/unassign", json=assign).status_code == 200

    def test_assign_unknown_tag_404(self, client):
        assert client.post("/tags/assign", json={
            "tag_id": "nope", "resource_type": "scan", "resource_id": "s",
        }).status_code == 404


class TestLiteralSubPathsNotShadowed:
    def test_stats(self, client):
        resp = client.get("/tags/stats")
        assert resp.status_code == 200, "/tags/stats was shadowed by /tags/{tag_id}"
        assert isinstance(resp.json(), dict)

    def test_colors(self, client):
        resp = client.get("/tags/colors")
        assert resp.status_code == 200, "/tags/colors was shadowed by /tags/{tag_id}"
        assert "colors" in resp.json()
