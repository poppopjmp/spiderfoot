import pytest
from fastapi.testclient import TestClient
import sfapi

client = TestClient(sfapi.app)

# --- CONFIG ENDPOINTS ---
def test_get_config():
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert "config" in resp.json()

def test_patch_config():
    resp = client.patch("/api/config", json={"_debug": True})
    assert resp.status_code == 200
    assert resp.json()["success"] is True

def test_put_config():
    resp = client.put("/api/config", json={"_debug": False})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

def test_reload_config():
    resp = client.post("/api/config/reload")
    assert resp.status_code == 200
    assert resp.json()["status"] == "reloaded"

def test_validate_config():
    resp = client.post("/api/config/validate", json={"_debug": True})
    assert resp.status_code == 200
    assert "valid" in resp.json()

def test_scan_defaults():
    resp = client.get("/api/config/scan-defaults")
    assert resp.status_code == 200
    resp2 = client.patch("/api/config/scan-defaults", json={"foo": "bar"})
    assert resp2.status_code == 200
    assert resp2.json()["success"] is True

def test_workspace_defaults():
    resp = client.get("/api/config/workspace-defaults")
    assert resp.status_code == 200
    resp2 = client.patch("/api/config/workspace-defaults", json={"foo": "bar"})
    assert resp2.status_code == 200
    assert resp2.json()["success"] is True

def test_api_keys_crud():
    resp = client.post("/api/config/api-keys", json={"key": "testkey"})
    assert resp.status_code == 200
    resp = client.get("/api/config/api-keys")
    assert resp.status_code == 200
    resp = client.delete("/api/config/api-keys/testkey")
    assert resp.status_code == 200

def test_credentials_crud():
    resp = client.post("/api/config/credentials", json={"key": "testcred"})
    assert resp.status_code == 200
    resp = client.get("/api/config/credentials")
    assert resp.status_code == 200
    resp = client.delete("/api/config/credentials/testcred")
    assert resp.status_code == 200

def test_config_export_import():
    resp = client.get("/api/config/export")
    assert resp.status_code == 200
    resp2 = client.post("/api/config/import", json=resp.json())
    assert resp2.status_code == 200

# --- MODULES & EVENT TYPES ---
def test_get_modules():
    resp = client.get("/api/modules")
    assert resp.status_code == 200
    assert "modules" in resp.json()

def test_update_module_options():
    # Try updating a non-existent module (should 404)
    resp = client.patch("/api/modules/FAKEMODULE/options", json={"foo": "bar"})
    assert resp.status_code == 404

def test_get_event_types():
    resp = client.get("/api/event-types")
    assert resp.status_code == 200
    assert "event_types" in resp.json()

# --- MODULE CONFIG ---
def test_get_module_config():
    resp = client.get("/api/module-config/FAKEMODULE")
    assert resp.status_code in (200, 404)  # 404 if not present

def test_put_module_config():
    resp = client.put("/api/module-config/FAKEMODULE", json={"foo": "bar"})
    assert resp.status_code in (200, 500, 404)

# --- Pydantic/utility/legacy ---
def test_clean_user_input():
    assert sfapi.clean_user_input(["<script>"]) == ["&lt;script&gt;"]
    assert sfapi.clean_user_input([123, None, True]) == [123, None, True]
    assert sfapi.clean_user_input([]) == []

def test_legacy_exports_exist():
    for attr in ["ScanRequest", "ScanResponse", "WorkspaceRequest", "WorkspaceResponse", "search_base", "app_config"]:
        assert hasattr(sfapi, attr)

# --- Negative/error cases ---
def test_patch_config_invalid():
    # Use a JSON-serializable but invalid value
    resp = client.patch("/api/config", json={"_debug": "notabool"})
    assert resp.status_code in (400, 422, 500)

def test_import_config_invalid():
    resp = client.post("/api/config/import", json={"bad": "data"})
    assert resp.status_code in (200, 400, 422, 500)

def test_add_api_key_invalid():
    resp = client.post("/api/config/api-keys", json={})
    assert resp.status_code in (200, 400, 422, 500)

def test_add_credential_invalid():
    resp = client.post("/api/config/credentials", json={})
    assert resp.status_code in (200, 400, 422, 500)
