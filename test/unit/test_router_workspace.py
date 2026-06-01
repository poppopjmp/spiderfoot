"""Tests for spiderfoot.api.routers.workspace — workspace management API.

Workspaces are DB-backed via SpiderFootWorkspace; these tests substitute a
fake workspace class and a fake app config so the list/create/get/delete
endpoints (including the 404 path for unknown workspaces) are exercised without
a database.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.workspace as ws_mod
from spiderfoot.api.routers.workspace import router
from spiderfoot.api.dependencies import get_api_key


class _FakeConfig:
    def get_config(self):
        return {"__fake__": True}


class _FakeWorkspace:
    """In-memory stand-in for SpiderFootWorkspace, shared via a class store."""

    _store: dict[str, dict] = {}
    _counter = 0

    def __init__(self, config, workspace_id=None, name=None):
        if workspace_id is not None:
            if workspace_id not in self._store:
                raise ValueError(f"Workspace {workspace_id} not found")
            data = self._store[workspace_id]
            self.workspace_id = workspace_id
            self.name = data["name"]
            self.description = data.get("description", "")
            self.created_time = data.get("created_time", 0.0)
            self.modified_time = data.get("modified_time", 0.0)
            self.metadata = data.get("metadata", {})
        else:
            type(self)._counter += 1
            self.workspace_id = f"ws-{type(self)._counter}"
            self.name = name or "unnamed"
            self.description = ""
            self.created_time = 1000.0
            self.modified_time = 1000.0
            self.metadata = {}

    @classmethod
    def list_workspaces(cls, config):
        return [{"workspace_id": k, **v} for k, v in cls._store.items()]

    def save_workspace(self):
        self._store[self.workspace_id] = {
            "name": self.name, "description": self.description,
            "created_time": self.created_time, "modified_time": self.modified_time,
            "metadata": self.metadata,
        }

    def delete_workspace(self):
        self._store.pop(self.workspace_id, None)

    def get_targets(self):
        return []

    def get_scans(self):
        return []


@pytest.fixture
def client(monkeypatch):
    _FakeWorkspace._store = {}
    _FakeWorkspace._counter = 0
    monkeypatch.setattr(ws_mod, "get_app_config", lambda: _FakeConfig())
    monkeypatch.setattr(ws_mod, "SpiderFootWorkspace", _FakeWorkspace)
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _create(client, name="ws-a"):
    return client.post("/workspaces", json={"name": name, "description": "d"})


class TestList:
    def test_list_empty(self, client):
        resp = client.get("/workspaces")
        assert resp.status_code == 200

    def test_list_after_create(self, client):
        _create(client, name="findme")
        resp = client.get("/workspaces")
        assert resp.status_code == 200
        # paginate() wraps the list; just assert our workspace is present somewhere.
        assert "findme" in resp.text


class TestCreateGetDelete:
    def test_create_201(self, client):
        resp = _create(client)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "ws-a"
        assert body["workspace_id"]

    def test_get(self, client):
        wid = _create(client).json()["workspace_id"]
        resp = client.get(f"/workspaces/{wid}")
        assert resp.status_code == 200
        assert resp.json()["workspace_id"] == wid

    def test_get_unknown_404(self, client):
        assert client.get("/workspaces/nonexistent").status_code == 404

    def test_delete(self, client):
        wid = _create(client).json()["workspace_id"]
        assert client.delete(f"/workspaces/{wid}").status_code == 200
        assert client.get(f"/workspaces/{wid}").status_code == 404
