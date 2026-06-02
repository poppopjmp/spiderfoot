"""Tests for spiderfoot.api.routers.scan_progress.

Progress trackers live in an in-memory registry (`_trackers`). These tests
register a real ScanProgressTracker and exercise the snapshot, per-module,
history, and active-scans endpoints plus the no-tracker 404 path — no DB.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.scan_progress as sp
from spiderfoot.scan.scan_progress import ScanProgressTracker


@pytest.fixture
def client():
    sp.clear_trackers()
    tracker = ScanProgressTracker("scan-1")
    tracker.register_modules(["sfp_dns", "sfp_whois"])
    sp.register_tracker("scan-1", tracker)
    app = FastAPI()
    app.include_router(sp.router)
    yield TestClient(app), tracker
    sp.clear_trackers()


class TestProgress:
    def test_snapshot(self, client):
        c, _ = client
        resp = c.get("/scans/scan-1/progress")
        assert resp.status_code == 200
        assert resp.json()["scan_id"] == "scan-1"

    def test_snapshot_unknown_404(self, client):
        c, _ = client
        assert c.get("/scans/nope/progress").status_code == 404

    def test_module_breakdown(self, client):
        c, tracker = client
        resp = c.get("/scans/scan-1/progress/modules")
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["total"] == 2

    def test_module_breakdown_unknown_404(self, client):
        c, _ = client
        assert c.get("/scans/nope/progress/modules").status_code == 404

    def test_reflects_module_state_change(self, client):
        c, tracker = client
        tracker.module_started("sfp_dns")
        running = c.get("/scans/scan-1/progress").json().get("running_modules", [])
        assert "sfp_dns" in running


class TestHistoryAndActive:
    def test_history(self, client):
        c, _ = client
        assert c.get("/scans/scan-1/progress/history").status_code == 200

    def test_active_lists_registered(self, client):
        c, _ = client
        resp = c.get("/scans/progress/active")
        assert resp.status_code == 200
        assert "scan-1" in resp.text
