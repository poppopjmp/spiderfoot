"""
Tests for spiderfoot.api.routers.scan_progress — Scan Progress API.

Covers: tracker registry, REST endpoints (progress, modules,
history, active list, create), SSE streaming, and edge cases.
"""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import MagicMock, patch

import pytest

import spiderfoot.api.routers.scan_progress as progress_mod
from spiderfoot.api.routers.scan_progress import (
    _sse_event,
    clear_trackers,
    get_tracker,
    list_tracked_scans,
    register_tracker,
    unregister_tracker,
)
from spiderfoot.scan_progress import (
    ModuleProgress,
    ModuleStatus,
    ProgressSnapshot,
    ScanProgressTracker,
)

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from spiderfoot.api.routers.scan_progress import router

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_trackers():
    """Ensure no leftover trackers between tests."""
    clear_trackers()
    yield
    clear_trackers()


@pytest.fixture
def tracker():
    """A fully initialised tracker with 3 modules."""
    t = ScanProgressTracker(scan_id="scan-001")
    t.register_modules(["sfp_dns", "sfp_ssl", "sfp_ports"])
    t.start()
    return t


@pytest.fixture
def client():
    if not HAS_FASTAPI:
        pytest.skip("FastAPI not installed")
    app = FastAPI()
    app.include_router(router, prefix="/api", tags=["scan-progress"])
    return TestClient(app)


# ===================================================================
# Tracker registry
# ===================================================================

class TestTrackerRegistry:
    def test_register_and_get(self, tracker):
        register_tracker("scan-001", tracker)
        assert get_tracker("scan-001") is tracker

    def test_get_nonexistent(self):
        assert get_tracker("nope") is None

    def test_unregister(self, tracker):
        register_tracker("scan-001", tracker)
        removed = unregister_tracker("scan-001")
        assert removed is tracker
        assert get_tracker("scan-001") is None

    def test_unregister_nonexistent(self):
        assert unregister_tracker("nope") is None

    def test_list_tracked_scans(self, tracker):
        register_tracker("scan-001", tracker)
        t2 = ScanProgressTracker(scan_id="scan-002")
        register_tracker("scan-002", t2)
        ids = list_tracked_scans()
        assert set(ids) == {"scan-001", "scan-002"}

    def test_clear_trackers(self, tracker):
        register_tracker("scan-001", tracker)
        count = clear_trackers()
        assert count == 1
        assert list_tracked_scans() == []

    def test_overwrite_tracker(self, tracker):
        register_tracker("scan-001", tracker)
        t2 = ScanProgressTracker(scan_id="scan-001")
        register_tracker("scan-001", t2)
        assert get_tracker("scan-001") is t2


# ===================================================================
# SSE helpers
# ===================================================================

class TestSSEEvent:
    def test_basic_event(self):
        text = _sse_event("progress", {"pct": 50})
        assert text.startswith("event: progress\n")
        assert "data: " in text
        assert text.endswith("\n\n")
        data = json.loads(text.split("data: ")[1].strip())
        assert data["pct"] == 50

    def test_serialises_non_json_types(self):
        """default=str should handle non-serialisable types."""
        text = _sse_event("test", {"ts": time.time()})
        assert "data: " in text


class TestSSEGenerator:
    def test_complete_when_tracker_removed(self):
        from spiderfoot.api.routers.scan_progress import _sse_generator

        t = ScanProgressTracker(scan_id="gen-test")
        t.register_modules(["m1"])
        t.start()
        register_tracker("gen-test", t)

        async def _run():
            gen = _sse_generator("gen-test", interval=0.1, timeout=5.0)
            first = await gen.__anext__()
            assert "event:" in first
            unregister_tracker("gen-test")
            second = await gen.__anext__()
            assert "complete" in second

        asyncio.run(_run())

    def test_complete_when_100_pct(self):
        from spiderfoot.api.routers.scan_progress import _sse_generator

        t = ScanProgressTracker(scan_id="gen-100")
        t.register_modules(["m1"])
        t.start()
        t.module_completed("m1")  # 100%
        register_tracker("gen-100", t)

        async def _run():
            gen = _sse_generator("gen-100", interval=0.1, timeout=5.0)
            first = await gen.__anext__()
            assert "progress" in first
            second = await gen.__anext__()
            assert "complete" in second

        asyncio.run(_run())

    def test_no_tracker_immediate_complete(self):
        from spiderfoot.api.routers.scan_progress import _sse_generator

        async def _run():
            gen = _sse_generator("ghost", interval=0.1, timeout=5.0)
            first = await gen.__anext__()
            assert "complete" in first
            assert "tracker_removed" in first

        asyncio.run(_run())


