"""Golden path end-to-end test — Steps 31-35 & 46-50.

Exercises the full scan lifecycle through the API layer:
  1. POST /scans (with stealth_level)  → scan created (201)
  2. GET  /scans/{id}                 → scan details returned
  3. GET  /scans/{id}/events          → events returned
  4. GET  /scans/{id}/correlations     → correlations returned
  5. POST /scans/{id}/correlations/run → correlations executed

Uses FastAPI TestClient with dependency-overridden services so the test
runs without Docker, PostgreSQL, Redis, or Celery.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.scan import router
from spiderfoot.api.dependencies import get_scan_service, optional_auth, get_api_key


# -----------------------------------------------------------------------
# Fake services
# -----------------------------------------------------------------------

@dataclass
class FakeScanRecord:
    scan_id: str = ""
    name: str = ""
    target: str = ""
    status: str = "CREATED"
    created: float = 0.0
    started: float = 0.0
    ended: float = 0.0
    result_count: int = 0

    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "name": self.name,
            "target": self.target,
            "status": self.status,
            "created": self.created,
            "started": self.started,
            "ended": self.ended,
            "result_count": self.result_count,
        }


class FakeScanService:
    """Minimal ScanService stand-in with an in-memory store."""

    def __init__(self):
        self._scans: dict[str, FakeScanRecord] = {}
        self._events: dict[str, list[tuple]] = {}
        self._correlations: dict[str, list[dict]] = {}

    def create_scan(self, scan_id: str, name: str, target: str) -> None:
        self._scans[scan_id] = FakeScanRecord(
            scan_id=scan_id, name=name, target=target,
            status="CREATED", started=time.time(),
        )

    def get_scan(self, scan_id: str):
        rec = self._scans.get(scan_id)
        if rec is None:
            return None
        # Return a dict-like object that the router expects
        return rec

    def list_scans(self, *, status: str | None = None):
        scans = list(self._scans.values())
        if status:
            scans = [s for s in scans if s.status == status]
        return scans

    def delete_scan(self, scan_id: str) -> bool:
        return self._scans.pop(scan_id, None) is not None

    def get_events(self, scan_id: str, event_type: str = "ALL",
                   filter_fp: bool = False) -> list[tuple]:
        return self._events.get(scan_id, [])

    def inject_events(self, scan_id: str, events: list[tuple]) -> None:
        """Test helper — inject fake event rows."""
        self._events[scan_id] = events

    # -- correlation helpers for golden-path steps 46-50 --

    def get_correlations(self, scan_id: str) -> list:
        return self._correlations.get(scan_id, [])

    def get_correlation_summary(self, scan_id: str, by: str = "risk") -> list:
        corrs = self._correlations.get(scan_id, [])
        if not corrs:
            return []
        if by == "risk":
            from collections import Counter
            counts = Counter(
                c.get("rule_risk", "INFO") if isinstance(c, dict) else "INFO"
                for c in corrs
            )
            return [{"risk": k, "total": v} for k, v in counts.items()]
        return corrs

    def inject_correlations(self, scan_id: str, corrs: list[dict]) -> None:
        """Test helper — inject fake correlation rows."""
        self._correlations[scan_id] = corrs


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture
def fake_svc():
    return FakeScanService()


@pytest.fixture
def client(fake_svc):
    """TestClient wired to the scan router with faked dependencies."""
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_scan_service] = lambda: fake_svc
    app.dependency_overrides[optional_auth] = lambda: None
    app.dependency_overrides[get_api_key] = lambda: "testkey"

    return TestClient(app)


# -----------------------------------------------------------------------
# Golden path tests
# -----------------------------------------------------------------------

class TestGoldenPath:
    """Full scan lifecycle: create → read → events."""

    @patch("spiderfoot.api.routers.scan.start_scan_background")
    @patch("spiderfoot.api.routers.scan.get_app_config")
    @patch("spiderfoot.api.routers.scan.SpiderFoot")
    @patch("spiderfoot.api.routers.scan.SpiderFootHelpers")
    def test_create_scan_returns_201(
        self, mock_helpers, mock_sf_cls, mock_config, mock_bg, client
    ):
        """POST /scans creates a scan and returns 201."""
        mock_helpers.genScanInstanceId.return_value = "test-scan-001"
        mock_helpers.targetTypeFromString.return_value = "INTERNET_NAME"
        mock_config.return_value.get_config.return_value = {}
        mock_sf_cls.return_value.modulesProducing.return_value = ["sfp_dnsresolve"]

        resp = client.post("/scans", json={
            "name": "Golden path scan",
            "target": "example.com",
        })

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "test-scan-001"
        assert body["name"] == "Golden path scan"
        assert body["target"] == "example.com"
        assert body["status"] is not None

    @patch("spiderfoot.api.routers.scan.start_scan_background")
    @patch("spiderfoot.api.routers.scan.get_app_config")
    @patch("spiderfoot.api.routers.scan.SpiderFoot")
    @patch("spiderfoot.api.routers.scan.SpiderFootHelpers")
    def test_create_scan_with_stealth_level(
        self, mock_helpers, mock_sf_cls, mock_config, mock_bg, client
    ):
        """POST /scans with stealth_level passes it to start_scan_background."""
        mock_helpers.genScanInstanceId.return_value = "stealth-scan-001"
        mock_helpers.targetTypeFromString.return_value = "INTERNET_NAME"
        mock_config.return_value.get_config.return_value = {}
        mock_sf_cls.return_value.modulesProducing.return_value = ["sfp_dnsresolve"]

        resp = client.post("/scans", json={
            "name": "Stealth scan",
            "target": "example.com",
            "stealth_level": "high",
        })

        assert resp.status_code == 201
        # Verify stealth_level was forwarded to background task
        mock_bg.assert_called_once()
        call_kwargs = mock_bg.call_args
        assert call_kwargs.kwargs.get("stealth_level") == "high"

    def test_get_scan_returns_details(self, client, fake_svc):
        """GET /scans/{id} returns scan details when scan exists."""
        fake_svc.create_scan("s1", "My Scan", "example.com")

        resp = client.get("/scans/s1")

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "My Scan"
        assert body["target"] == "example.com"

    def test_get_scan_not_found(self, client):
        """GET /scans/{id} returns 404 for missing scan."""
        resp = client.get("/scans/nonexistent")
        assert resp.status_code == 404

    def test_get_events_empty(self, client, fake_svc):
        """GET /scans/{id}/events returns empty list when no events."""
        fake_svc.create_scan("s1", "Scan1", "example.com")

        resp = client.get("/scans/s1/events")

        assert resp.status_code == 200
        body = resp.json()
        assert body["events"] == []
        assert body["total"] == 0

    def test_get_events_with_data(self, client, fake_svc):
        """GET /scans/{id}/events returns stored events."""
        fake_svc.create_scan("s1", "Scan1", "example.com")
        fake_svc.inject_events("s1", [
            # (generated, data, module, hash, type, source_hash, confidence, visibility, risk)
            (1234567890, "1.2.3.4", "sfp_dnsresolve", "hash1", "IP_ADDRESS", "ROOT", 100, 100, 0),
            (1234567891, "mx.example.com", "sfp_dnsresolve", "hash2", "INTERNET_NAME", "ROOT", 90, 100, 0),
        ])

        resp = client.get("/scans/s1/events")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        events = body["events"]
        assert events[0]["data"] == "1.2.3.4"
        assert events[0]["type"] == "IP_ADDRESS"
        assert events[0]["module"] == "sfp_dnsresolve"
        assert events[1]["data"] == "mx.example.com"
        assert events[1]["type"] == "INTERNET_NAME"

    @patch("spiderfoot.api.routers.scan.start_scan_background")
    @patch("spiderfoot.api.routers.scan.get_app_config")
    @patch("spiderfoot.api.routers.scan.SpiderFoot")
    @patch("spiderfoot.api.routers.scan.SpiderFootHelpers")
    def test_full_lifecycle(
        self, mock_helpers, mock_sf_cls, mock_config, mock_bg, client, fake_svc
    ):
        """Full golden path: create → get → events → verify."""
        # 1. Create scan
        mock_helpers.genScanInstanceId.return_value = "golden-001"
        mock_helpers.targetTypeFromString.return_value = "INTERNET_NAME"
        mock_config.return_value.get_config.return_value = {}
        mock_sf_cls.return_value.modulesProducing.return_value = ["sfp_dnsresolve"]

        create_resp = client.post("/scans", json={
            "name": "Full lifecycle",
            "target": "example.com",
            "stealth_level": "medium",
        })
        assert create_resp.status_code == 201
        scan_id = create_resp.json()["id"]
        assert scan_id == "golden-001"

        # 2. Retrieve scan
        get_resp = client.get(f"/scans/{scan_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Full lifecycle"

        # 3. Simulate events being stored (as if modules ran)
        fake_svc.inject_events(scan_id, [
            (int(time.time()), "example.com", "sfp_dnsresolve", "h1",
             "INTERNET_NAME", "ROOT", 100, 100, 0),
            (int(time.time()), "93.184.216.34", "sfp_dnsresolve", "h2",
             "IP_ADDRESS", "h1", 100, 100, 0),
            (int(time.time()), "www.example.com", "sfp_dnsresolve", "h3",
             "INTERNET_NAME", "h1", 90, 100, 0),
        ])

        # 4. Retrieve events
        events_resp = client.get(f"/scans/{scan_id}/events")
        assert events_resp.status_code == 200
        body = events_resp.json()
        assert body["total"] == 3
        types = [e["type"] for e in body["events"]]
        assert "INTERNET_NAME" in types
        assert "IP_ADDRESS" in types

        # 5. Verify stealth was forwarded
        mock_bg.assert_called_once()
        assert mock_bg.call_args.kwargs.get("stealth_level") == "medium"


# -----------------------------------------------------------------------
# Correlation golden path tests (Steps 46-50)
# -----------------------------------------------------------------------

class TestCorrelationGoldenPath:
    """Verify correlations flow: events → correlations → API display."""

    def test_get_correlations_empty(self, client, fake_svc):
        """GET /scans/{id}/correlations returns empty when no correlations."""
        fake_svc.create_scan("c1", "CorrScan", "example.com")

        resp = client.get("/scans/c1/correlations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["correlations"] == []
        assert body["total"] == 0

    def test_get_correlations_with_data(self, client, fake_svc):
        """GET /scans/{id}/correlations returns stored correlation results."""
        fake_svc.create_scan("c2", "CorrScan2", "example.com")
        fake_svc.inject_correlations("c2", [
            {
                "id": "corr-001",
                "title": "Expired TLS Certificate",
                "rule_id": "cert_expired",
                "rule_risk": "HIGH",
                "rule_name": "cert_expired",
                "rule_descr": "Target uses an expired TLS certificate",
                "rule_logic": "TLS_CERTIFICATE_EXPIRED AND INTERNET_NAME",
                "event_count": 3,
            },
            {
                "id": "corr-002",
                "title": "Open Cloud Bucket",
                "rule_id": "cloud_bucket_open",
                "rule_risk": "MEDIUM",
                "rule_name": "cloud_bucket_open",
                "rule_descr": "Publicly accessible cloud storage bucket",
                "rule_logic": "CLOUD_STORAGE_BUCKET AND PUBLIC_ACCESS",
                "event_count": 1,
            },
        ])

        resp = client.get("/scans/c2/correlations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        titles = [c["title"] for c in body["correlations"]]
        assert "Expired TLS Certificate" in titles
        assert "Open Cloud Bucket" in titles
        # Verify risk levels preserved
        risks = {c["rule_id"]: c["rule_risk"] for c in body["correlations"]}
        assert risks["cert_expired"] == "HIGH"
        assert risks["cloud_bucket_open"] == "MEDIUM"

    def test_get_correlations_not_found(self, client):
        """GET /scans/{id}/correlations returns 404 for missing scan."""
        resp = client.get("/scans/nonexistent/correlations")
        assert resp.status_code == 404

    def test_correlation_summary_by_risk(self, client, fake_svc):
        """GET /scans/{id}/correlations/summary groups by risk."""
        fake_svc.create_scan("c3", "CorrScan3", "example.com")
        fake_svc.inject_correlations("c3", [
            {"id": "1", "rule_risk": "HIGH", "title": "A"},
            {"id": "2", "rule_risk": "HIGH", "title": "B"},
            {"id": "3", "rule_risk": "LOW", "title": "C"},
        ])

        resp = client.get("/scans/c3/correlations/summary?by=risk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2  # at least HIGH and LOW buckets
        risk_map = {s["risk"]: s["total"] for s in body["summary"]}
        assert risk_map.get("HIGH") == 2
        assert risk_map.get("LOW") == 1

    @patch("spiderfoot.api.routers.scan.start_scan_background")
    @patch("spiderfoot.api.routers.scan.get_app_config")
    @patch("spiderfoot.api.routers.scan.SpiderFoot")
    @patch("spiderfoot.api.routers.scan.SpiderFootHelpers")
    def test_full_lifecycle_with_correlations(
        self, mock_helpers, mock_sf_cls, mock_config, mock_bg, client, fake_svc
    ):
        """Full golden path: create → scan → events → correlations → verify.

        This is the definitive end-to-end test verifying that scan results
        flow through the complete pipeline: target → scan → events →
        correlations → API display.
        """
        # 1. Create scan
        mock_helpers.genScanInstanceId.return_value = "golden-full-001"
        mock_helpers.targetTypeFromString.return_value = "INTERNET_NAME"
        mock_config.return_value.get_config.return_value = {}
        mock_sf_cls.return_value.modulesProducing.return_value = ["sfp_dnsresolve"]

        create_resp = client.post("/scans", json={
            "name": "Full lifecycle with correlations",
            "target": "example.com",
            "stealth_level": "medium",
        })
        assert create_resp.status_code == 201
        scan_id = create_resp.json()["id"]

        # 2. Simulate modules producing events
        now = int(time.time())
        fake_svc.inject_events(scan_id, [
            (now, "example.com", "sfp_dnsresolve", "h1", "INTERNET_NAME", "ROOT", 100, 100, 0),
            (now, "93.184.216.34", "sfp_dnsresolve", "h2", "IP_ADDRESS", "h1", 100, 100, 0),
            (now, "EXPIRED", "sfp_sslcert", "h3", "TLS_CERTIFICATE_EXPIRED", "h1", 100, 100, 0),
            (now, "s3://example-bucket", "sfp_cloud", "h4", "CLOUD_STORAGE_BUCKET", "h1", 80, 100, 0),
        ])

        # 3. Verify events stored
        events_resp = client.get(f"/scans/{scan_id}/events")
        assert events_resp.status_code == 200
        assert events_resp.json()["total"] == 4

        # 4. Simulate correlation engine producing results
        fake_svc.inject_correlations(scan_id, [
            {
                "id": "fc-001",
                "title": "Expired TLS Certificate",
                "rule_id": "cert_expired",
                "rule_risk": "HIGH",
                "rule_name": "cert_expired",
                "rule_descr": "Target uses an expired TLS certificate",
                "rule_logic": "TLS_CERTIFICATE_EXPIRED AND INTERNET_NAME",
                "event_count": 2,
            },
        ])

        # 5. Verify correlations accessible via API
        corr_resp = client.get(f"/scans/{scan_id}/correlations")
        assert corr_resp.status_code == 200
        corr_body = corr_resp.json()
        assert corr_body["total"] == 1
        assert corr_body["correlations"][0]["title"] == "Expired TLS Certificate"
        assert corr_body["correlations"][0]["rule_risk"] == "HIGH"

        # 6. Verify summary works
        summary_resp = client.get(f"/scans/{scan_id}/correlations/summary?by=risk")
        assert summary_resp.status_code == 200
        assert summary_resp.json()["total"] >= 1

        # 7. Verify stealth was forwarded
        mock_bg.assert_called_once()
        assert mock_bg.call_args.kwargs.get("stealth_level") == "medium"


# -----------------------------------------------------------------------
# IaC generation golden path tests (Phase 2 — Steps 77-80)
# -----------------------------------------------------------------------

class TestIaCGoldenPath:
    """Verify IaC generation endpoint: events → profile → Terraform/Ansible/Docker."""

    def _seed_scan_with_events(self, fake_svc, scan_id="iac-scan-001"):
        """Create a scan and seed realistic OSINT events."""
        fake_svc.create_scan(scan_id, "IaC Test Scan", "example.com")
        now = int(time.time())
        fake_svc.inject_events(scan_id, [
            (now, "example.com", "sfp_dnsresolve", "h1", "INTERNET_NAME", "ROOT", 100, 100, 0),
            (now, "93.184.216.34", "sfp_dnsresolve", "h2", "IP_ADDRESS", "h1", 100, 100, 0),
            (now, "93.184.216.34:80", "sfp_portscan_tcp", "h3", "TCP_PORT_OPEN", "h2", 100, 100, 0),
            (now, "93.184.216.34:443", "sfp_portscan_tcp", "h4", "TCP_PORT_OPEN", "h2", 100, 100, 0),
            (now, "93.184.216.34:22", "sfp_portscan_tcp", "h5", "TCP_PORT_OPEN", "h2", 100, 100, 0),
            (now, "nginx/1.24.0", "sfp_webserver", "h6", "WEBSERVER_BANNER", "h3", 100, 100, 0),
            (now, "Ubuntu 22.04", "sfp_portscan_tcp", "h7", "OPERATING_SYSTEM", "h2", 80, 100, 0),
            (now, "WordPress 6.4", "sfp_wappalyzer", "h8", "WEBSERVER_TECHNOLOGY", "h3", 90, 100, 0),
        ])
        return scan_id

    def test_iac_404_for_missing_scan(self, client):
        """POST /scans/{id}/iac returns 404 when scan doesn't exist."""
        resp = client.post("/scans/nonexistent/iac", json={})
        assert resp.status_code == 404

    def test_iac_empty_events(self, client, fake_svc):
        """POST /scans/{id}/iac returns empty bundle when scan has no events."""
        fake_svc.create_scan("empty-iac", "Empty Scan", "example.com")

        resp = client.post("/scans/empty-iac/iac", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["scan_id"] == "empty-iac"
        assert body["bundle"] == {}
        assert "No events found" in body["message"]

    def test_iac_generates_terraform(self, client, fake_svc):
        """POST /scans/{id}/iac generates Terraform configs from events."""
        scan_id = self._seed_scan_with_events(fake_svc)

        resp = client.post(f"/scans/{scan_id}/iac", json={
            "provider": "aws",
            "include_terraform": True,
            "include_ansible": False,
            "include_docker": False,
            "validate": False,
        })
        assert resp.status_code == 200
        body = resp.json()

        assert body["provider"] == "aws"
        assert "terraform" in body["bundle"]
        assert "ansible" not in body["bundle"]
        assert "docker" not in body["bundle"]

        # Terraform bundle should contain main.tf at minimum
        tf_files = body["files"].get("terraform", [])
        assert len(tf_files) > 0
        assert any("main" in f for f in tf_files)

    def test_iac_generates_ansible(self, client, fake_svc):
        """POST /scans/{id}/iac generates Ansible playbook from events."""
        scan_id = self._seed_scan_with_events(fake_svc)

        resp = client.post(f"/scans/{scan_id}/iac", json={
            "include_terraform": False,
            "include_ansible": True,
            "include_docker": False,
            "validate": False,
        })
        assert resp.status_code == 200
        body = resp.json()

        assert "ansible" in body["bundle"]
        ansible_files = body["files"].get("ansible", [])
        assert len(ansible_files) > 0

    def test_iac_generates_docker_compose(self, client, fake_svc):
        """POST /scans/{id}/iac generates Docker Compose from events."""
        scan_id = self._seed_scan_with_events(fake_svc)

        resp = client.post(f"/scans/{scan_id}/iac", json={
            "include_terraform": False,
            "include_ansible": False,
            "include_docker": True,
            "validate": False,
        })
        assert resp.status_code == 200
        body = resp.json()

        assert "docker" in body["bundle"]
        docker_files = body["files"].get("docker", [])
        assert "docker-compose.yml" in docker_files

    def test_iac_validates_output(self, client, fake_svc):
        """POST /scans/{id}/iac with validate=True returns schema results."""
        scan_id = self._seed_scan_with_events(fake_svc)

        resp = client.post(f"/scans/{scan_id}/iac", json={
            "validate": True,
        })
        assert resp.status_code == 200
        body = resp.json()

        assert "validation" in body
        assert isinstance(body["validation"], list)
        assert "all_valid" in body
        # Each validation result should have required fields
        for v in body["validation"]:
            assert "artifact_type" in v
            assert "valid" in v

    def test_iac_profile_summary(self, client, fake_svc):
        """POST /scans/{id}/iac returns profile summary from discovered infra."""
        scan_id = self._seed_scan_with_events(fake_svc)

        resp = client.post(f"/scans/{scan_id}/iac", json={"validate": False})
        assert resp.status_code == 200
        body = resp.json()

        summary = body["profile_summary"]
        assert summary["ip_count"] >= 1  # At least 93.184.216.34
        assert summary["port_count"] >= 3  # 80, 443, 22
        assert summary["web_server"] == "nginx"
        assert "Ubuntu" in summary["os_detected"]

    def test_iac_invalid_provider(self, client, fake_svc):
        """POST /scans/{id}/iac rejects unknown cloud provider."""
        fake_svc.create_scan("bad-prov", "Bad Provider", "example.com")
        fake_svc.inject_events("bad-prov", [
            (int(time.time()), "1.2.3.4", "sfp_dns", "h1", "IP_ADDRESS", "ROOT", 100, 100, 0),
        ])

        resp = client.post("/scans/bad-prov/iac", json={"provider": "oracle"})
        assert resp.status_code == 400
        assert "Unknown provider" in resp.json()["detail"]

    def test_iac_full_lifecycle(self, client, fake_svc):
        """Full IaC golden path: seed events → generate → validate → verify."""
        scan_id = self._seed_scan_with_events(fake_svc, "iac-full-001")

        # Generate full IaC bundle with validation
        resp = client.post(f"/scans/{scan_id}/iac", json={
            "provider": "aws",
            "include_terraform": True,
            "include_ansible": True,
            "include_docker": True,
            "include_packer": True,
            "validate": True,
        })
        assert resp.status_code == 200
        body = resp.json()

        # 1. Provider correct
        assert body["provider"] == "aws"
        assert body["scan_id"] == scan_id

        # 2. All requested categories present
        bundle = body["bundle"]
        assert "terraform" in bundle
        assert "ansible" in bundle
        assert "docker" in bundle

        # 3. Validation ran
        assert isinstance(body["validation"], list)
        assert "all_valid" in body

        # 4. Profile summary populated from events
        summary = body["profile_summary"]
        assert summary["ip_count"] >= 1
        assert summary["port_count"] >= 1

        # 5. File listing is structured
        files = body["files"]
        assert isinstance(files, dict)
        for category in ["terraform", "ansible", "docker"]:
            if category in files:
                assert isinstance(files[category], list)
                assert len(files[category]) > 0
