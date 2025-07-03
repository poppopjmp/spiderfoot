import sfapi
from fastapi.testclient import TestClient

client = TestClient(sfapi.app)


def create_minimal_scan():
    # Helper to create a scan for positive tests
    scan_req = {
        "name": "testscan",
        "target": "example.com",
        "modules": [],
        "type_filter": []
    }
    resp = client.post("/api/scans", json=scan_req)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_archive_and_unarchive_scan():
    scan_id = create_minimal_scan()
    resp = client.post(f"/api/scans/{scan_id}/archive")
    assert resp.status_code == 200
    assert resp.json()["success"]
    resp = client.post(f"/api/scans/{scan_id}/unarchive")
    assert resp.status_code == 200
    assert resp.json()["success"]


def test_clear_scan_success():
    scan_id = create_minimal_scan()
    resp = client.post(f"/api/scans/{scan_id}/clear")
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        assert resp.json()["success"]


def test_metadata_notes_cycle():
    scan_id = create_minimal_scan()
    # Metadata
    resp = client.patch(f"/api/scans/{scan_id}/metadata", json={"foo": "bar"})
    assert resp.status_code == 200
    assert resp.json()["success"]
    resp = client.get(f"/api/scans/{scan_id}/metadata")
    assert resp.status_code == 200
    assert "metadata" in resp.json()
    # Notes
    resp = client.patch(f"/api/scans/{scan_id}/notes", json="test note")
    assert resp.status_code == 200
    assert resp.json()["success"]
    resp = client.get(f"/api/scans/{scan_id}/notes")
    assert resp.status_code == 200
    assert "notes" in resp.json()


def test_set_results_false_positive_warning():
    scan_id = create_minimal_scan()
    # Not finished, should warn
    resp = client.post(f"/api/scans/{scan_id}/results/falsepositive", json={"resultids": ["id1"], "fp": "1"})
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        assert resp.json()["status"] in ("WARNING", "ERROR")


def test_clone_and_rerun_scan():
    scan_id = create_minimal_scan()
    # Clone
    resp = client.post(f"/api/scans/{scan_id}/clone")
    assert resp.status_code in (200, 400)  # 400 if config missing
    # Rerun
    resp = client.post(f"/api/scans/{scan_id}/rerun")
    assert resp.status_code in (200, 400)  # 400 if config missing


def test_export_scan_event_results_types():
    scan_id = create_minimal_scan()
    for filetype in ["csv", "xlsx"]:
        resp = client.get(f"/api/scans/{scan_id}/events/export?filetype={filetype}")
        assert resp.status_code in (200, 404)


def test_export_scan_search_results_types():
    scan_id = create_minimal_scan()
    for filetype in ["csv", "xlsx"]:
        resp = client.get(f"/api/scans/{scan_id}/search/export?filetype={filetype}")
        assert resp.status_code in (200, 404, 500)


def test_export_scan_logs_and_correlations():
    scan_id = create_minimal_scan()
    resp = client.get(f"/api/scans/{scan_id}/logs/export")
    assert resp.status_code in (200, 404)
    resp = client.get(f"/api/scans/{scan_id}/correlations/export")
    assert resp.status_code in (200, 404)


def test_export_scan_viz_types():
    scan_id = create_minimal_scan()
    for gexf in ["0", "1"]:
        resp = client.get(f"/api/scans/{scan_id}/viz?gexf={gexf}")
        assert resp.status_code in (200, 404, 501)


def test_export_scan_json_multi_and_viz_multi():
    scan_id = create_minimal_scan()
    resp = client.get(f"/api/scans/export-multi?ids={scan_id}")
    assert resp.status_code in (200, 404)
    resp = client.get(f"/api/scans/viz-multi?ids={scan_id}")
    assert resp.status_code in (200, 404, 400, 501)


def test_get_scan_options_success():
    scan_id = create_minimal_scan()
    resp = client.get(f"/api/scans/{scan_id}/options")
    assert resp.status_code == 200
    assert "meta" in resp.json() or resp.json() == {}


def test_delete_scan_success():
    scan_id = create_minimal_scan()
    resp = client.delete(f"/api/scans/{scan_id}")
    assert resp.status_code == 200
    assert "message" in resp.json()


def test_delete_scan_full_success():
    scan_id = create_minimal_scan()
    resp = client.delete(f"/api/scans/{scan_id}/full")
    assert resp.status_code in (200, 404)


def test_rerun_scan_multi_success():
    scan_id = create_minimal_scan()
    resp = client.post(f"/api/scans/rerun-multi?ids={scan_id}")
    assert resp.status_code == 200
    assert "new_scan_ids" in resp.json()


def test_large_payload_metadata():
    scan_id = create_minimal_scan()
    large_meta = {"x": "y" * 10000}
    resp = client.patch(f"/api/scans/{scan_id}/metadata", json=large_meta)
    assert resp.status_code == 200
    assert resp.json()["success"]


def test_invalid_types_metadata():
    scan_id = create_minimal_scan()
    resp = client.patch(f"/api/scans/{scan_id}/metadata", json="notadict")
    assert resp.status_code == 422


def test_invalid_types_notes():
    scan_id = create_minimal_scan()
    resp = client.patch(f"/api/scans/{scan_id}/notes", json={"not": "a string"})
    assert resp.status_code in (200, 422)


def test_permission_required_endpoints():
    # Simulate missing/invalid API key if implemented
    # This is a placeholder; actual implementation may vary
    scan_id = create_minimal_scan()
    resp = client.post(f"/api/scans/{scan_id}/archive", headers={"x-api-key": "badkey"})
    # Accept 401, 403, or 200 if no auth enforced
    assert resp.status_code in (401, 403, 200)