# ===================================================================
# ScanProgressTracker integration
# ===================================================================

class TestTrackerIntegration:
    def test_snapshot_round_trip(self, tracker):
        tracker.module_started("sfp_dns")
        tracker.record_event("sfp_dns", produced=True)
        tracker.module_completed("sfp_dns")

        snap = tracker.get_snapshot()
        d = snap.to_dict()
        assert d["overall_pct"] > 0
        assert d["modules_completed"] == 1
        assert d["modules_total"] == 3
        assert d["events_total"] == 1

    def test_module_progress_dict(self, tracker):
        tracker.module_started("sfp_dns")
        mp = tracker.get_module_progress("sfp_dns")
        d = mp.to_dict()
        assert d["status"] == "running"
        assert d["module"] == "sfp_dns"

    def test_running_failed_pending(self, tracker):
        tracker.module_started("sfp_dns")
        tracker.module_failed("sfp_ssl", "timeout")
        assert "sfp_dns" in tracker.get_running_modules()
        assert "sfp_ssl" in tracker.get_failed_modules()
        assert "sfp_ports" in tracker.get_pending_modules()

    def test_to_dict(self, tracker):
        d = tracker.to_dict()
        assert d["scan_id"] == "scan-001"
        assert "modules" in d
        assert len(d["modules"]) == 3


# ===================================================================
# FastAPI endpoint tests
# ===================================================================

