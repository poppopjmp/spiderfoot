import os
import time
import requests
import pytest
from typing import Dict, Any

# Base URL for the live SpiderFoot API (proxied via frontend)
BASE_URL = os.environ.get("SF_TEST_API_URL", "http://localhost:3000")
USERNAME = os.environ.get("SF_TEST_USERNAME", "admin")
PASSWORD = os.environ.get("SF_TEST_PASSWORD", "admin")

@pytest.fixture(scope="module")
def api_session() -> requests.Session:
    """Fixture to provide an authenticated session for API requests."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def auth_token(api_session: requests.Session) -> str:
    """Fixture to obtain an authentication token and attach it to the session."""
    url = f"{BASE_URL}/api/v1/auth/login"
    payload = {"username": USERNAME, "password": PASSWORD}
    response = api_session.post(url, json=payload)
    
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "access_token" in data, "No access token in login response"
    
    token = data["access_token"]
    api_session.headers.update({"Authorization": f"Bearer {token}"})
    return token

def test_api_health():
    """Verify that the API and overall system health is OK."""
    url = f"{BASE_URL}/health"
    response = requests.get(url)
    assert response.status_code == 200, f"System health check failed: {response.text}"
    data = response.json()
    assert data.get("status") == "up", f"System is not healthy: {data}"

def test_authentication(auth_token: str):
    """Verify that authentication produces a valid token."""
    assert isinstance(auth_token, str)
    assert len(auth_token) > 10

def test_scan_lifecycle_and_output(api_session: requests.Session):
    """Verify end-to-end scan creation, execution, completion, and output generation."""
    
    # 1. Create a fast scan
    url = f"{BASE_URL}/api/v1/scans"
    payload = {
        "name": "e2e-test-scan",
        "target": "spiderfoot.net",
        "modules": ["sfp_dnsresolve"]
    }
    
    response = api_session.post(url, json=payload)
    assert response.status_code in (200, 201), f"Scan creation failed: {response.text}"
    scan_data = response.json()
    
    scan_id = scan_data.get("id")
    assert scan_id is not None, "Scan ID not returned"
    
    # 2. Poll for scan completion
    max_retries = 30
    poll_interval = 2.0
    scan_finished = False
    
    for i in range(max_retries):
        status_url = f"{BASE_URL}/api/v1/scans/{scan_id}"
        status_resp = api_session.get(status_url)
        assert status_resp.status_code == 200, f"Failed to get scan status: {status_resp.text}"
        
        status_data = status_resp.json()
        current_status = status_data.get("status", "").upper()
        
        if current_status == "FINISHED":
            scan_finished = True
            break
        elif current_status in ("ERROR", "ABORTED"):
            pytest.fail(f"Scan ended in error state: {current_status}")
            
        time.sleep(poll_interval)
        
    assert scan_finished, f"Scan {scan_id} did not finish within {max_retries * poll_interval} seconds"
    
    # 3. Verify scan output stability
    results_url = f"{BASE_URL}/api/v1/scans/{scan_id}/events"
    results_resp = api_session.get(results_url)
    assert results_resp.status_code == 200, f"Failed to fetch scan results: {results_resp.text}"
    
    results = results_resp.json()
    assert isinstance(results, dict)
    
    events = results.get("events", [])
    
    # Assert that actual events were recorded (sfp_dnsresolve against spiderfoot.net should yield events)
    assert len(events) > 0, "Scan finished but produced zero events"
    
    # Check for expected event types
    event_types = [event.get("type") for event in events]
    assert "INTERNET_NAME" in event_types or "IP_ADDRESS" in event_types, \
        f"Expected DNS-related events not found. Got: {set(event_types)}"
        
    # Verify the structure of the first result to ensure API contract stability
    first_event = events[0]
    expected_keys = ["hash", "type", "data", "module", "generated"]
    for key in expected_keys:
        assert key in first_event, f"Missing expected key '{key}' in result output"
