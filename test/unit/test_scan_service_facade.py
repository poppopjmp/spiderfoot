"""
Tests for Cycle 27 — Scan Service Facade + Router Wiring.

Covers:
  - ScanService lifecycle (CRUD, state machine integration)
  - ScanStateMachine transition enforcement
  - Scan router endpoints via Starlette TestClient
  - Pagination on list_scans
"""

import time
import threading
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass

import pytest

from spiderfoot.scan_state import (
    ScanState,
    ScanStateMachine,
    InvalidTransitionError,
    VALID_TRANSITIONS,
    StateTransition,
)
from spiderfoot.scan_service_facade import (
    ScanService,
    ScanServiceError,
)
from spiderfoot.db.repositories.scan_repository import ScanRecord


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

class FakeRepo:
    """Minimal ScanRepository stand-in."""

    __bool__ = True  # avoid MagicMock dunder issues

    def __init__(self):
        self._scans = {}
        self._dbh = FakeDbh()

    def list_scans(self):
        return list(self._scans.values())

    def get_scan(self, scan_id):
        return self._scans.get(scan_id)

    def create_scan(self, scan_id, name, target):
        self._scans[scan_id] = ScanRecord(
            scan_id=scan_id, name=name, target=target, status="CREATED",
        )

    def delete_scan(self, scan_id):
        return self._scans.pop(scan_id, None) is not None

    def update_status(self, scan_id, status, *, started=None, ended=None):
        if scan_id in self._scans:
            self._scans[scan_id].status = status

    def get_config(self, scan_id):
        return {"_modulesenabled": "sfp__stor_db"}

    def set_config(self, scan_id, config_data):
        pass

    def get_scan_log(self, scan_id, **kw):
        return [("2025-01-01", "module", "INFO", "msg")]

    def get_scan_errors(self, scan_id, limit=0):
        return []

    def close(self):
        pass


class FakeDbh:
    """Fake DB handle for un-migrated methods."""

    __bool__ = True

    def scanResultDelete(self, scan_id):
        pass

    def scanConfigDelete(self, scan_id):
        pass

    def scanInstanceDelete(self, scan_id):
        pass


def _make_svc(scans=None):
    repo = FakeRepo()
    if scans:
        for s in scans:
            repo._scans[s.scan_id] = s
    return ScanService(repo, dbh=repo._dbh)


def _sample_records():
    return [
        ScanRecord(scan_id="s1", name="Scan 1", target="example.com",
                   status="RUNNING", created=1000, started=1001),
        ScanRecord(scan_id="s2", name="Scan 2", target="test.org",
                   status="COMPLETED", created=2000, started=2001, ended=2100),
        ScanRecord(scan_id="s3", name="Scan 3", target="foo.net",
                   status="CREATED", created=3000),
    ]


# ===================================================================
# 1. ScanStateMachine
# ===================================================================

class TestScanStateMachine:
    def test_initial_state(self):
        sm = ScanStateMachine("s1")
        assert sm.state == ScanState.CREATED

    def test_valid_transition(self):
        sm = ScanStateMachine("s1")
        sm.transition(ScanState.QUEUED)
        assert sm.state == ScanState.QUEUED

    def test_invalid_transition_raises(self):
        sm = ScanStateMachine("s1")
        with pytest.raises(InvalidTransitionError):
            sm.transition(ScanState.COMPLETED)

    def test_terminal_state_blocks_transitions(self):
        sm = ScanStateMachine("s1", initial_state=ScanState.COMPLETED)
        assert sm.is_terminal
        with pytest.raises(InvalidTransitionError):
            sm.transition(ScanState.RUNNING)

    def test_history_recorded(self):
        sm = ScanStateMachine("s1")
        sm.transition(ScanState.QUEUED, reason="test")
        sm.transition(ScanState.STARTING)
        assert len(sm.history) == 2
        assert sm.history[0].from_state == ScanState.CREATED
        assert sm.history[0].reason == "test"

    def test_callback_fired(self):
        sm = ScanStateMachine("s1")
        log = []
        sm.on_transition(lambda old, new, sid: log.append((old, new, sid)))
        sm.transition(ScanState.QUEUED)
        assert len(log) == 1
        assert log[0] == (ScanState.CREATED, ScanState.QUEUED, "s1")

    def test_can_transition(self):
        sm = ScanStateMachine("s1", initial_state=ScanState.RUNNING)
        assert sm.can_transition(ScanState.COMPLETED) is True
        assert sm.can_transition(ScanState.CREATED) is False

    def test_to_dict(self):
        sm = ScanStateMachine("s1")
        d = sm.to_dict()
        assert d["scan_id"] == "s1"
        assert d["state"] == "CREATED"
        assert d["is_terminal"] is False

    def test_is_active(self):
        sm = ScanStateMachine("s1", initial_state=ScanState.RUNNING)
        assert sm.is_active is True