@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestProgressEndpoints:
    def test_get_progress(self, client, tracker):
        register_tracker("scan-001", tracker)
        tracker.module_started("sfp_dns")
        resp = client.get("/api/scans/scan-001/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scan_id"] == "scan-001"
        assert "overall_pct" in data
        assert "running_modules" in data
        assert "sfp_dns" in data["running_modules"]

    def test_get_progress_404(self, client):
        resp = client.get("/api/scans/nonexistent/progress")
        assert resp.status_code == 404

    def test_get_module_progress(self, client, tracker):
        register_tracker("scan-001", tracker)
        tracker.module_started("sfp_dns")
        tracker.module_completed("sfp_dns")
        resp = client.get("/api/scans/scan-001/progress/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scan_id"] == "scan-001"
        assert "sfp_dns" in data["modules"]
        assert data["modules"]["sfp_dns"]["status"] == "completed"
        assert data["summary"]["completed"] == 1
        assert data["summary"]["total"] == 3

    def test_get_module_progress_404(self, client):
        resp = client.get("/api/scans/ghost/progress/modules")
        assert resp.status_code == 404

    def test_get_history(self, client, tracker):
        register_tracker("scan-001", tracker)
        # Generate some snapshots
        tracker.get_snapshot()
        tracker.get_snapshot()
        resp = client.get("/api/scans/scan-001/progress/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2
        assert len(data["snapshots"]) >= 2

    def test_get_history_404(self, client):
        resp = client.get("/api/scans/ghost/progress/history")
        assert resp.status_code == 404

    def test_create_tracker(self, client):
        resp = client.post(
            "/api/scans/new-scan/progress/start",
            json=["sfp_a", "sfp_b"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["scan_id"] == "new-scan"
        assert data["modules_registered"] == 2
        assert data["status"] == "tracking"
        # Verify tracker was registered
        assert get_tracker("new-scan") is not None

    def test_create_tracker_no_modules(self, client):
        resp = client.post("/api/scans/bare-scan/progress/start")
        assert resp.status_code == 201
        data = resp.json()
        assert data["modules_registered"] == 0

    def test_create_tracker_conflict(self, client, tracker):
        register_tracker("scan-001", tracker)
        resp = client.post(
            "/api/scans/scan-001/progress/start",
            json=["sfp_a"],
        )
        assert resp.status_code == 409

    def test_list_active_trackers(self, client, tracker):
        register_tracker("scan-001", tracker)
        tracker.module_started("sfp_dns")
        tracker.module_completed("sfp_dns")

        resp = client.get("/api/scans/progress/active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["active_scans"][0]["scan_id"] == "scan-001"
        assert data["active_scans"][0]["modules_total"] == 3

    def test_list_active_empty(self, client):
        resp = client.get("/api/scans/progress/active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0

    def test_stream_progress_404(self, client):
        resp = client.get("/api/scans/ghost/progress/stream")
        assert resp.status_code == 404

    def test_stream_progress_returns_sse(self, client, tracker):
        """SSE stream should return text/event-stream content type."""
        tracker.register_modules(["m1"])
        tracker.start()
        tracker.module_completed("m1")  # complete immediately
        # Re-register with full modules so tracker is valid
        t = ScanProgressTracker(scan_id="sse-test")
        t.register_modules(["m1"])
        t.start()
        t.module_completed("m1")
        register_tracker("sse-test", t)

        with client.stream("GET", "/api/scans/sse-test/progress/stream") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            # Read first chunk
            lines = []
            for chunk in resp.iter_text():
                lines.append(chunk)
                if len(lines) >= 2:
                    break
            combined = "".join(lines)
            assert "event:" in combined

    def test_progress_full_lifecycle(self, client):
        """Test full lifecycle: create, update, query, complete."""
        # Create
        resp = client.post(
            "/api/scans/lifecycle/progress/start",
            json=["mod_a", "mod_b"],
        )
        assert resp.status_code == 201

        # Get progress — should be 0%
        resp = client.get("/api/scans/lifecycle/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_pct"] == 0.0

        # Simulate module progress
        t = get_tracker("lifecycle")
        t.module_started("mod_a")
        t.module_completed("mod_a")

        # Module breakdown
        resp = client.get("/api/scans/lifecycle/progress/modules")
        data = resp.json()
        assert data["summary"]["completed"] == 1
        assert data["summary"]["pending"] == 1

        # Complete second module
        t.module_started("mod_b")
        t.module_completed("mod_b")

        resp = client.get("/api/scans/lifecycle/progress")
        data = resp.json()
        assert data["overall_pct"] == 100.0

    def test_progress_with_events(self, client):
        """Record events and verify throughput is tracked."""
        resp = client.post(
            "/api/scans/evtest/progress/start",
            json=["mod_a"],
        )
        assert resp.status_code == 201

        t = get_tracker("evtest")
        t.module_started("mod_a")
        for _ in range(10):
            t.record_event("mod_a", produced=True)

        resp = client.get("/api/scans/evtest/progress")
        data = resp.json()
        assert data["events_total"] == 10
        assert data["throughput_eps"] > 0

    def test_progress_with_failures(self, client):
        """Failed modules should appear in failed_modules."""
        resp = client.post(
            "/api/scans/failtest/progress/start",
            json=["mod_a", "mod_b"],
        )
        assert resp.status_code == 201
        t = get_tracker("failtest")
        t.module_started("mod_a")
        t.module_failed("mod_a", "Connection timeout")

        resp = client.get("/api/scans/failtest/progress")
        data = resp.json()
        assert "mod_a" in data["failed_modules"]
        assert data["overall_pct"] == 50.0  # 1 of 2 terminal


# ===================================================================
# Edge cases
# ===================================================================

class TestEdgeCases:
    def test_register_same_id_twice(self, tracker):
        register_tracker("dup", tracker)
        t2 = ScanProgressTracker(scan_id="dup")
        register_tracker("dup", t2)
        assert get_tracker("dup") is t2

    def test_concurrent_register(self):
        """Basic thread safety - register from multiple threads."""
        import threading

        def register_n(n):
            t = ScanProgressTracker(scan_id=f"t-{n}")
            register_tracker(f"t-{n}", t)

        threads = [threading.Thread(target=register_n, args=(i,)) for i in range(20)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(list_tracked_scans()) == 20

    def test_tracker_snapshot_no_modules(self):
        t = ScanProgressTracker(scan_id="empty")
        t.start()
        snap = t.get_snapshot()
        assert snap.overall_pct == 0.0
        assert snap.modules_total == 0
