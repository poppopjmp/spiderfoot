import os
import tempfile
import time
import pytest
from fastapi.testclient import TestClient

from sfapi import app
from spiderfoot.workspace import SpiderFootWorkspace

@pytest.fixture(scope="module")
def client():
    db_fd, db_path = tempfile.mkstemp()
    os.environ['SPIDERFOOT_DB'] = db_path
    with TestClient(app) as c:
        yield c
    time.sleep(2)  # Wait for background tasks to finish using the DB
    os.close(db_fd)
    os.remove(db_path)

def test_workspace_lifecycle(client):
    resp = client.post("/api/workspaces", json={"name": "TestWS", "description": "desc"})
    assert resp.status_code == 201
    ws_id = resp.json()["workspace_id"]

    resp = client.get("/api/workspaces")
    assert resp.status_code == 200
    assert any(ws["workspace_id"] == ws_id for ws in resp.json()["workspaces"])

    resp = client.get(f"/api/workspaces/{ws_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "TestWS"

    target_data = {"target": "example.com", "target_type": "INTERNET_NAME", "metadata": {}}
    resp = client.post(f"/api/workspaces/{ws_id}/targets", json=target_data)
    assert resp.status_code == 201
    target_id = resp.json()["target_id"]

    resp = client.get(f"/api/workspaces/{ws_id}/targets")
    assert resp.status_code == 200
    assert any(t["target_id"] == target_id for t in resp.json()["targets"])

    resp = client.delete(f"/api/workspaces/{ws_id}/targets/{target_id}")
    assert resp.status_code == 200

    resp = client.delete(f"/api/workspaces/{ws_id}")
    assert resp.status_code == 200

def test_workspace_class_direct(tmp_path):
    config = {"__database": str(tmp_path / "test.db")}
    ws = SpiderFootWorkspace(config, name="DirectWS")
    assert ws.name == "DirectWS"
    tid = ws.add_target("1.2.3.4", "IP_ADDRESS")
    assert any(t["target_id"] == tid for t in ws.get_targets())
    ws.remove_target(tid)
    assert not ws.get_targets()
    ws.delete_workspace()

def test_workspace_export(client):
    resp = client.post("/api/workspaces", json={"name": "ExportWS", "description": "desc"})
    ws_id = resp.json()["workspace_id"]
    target_data = {"target": "export.com", "target_type": "INTERNET_NAME", "metadata": {}}
    client.post(f"/api/workspaces/{ws_id}/targets", json=target_data)
    # If you have an export endpoint, e.g., /api/workspaces/{ws_id}/export
    # resp = client.get(f"/api/workspaces/{ws_id}/export")
    # assert resp.status_code == 200
    # assert "workspace_info" in resp.json()
    client.delete(f"/api/workspaces/{ws_id}")