# ===================================================================
# 2. ScanService
# ===================================================================

class TestScanService:
    def test_list_scans(self):
        svc = _make_svc(_sample_records())
        assert len(svc.list_scans()) == 3

    def test_get_scan(self):
        svc = _make_svc(_sample_records())
        r = svc.get_scan("s1")
        assert r is not None
        assert r.name == "Scan 1"

    def test_get_scan_not_found(self):
        svc = _make_svc([])
        assert svc.get_scan("nope") is None

    def test_create_scan(self):
        svc = _make_svc([])
        svc.create_scan("new1", "New Scan", "example.com")
        assert svc.get_scan("new1") is not None
        # State machine should be bootstrapped
        state = svc.get_scan_state("new1")
        assert state["state"] == "CREATED"

    def test_delete_scan(self):
        svc = _make_svc(_sample_records())
        assert svc.delete_scan("s1") is True
        assert svc.get_scan("s1") is None

    def test_delete_scan_not_found(self):
        svc = _make_svc([])
        assert svc.delete_scan("nope") is False

    def test_delete_scan_full(self):
        svc = _make_svc(_sample_records())
        svc.delete_scan_full("s1")
        # The FakeDbh's methods are called; no exception = success

    def test_stop_scan_running(self):
        svc = _make_svc(_sample_records())
        # s1 is RUNNING — should transition to STOPPING then persist ABORTED
        status = svc.stop_scan("s1")
        assert status == "ABORTED"

    def test_stop_scan_created(self):
        svc = _make_svc(_sample_records())
        # s3 is CREATED — should transition to CANCELLED
        status = svc.stop_scan("s3")
        assert status == "ABORTED"

    def test_stop_scan_completed_raises(self):
        svc = _make_svc(_sample_records())
        # s2 is COMPLETED (terminal) — cannot stop
        with pytest.raises(ScanServiceError, match="Cannot stop"):
            svc.stop_scan("s2")

    def test_stop_scan_not_found(self):
        svc = _make_svc([])
        with pytest.raises(ScanServiceError, match="Scan not found"):
            svc.stop_scan("nope")

    def test_get_config(self):
        svc = _make_svc(_sample_records())
        cfg = svc.get_config("s1")
        assert "_modulesenabled" in cfg

    def test_get_scan_log(self):
        svc = _make_svc(_sample_records())
        logs = svc.get_scan_log("s1")
        assert len(logs) == 1

    def test_close(self):
        svc = _make_svc([])
        svc.close()  # should not raise


# ===================================================================
# 3. Router tests (via TestClient)
# ===================================================================

class TestScanRouter:
    @staticmethod
    def _make_client(svc=None):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from spiderfoot.api.routers.scan import router

        app = FastAPI()
        app.include_router(router)

        if svc is None:
            svc = _make_svc(_sample_records())

        from spiderfoot.api.dependencies import get_scan_service, optional_auth, get_api_key
        app.dependency_overrides[get_scan_service] = lambda: svc
        app.dependency_overrides[optional_auth] = lambda: None
        app.dependency_overrides[get_api_key] = lambda: "testkey"

        return TestClient(app), svc

    # --- list ---
    def test_list_scans(self):
        client, _ = self._make_client()
        resp = client.get("/scans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_scans_pagination(self):
        client, _ = self._make_client()
        resp = client.get("/scans?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["has_next"] is True

    # --- get ---
    def test_get_scan(self):
        client, _ = self._make_client()
        resp = client.get("/scans/s1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Scan 1"

    def test_get_scan_not_found(self):
        client, _ = self._make_client()
        resp = client.get("/scans/nonexistent")
        assert resp.status_code == 404

    def test_get_scan_includes_state_machine(self):
        svc = _make_svc(_sample_records())
        client, _ = self._make_client(svc)
        resp = client.get("/scans/s1")
        assert resp.status_code == 200
        data = resp.json()
        assert "state_machine" in data

    # --- delete ---
    def test_delete_scan(self):
        client, svc = self._make_client()
        resp = client.delete("/scans/s1")
        assert resp.status_code == 200
        assert svc.get_scan("s1") is None

    def test_delete_scan_not_found(self):
        client, _ = self._make_client()
        resp = client.delete("/scans/nonexistent")
        assert resp.status_code == 404

    # --- stop ---
    def test_stop_scan_running(self):
        client, _ = self._make_client()
        resp = client.post("/scans/s1/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ABORTED"

    def test_stop_scan_completed_conflict(self):
        client, _ = self._make_client()
        resp = client.post("/scans/s2/stop")
        assert resp.status_code == 409

    def test_stop_scan_not_found(self):
        client, _ = self._make_client()
        resp = client.post("/scans/nonexistent/stop")
        assert resp.status_code == 404
