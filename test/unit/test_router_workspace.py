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

    _target_counter = 0

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
            self._targets = data.get("targets", [])
            self._scans = data.get("scans", [])
        else:
            type(self)._counter += 1
            self.workspace_id = f"ws-{type(self)._counter}"
            self.name = name or "unnamed"
            self.description = ""
            self.created_time = 1000.0
            self.modified_time = 1000.0
            self.metadata = {}
            self._targets = []
            self._scans = []

    @classmethod
    def list_workspaces(cls, config):
        return [{"workspace_id": k, **v} for k, v in cls._store.items()]

    def save_workspace(self):
        self._store[self.workspace_id] = {
            "name": self.name, "description": self.description,
            "created_time": self.created_time, "modified_time": self.modified_time,
            "metadata": self.metadata, "targets": self._targets,
            "scans": self._scans,
        }

    def delete_workspace(self):
        self._store.pop(self.workspace_id, None)

    def get_targets(self):
        return self._targets

    def add_target(self, value, target_type, metadata=None):
        type(self)._target_counter += 1
        tid = f"tgt-{type(self)._target_counter}"
        self._targets.append({"id": tid, "value": value, "type": target_type,
                              "metadata": metadata or {}})
        self.save_workspace()
        return tid

    def remove_target(self, target_id):
        before = len(self._targets)
        self._targets = [t for t in self._targets if t["id"] != target_id]
        self.save_workspace()
        return len(self._targets) < before

    def get_scans(self):
        return self._scans

    def remove_scan(self, scan_id):
        present = scan_id in self._scans
        self._scans = [s for s in self._scans if s != scan_id]
        self.save_workspace()
        return present

    def import_single_scan(self, scan_id):
        if scan_id in self._scans:
            return False
        self._scans.append(scan_id)
        self.save_workspace()
        return True

    def get_workspace_summary(self):
        return {"workspace_id": self.workspace_id, "name": self.name,
                "target_count": len(self._targets), "scan_count": len(self._scans)}


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


class TestUpdate:
    def test_update_via_query_params(self, client):
        # NOTE: update_workspace binds name/description as query params (not a
        # JSON body); this test documents that actual contract.
        wid = _create(client).json()["workspace_id"]
        resp = client.put(f"/workspaces/{wid}",
                          params={"name": "renamed", "description": "new"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert client.get(f"/workspaces/{wid}").json()["name"] == "renamed"

    def test_update_unknown_404(self, client):
        assert client.put("/workspaces/nope",
                         params={"name": "x"}).status_code == 404


class TestSummary:
    def test_summary(self, client):
        wid = _create(client).json()["workspace_id"]
        resp = client.get(f"/workspaces/{wid}/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["summary"]["workspace_id"] == wid

    def test_summary_unknown_404(self, client):
        assert client.get("/workspaces/nope/summary").status_code == 404


class TestTargets:
    def test_add_list_remove(self, client):
        wid = _create(client).json()["workspace_id"]
        add = client.post(f"/workspaces/{wid}/targets",
                         json={"target": "8.8.8.8", "target_type": "IP_ADDRESS"})
        assert add.status_code == 201
        tid = add.json()["target_id"]
        listing = client.get(f"/workspaces/{wid}/targets")
        assert listing.status_code == 200
        assert client.delete(f"/workspaces/{wid}/targets/{tid}").status_code == 200

    def test_add_target_type_mismatch_422(self, client):
        wid = _create(client).json()["workspace_id"]
        # 8.8.8.8 is detected as IP_ADDRESS, not INTERNET_NAME.
        resp = client.post(f"/workspaces/{wid}/targets",
                          json={"target": "8.8.8.8", "target_type": "INTERNET_NAME"})
        assert resp.status_code == 422

    def test_remove_unknown_target_404(self, client):
        wid = _create(client).json()["workspace_id"]
        assert client.delete(
            f"/workspaces/{wid}/targets/nope").status_code == 404


class TestMetadata:
    def test_patch_metadata(self, client):
        wid = _create(client).json()["workspace_id"]
        resp = client.patch(f"/workspaces/{wid}/metadata",
                           json={"owner": "alice"})
        assert resp.status_code == 200
        assert resp.json()["metadata"]["owner"] == "alice"

    def test_patch_metadata_unknown_404(self, client):
        assert client.patch("/workspaces/nope/metadata",
                           json={"k": "v"}).status_code == 404


class TestCloneAndScans:
    def test_clone_copies_targets(self, client):
        wid = _create(client, name="orig").json()["workspace_id"]
        client.post(f"/workspaces/{wid}/targets",
                   json={"target": "8.8.8.8", "target_type": "IP_ADDRESS"})
        resp = client.post(f"/workspaces/{wid}/clone")
        assert resp.status_code == 201
        assert "Clone" in resp.json()["name"]

    def test_link_scan_then_clear(self, client):
        wid = _create(client).json()["workspace_id"]
        link = client.post(f"/workspaces/{wid}/scans/scan-1")
        assert link.status_code == 200
        # Linking the same scan again is a no-op message, not an error.
        again = client.post(f"/workspaces/{wid}/scans/scan-1")
        assert again.status_code == 200
        assert client.post(f"/workspaces/{wid}/clear").status_code == 200

    def test_set_active(self, client):
        wid = _create(client).json()["workspace_id"]
        assert client.post(f"/workspaces/{wid}/set-active").status_code == 200

    def test_set_active_unknown_404(self, client):
        assert client.post("/workspaces/nope/set-active").status_code == 404


class TestNotFoundStatusPreserved:
    """Regression: these intended 4xx codes were swallowed by a broad
    'except Exception' and returned as 500. They must keep their status."""

    def test_multi_scan_no_targets_400(self, client):
        # A workspace with no targets and an empty request -> 400, not 500.
        wid = _create(client).json()["workspace_id"]
        resp = client.post(f"/workspaces/{wid}/multi-scan",
                          json={"targets": [], "modules": []})
        assert resp.status_code == 400

    def test_remove_unknown_scan_404(self, client):
        wid = _create(client).json()["workspace_id"]
        # Scan never linked -> remove_scan returns falsy -> 404, not 500.
        resp = client.delete(f"/workspaces/{wid}/scans/never-linked")
        assert resp.status_code == 404
