"""
Tests for Cycle 30 — Final Router DB Purge + Dead Code Removal.

Covers:
  - ConfigRepository.get_event_types()
  - config.py /event-types endpoint via TestClient with dependency override
  - reports.py _get_scan_events() with injected ScanService
  - websocket.py _polling_mode() with ScanService (unit-level)
  - Verification that event_schema.py is deleted (dead code removal)
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import pytest
from starlette.testclient import TestClient

from spiderfoot.db.repositories.config_repository import ConfigRepository


# -----------------------------------------------------------------------
# Fake doubles
# -----------------------------------------------------------------------

class FakeDbh:
    """Minimal SpiderFootDb stand-in for ConfigRepository tests."""
    __bool__ = True

    def __init__(self):
        self._event_types = []

    def eventTypes(self):
        return self._event_types

    def configGet(self):
        return {}

    def configSet(self, data):
        pass

    def configClear(self):
        pass

    # Scan-related stubs for ScanService
    def scanInstanceGet(self, scan_id):
        return self._scans.get(scan_id) if hasattr(self, '_scans') else None

    def scanResultEvent(self, scan_id, event_type=None, filterFp=False):
        rows = self._events.get(scan_id, []) if hasattr(self, '_events') else []
        if event_type and event_type != "ALL":
            return [r for r in rows if len(r) > 4 and r[4] == event_type]
        return rows

    def scanResultSummary(self, scan_id, group_by="type"):
        return []

    def scanResultDelete(self, scan_id):
        pass

    def scanConfigDelete(self, scan_id):
        pass

    def scanInstanceDelete(self, scan_id):
        pass


class FakeScanDbh(FakeDbh):
    """Extended fake for ScanService tests with event/scan data."""

    def __init__(self):
        super().__init__()
        self._scans = {}
        self._events = {}


@dataclass
class FakeScanRecord:
    scan_id: str = "scan-1"
    name: str = "Test Scan"
    target: str = "example.com"
    status: str = "FINISHED"
    started: str = "2024-01-01 00:00:00"
    ended: str = "2024-01-01 01:00:00"

    def to_dict(self):
        return {
            "scan_id": self.scan_id,
            "name": self.name,
            "target": self.target,
            "status": self.status,
        }


class FakeRepo:
    """Minimal ScanRepository stand-in."""
    __bool__ = True

    def __init__(self, dbh=None):
        self._scans = {}
        self._dbh = dbh if dbh is not None else FakeScanDbh()

    def get_scan(self, scan_id):
        return self._scans.get(scan_id)

    def list_scans(self, **kw):
        return list(self._scans.values())

    def create_scan(self, scan_id, name, target):
        self._scans[scan_id] = FakeScanRecord(scan_id=scan_id, name=name, target=target)

    def delete_scan(self, scan_id):
        return self._scans.pop(scan_id, None) is not None

    def update_status(self, scan_id, status):
        rec = self._scans.get(scan_id)
        if rec:
            rec.status = status

    def get_config(self, scan_id):
        return None

    def set_config(self, scan_id, data):
        pass

    def get_scan_log(self, scan_id, **kw):
        return []

    def get_scan_errors(self, scan_id, **kw):
        return []

    def close(self):
        pass


# =====================================================================
# 1. ConfigRepository.get_event_types()
# =====================================================================

class TestConfigRepositoryEventTypes:
    """Unit tests for ConfigRepository.get_event_types()."""

    def test_get_event_types_returns_list(self):
        dbh = FakeDbh()
        dbh._event_types = [
            ("IP Address", "IP_ADDRESS", 0, "ENTITY"),
            ("Domain Name", "DOMAIN_NAME", 0, "ENTITY"),
        ]
        repo = ConfigRepository(dbh)
        result = repo.get_event_types()
        assert len(result) == 2
        assert result[0][0] == "IP Address"
        assert result[1][1] == "DOMAIN_NAME"

    def test_get_event_types_empty(self):
        dbh = FakeDbh()
        dbh._event_types = []
        repo = ConfigRepository(dbh)
        result = repo.get_event_types()
        assert result == []


# =====================================================================
# 2. Config router /event-types endpoint
# =====================================================================

class TestConfigEventTypesEndpoint:
    """Integration tests for GET /event-types via TestClient."""

    def _build_client(self, fake_dbh):
        from fastapi import FastAPI
        from spiderfoot.api.routers import config as config_router

        app = FastAPI()
        app.include_router(config_router.router, prefix="/api/config")

        # Override config_repository dependency
        from spiderfoot.api.dependencies import get_config_repository, optional_auth

        repo = ConfigRepository(fake_dbh)

        app.dependency_overrides[get_config_repository] = lambda: repo
        app.dependency_overrides[optional_auth] = lambda: None

        return TestClient(app)

    def test_event_types_success(self):
        dbh = FakeDbh()
        dbh._event_types = [
            ("IP Address", "IP_ADDRESS", 0, "ENTITY"),
            ("Domain Name", "DOMAIN_NAME", 0, "ENTITY"),
            ("Email Address", "EMAILADDR", 0, "ENTITY"),
        ]
        client = self._build_client(dbh)
        resp = client.get("/api/config/event-types")
        assert resp.status_code == 200
        data = resp.json()
        assert "event_types" in data
        assert len(data["event_types"]) == 3

    def test_event_types_empty(self):
        dbh = FakeDbh()
        dbh._event_types = []
        client = self._build_client(dbh)
        resp = client.get("/api/config/event-types")
        assert resp.status_code == 200
        assert resp.json()["event_types"] == []

    def test_event_types_error(self):
        dbh = FakeDbh()
        dbh.eventTypes = lambda: (_ for _ in ()).throw(IOError("DB down"))
        client = self._build_client(dbh)
        resp = client.get("/api/config/event-types")
        assert resp.status_code == 500


# =====================================================================
# 3. Reports _get_scan_events() with injected ScanService
# =====================================================================

class TestReportsGetScanEvents:
    """Unit tests for _get_scan_events() using ScanService."""

    def _make_service(self, scan_record=None, events=None):
        from spiderfoot.scan_service_facade import ScanService

        dbh = FakeScanDbh()
        repo = FakeRepo(dbh=dbh)

        if scan_record:
            repo._scans[scan_record.scan_id] = scan_record

        if events:
            for scan_id, rows in events.items():
                dbh._events[scan_id] = rows

        return ScanService(repo, dbh=dbh)

    def test_returns_events_and_metadata(self):
        from spiderfoot.api.routers.reports import _get_scan_events

        rec = FakeScanRecord(scan_id="s1", target="example.com")
        svc = self._make_service(
            scan_record=rec,
            events={"s1": [
                (1704067200, "1.2.3.4", "", "sfp_dns", "IP_ADDRESS"),
                (1704067201, "foo.com", "", "sfp_dns", "DOMAIN_NAME"),
            ]},
        )

        events, meta = _get_scan_events("s1", scan_service=svc)
        assert len(events) == 2
        assert meta["target"] == "example.com"
        assert events[0]["type"] == "IP_ADDRESS"
        assert events[1]["data"] == "foo.com"

    def test_scan_not_found_returns_empty(self):
        from spiderfoot.api.routers.reports import _get_scan_events

        svc = self._make_service()
        events, meta = _get_scan_events("nonexistent", scan_service=svc)
        assert events == []
        assert meta["target"] == "Unknown"

    def test_no_events_returns_empty_list(self):
        from spiderfoot.api.routers.reports import _get_scan_events

        rec = FakeScanRecord(scan_id="s1")
        svc = self._make_service(scan_record=rec)
        events, meta = _get_scan_events("s1", scan_service=svc)
        assert events == []

    def test_metadata_includes_started_ended(self):
        from spiderfoot.api.routers.reports import _get_scan_events

        rec = FakeScanRecord(
            scan_id="s1",
            started="2024-01-01 00:00:00",
            ended="2024-01-01 01:00:00",
        )
        svc = self._make_service(scan_record=rec)
        _, meta = _get_scan_events("s1", scan_service=svc)
        assert meta["started"] == "2024-01-01 00:00:00"
        assert meta["ended"] == "2024-01-01 01:00:00"


# =====================================================================
# 4. WebSocket _polling_mode() with ScanService
# =====================================================================

class TestWebSocketPollingMode:
    """Verify _polling_mode uses ScanService (no raw SpiderFootDb)."""

    def test_no_spiderfoot_db_import_in_websocket(self):
        """Verify that websocket.py no longer imports SpiderFootDb."""
        import spiderfoot.api.routers.websocket as ws_module
        import inspect
        source = inspect.getsource(ws_module)
        # Should NOT contain a direct import of SpiderFootDb at module level
        lines = source.split("\n")
        module_level_imports = [
            line for line in lines
            if "SpiderFootDb" in line
            and not line.strip().startswith("#")
            and not line.strip().startswith('"""')
            and not line.strip().startswith("'")
        ]
        assert len(module_level_imports) == 0, (
            f"Found SpiderFootDb references in websocket.py: {module_level_imports}"
        )

    def test_polling_mode_uses_scan_service(self):
        """Verify _polling_mode references ScanService, not SpiderFootDb."""
        import inspect
        from spiderfoot.api.routers.websocket import _polling_mode
        source = inspect.getsource(_polling_mode)
        assert "ScanService" in source
        assert "SpiderFootDb" not in source


