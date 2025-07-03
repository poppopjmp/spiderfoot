import pytest
from fastapi.testclient import TestClient
import sfapi

client = TestClient(sfapi.app)

# --- SCAN ENDPOINTS ---
def test_list_scans():
    resp = client.get("/api/scans")
    assert resp.status_code == 200
    assert "scans" in resp.json()

def test_create_scan_invalid():
    # Missing required fields
    resp = client.post("/api/scans", json={})
    assert resp.status_code in (400, 422)

def test_get_scan_not_found():
    resp = client.get("/api/scans/FAKESCANID")
    assert resp.status_code == 404

def test_delete_scan_not_found():
    resp = client.delete("/api/scans/FAKESCANID")
    assert resp.status_code == 404

def test_delete_scan_full_not_found():
    resp = client.delete("/api/scans/FAKESCANID/full")
    assert resp.status_code == 404

def test_stop_scan_not_found():
    resp = client.post("/api/scans/FAKESCANID/stop")
    assert resp.status_code == 404

def test_export_scan_event_results_not_found():
    resp = client.get("/api/scans/FAKESCANID/events/export")
    assert resp.status_code in (404, 500)

def test_export_scan_json_multi_empty():
    resp = client.get("/api/scans/export-multi?ids=FAKESCANID")
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        assert resp.headers["content-type"].startswith("application/json")

def test_export_scan_search_results_not_found():
    resp = client.get("/api/scans/FAKESCANID/search/export")
    assert resp.status_code in (404, 500)

def test_export_scan_viz_not_found():
    resp = client.get("/api/scans/FAKESCANID/viz")
    assert resp.status_code == 404

def test_export_scan_viz_multi_empty():
    resp = client.get("/api/scans/viz-multi?ids=FAKESCANID")
    assert resp.status_code in (404, 400)

def test_get_scan_options_not_found():
    resp = client.get("/api/scans/FAKESCANID/options")
    assert resp.status_code == 200
    assert resp.json() == {}

def test_rerun_scan_not_found():
    resp = client.post("/api/scans/FAKESCANID/rerun")
    assert resp.status_code == 404

def test_rerun_scan_multi_empty():
    resp = client.post("/api/scans/rerun-multi?ids=FAKESCANID")
    assert resp.status_code == 200
    assert "new_scan_ids" in resp.json()

def test_clone_scan_not_found():
    resp = client.post("/api/scans/FAKESCANID/clone")
    assert resp.status_code == 404

def test_set_results_false_positive_invalid():
    resp = client.post("/api/scans/FAKESCANID/results/falsepositive", json={"resultids": ["id1"], "fp": "2"})
    assert resp.status_code in (400, 422)

def test_export_scan_logs_not_found():
    resp = client.get("/api/scans/FAKESCANID/logs/export")
    assert resp.status_code == 404

def test_export_scan_correlations_not_found():
    resp = client.get("/api/scans/FAKESCANID/correlations/export")
    assert resp.status_code == 404

def test_get_scan_metadata_not_found():
    resp = client.get("/api/scans/FAKESCANID/metadata")
    assert resp.status_code == 404

def test_update_scan_metadata_not_found():
    resp = client.patch("/api/scans/FAKESCANID/metadata", json={"foo": "bar"})
    assert resp.status_code == 404

def test_get_scan_notes_not_found():
    resp = client.get("/api/scans/FAKESCANID/notes")
    assert resp.status_code == 404

def test_update_scan_notes_not_found():
    resp = client.patch("/api/scans/FAKESCANID/notes", json="test note")
    assert resp.status_code == 404

def test_archive_scan_not_found():
    resp = client.post("/api/scans/FAKESCANID/archive")
    assert resp.status_code == 404

def test_unarchive_scan_not_found():
    resp = client.post("/api/scans/FAKESCANID/unarchive")
    assert resp.status_code == 404

def test_clear_scan_not_found():
    resp = client.post("/api/scans/FAKESCANID/clear")
    assert resp.status_code == 404