# =====================================================================
# 5. Dead code verification — event_schema.py deleted
# =====================================================================

class TestDeadCodeRemoval:
    """Verify dead code has been deleted."""

    def test_event_schema_deleted(self):
        """event_schema.py should no longer exist."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "spiderfoot", "event_schema.py",
        )
        assert not os.path.exists(path), f"Dead code still present: {path}"

    def test_event_schema_test_deleted(self):
        """test_event_schema.py should no longer exist."""
        path = os.path.join(
            os.path.dirname(__file__),
            "test_event_schema.py",
        )
        assert not os.path.exists(path), f"Dead test still present: {path}"


# =====================================================================
# 6. Router-level SpiderFootDb purge verification
# =====================================================================

class TestRouterDbPurge:
    """Verify no router imports SpiderFootDb at module level."""

    def _get_router_files(self):
        import glob
        routers_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "spiderfoot", "api", "routers",
        )
        return glob.glob(os.path.join(routers_dir, "*.py"))

    def test_no_spiderfoot_db_import_in_any_router(self):
        """No router should have 'from spiderfoot import SpiderFootDb'
        or 'from spiderfoot import SpiderFootDb' as an actual import."""
        for filepath in self._get_router_files():
            with open(filepath, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    stripped = line.strip()
                    # Skip comments, docstrings
                    if stripped.startswith("#") or stripped.startswith('"""'):
                        continue
                    if stripped.startswith("'") or stripped.startswith('"'):
                        continue
                    if "import SpiderFootDb" in stripped:
                        pytest.fail(
                            f"SpiderFootDb import found in "
                            f"{os.path.basename(filepath)}:{lineno}: {stripped}"
                        )

    def test_no_spiderfoot_db_instantiation_in_any_router(self):
        """No router should instantiate SpiderFootDb(...)."""
        for filepath in self._get_router_files():
            with open(filepath, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    stripped = line.strip()
                    if stripped.startswith("#") or stripped.startswith('"""'):
                        continue
                    if stripped.startswith("'") or stripped.startswith('"'):
                        continue
                    if "SpiderFootDb(" in stripped:
                        pytest.fail(
                            f"SpiderFootDb instantiation found in "
                            f"{os.path.basename(filepath)}:{lineno}: {stripped}"
                        )
