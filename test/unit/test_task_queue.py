"""
Tests for spiderfoot.task_queue and spiderfoot.api.routers.tasks.

Covers: TaskManager lifecycle, submit/get/list/cancel/progress,
callbacks, history pruning, singleton accessor, and all REST endpoints.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from spiderfoot.task_queue import (
    TaskManager,
    TaskRecord,
    TaskState,
    TaskType,
    _TaskEntry,
    get_task_manager,
    reset_task_manager,
)

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from spiderfoot.api.routers.tasks import router

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mgr():
    """A fresh TaskManager for each test."""
    m = TaskManager(max_workers=2, max_history=10)
    yield m
    m.shutdown(wait=True)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global singleton between tests."""
    reset_task_manager()
    yield
    reset_task_manager()


@pytest.fixture
def client():
    if not HAS_FASTAPI:
        pytest.skip("FastAPI not installed")
    app = FastAPI()
    app.include_router(router, prefix="/api", tags=["tasks"])
    return TestClient(app)


# ===================================================================
# TaskRecord / TaskEntry models
# ===================================================================

class TestTaskRecord:
    def test_to_dict(self):
        r = TaskRecord(
            task_id="t1",
            task_type=TaskType.SCAN,
            state=TaskState.COMPLETED,
            progress=100.0,
            meta={"scan_id": "s1"},
            result="done",
            created_at=1000.0,
            started_at=1001.0,
            completed_at=1005.0,
        )
        d = r.to_dict()
        assert d["task_id"] == "t1"
        assert d["task_type"] == "scan"
        assert d["state"] == "completed"
        assert d["progress"] == 100.0
        assert d["elapsed_seconds"] == 4.0
        assert d["result"] == "done"

    def test_is_terminal(self):
        r = TaskRecord(
            task_id="t2", task_type=TaskType.GENERIC,
            state=TaskState.RUNNING, progress=50, meta={},
            created_at=0,
        )
        assert not r.is_terminal
        r2 = TaskRecord(
            task_id="t3", task_type=TaskType.GENERIC,
            state=TaskState.FAILED, progress=0, meta={},
            created_at=0,
        )
        assert r2.is_terminal

    def test_elapsed_not_started(self):
        r = TaskRecord(
            task_id="t4", task_type=TaskType.GENERIC,
            state=TaskState.QUEUED, progress=0, meta={},
            created_at=0,
        )
        assert r.elapsed_seconds == 0.0


class TestTaskEntry:
    def test_to_record(self):
        e = _TaskEntry(
            task_id="e1", task_type=TaskType.REPORT,
            meta={"k": "v"}, created_at=1000.0,
        )
        r = e.to_record()
        assert r.task_id == "e1"
        assert r.state == TaskState.QUEUED
        assert r.meta == {"k": "v"}

    def test_is_terminal_states(self):
        e = _TaskEntry(
            task_id="e2", task_type=TaskType.GENERIC,
            meta={}, created_at=0,
        )
        e.state = TaskState.QUEUED
        assert not e.is_terminal
        e.state = TaskState.RUNNING
        assert not e.is_terminal
        e.state = TaskState.COMPLETED
        assert e.is_terminal
        e.state = TaskState.CANCELLED
        assert e.is_terminal


# ===================================================================
# TaskManager core
# ===================================================================

class TestTaskManagerSubmit:
    def test_submit_returns_id(self, mgr):
        tid = mgr.submit(TaskType.GENERIC, lambda: "ok")
        assert isinstance(tid, str)
        assert len(tid) > 0

    def test_submit_with_custom_id(self, mgr):
        tid = mgr.submit(TaskType.SCAN, lambda: None, task_id="custom-1")
        assert tid == "custom-1"

    def test_submit_duplicate_id_raises(self, mgr):
        mgr.submit(TaskType.GENERIC, lambda: None, task_id="dup")
        with pytest.raises(ValueError, match="already exists"):
            mgr.submit(TaskType.GENERIC, lambda: None, task_id="dup")

    def test_task_reaches_completed(self, mgr):
        event = threading.Event()

        def work():
            event.set()
            return 42

        tid = mgr.submit(TaskType.GENERIC, work)
        event.wait(timeout=5)
        time.sleep(0.2)  # allow completion logic to run
        record = mgr.get(tid)
        assert record is not None
        assert record.state == TaskState.COMPLETED
        assert record.result == 42
        assert record.progress == 100.0
        assert record.started_at is not None
        assert record.completed_at is not None

    def test_task_failure_recorded(self, mgr):
        def fail():
            raise RuntimeError("boom")

        tid = mgr.submit(TaskType.GENERIC, fail)
        time.sleep(0.5)
        record = mgr.get(tid)
        assert record.state == TaskState.FAILED
        assert "boom" in record.error

    def test_submit_with_args(self, mgr):
        results = []

        def work(a, b, key="default"):
            results.append((a, b, key))

        tid = mgr.submit(
            TaskType.GENERIC, work,
            args=(1, 2), kwargs={"key": "custom"},
        )
        time.sleep(0.5)
        assert results == [(1, 2, "custom")]


class TestTaskManagerQuery:
    def test_get_nonexistent(self, mgr):
        assert mgr.get("nope") is None

    def test_list_empty(self, mgr):
        assert mgr.list_tasks() == []

    def test_list_filtered(self, mgr):
        event = threading.Event()

        def slow():
            event.wait(5)

        mgr.submit(TaskType.SCAN, slow, task_id="s1")
        mgr.submit(TaskType.REPORT, lambda: None, task_id="r1")
        time.sleep(0.3)

        # Filter by type
        scan_tasks = mgr.list_tasks(task_type=TaskType.SCAN)
        assert any(r.task_id == "s1" for r in scan_tasks)

        event.set()
        time.sleep(0.3)

    def test_active_count(self, mgr):
        event = threading.Event()
        mgr.submit(TaskType.GENERIC, lambda: event.wait(5), task_id="a1")
        time.sleep(0.2)
        assert mgr.active_count() >= 1
        event.set()
        time.sleep(0.3)

    def test_task_count(self, mgr):
        mgr.submit(TaskType.GENERIC, lambda: None, task_id="c1")
        assert mgr.task_count >= 1


class TestTaskManagerCancel:
    def test_cancel_running(self, mgr):
        event = threading.Event()
        mgr.submit(TaskType.GENERIC, lambda: event.wait(10), task_id="x1")
        time.sleep(0.2)
        assert mgr.cancel("x1") is True
        record = mgr.get("x1")
        assert record.state == TaskState.CANCELLED
        event.set()

    def test_cancel_completed(self, mgr):
        mgr.submit(TaskType.GENERIC, lambda: None, task_id="x2")
        time.sleep(0.5)
        assert mgr.cancel("x2") is False

    def test_cancel_nonexistent(self, mgr):
        assert mgr.cancel("ghost") is False


class TestTaskManagerProgress:
    def test_update_progress(self, mgr):
        event = threading.Event()
        mgr.submit(TaskType.GENERIC, lambda: event.wait(5), task_id="p1")
        time.sleep(0.2)
        assert mgr.update_progress("p1", 50.0) is True
        record = mgr.get("p1")
        assert record.progress == 50.0
        event.set()
        time.sleep(0.3)

    def test_update_clamps(self, mgr):
        event = threading.Event()
        mgr.submit(TaskType.GENERIC, lambda: event.wait(5), task_id="p2")
        time.sleep(0.2)
        mgr.update_progress("p2", 150.0)
        assert mgr.get("p2").progress == 100.0
        mgr.update_progress("p2", -10.0)
        assert mgr.get("p2").progress == 0.0
        event.set()
        time.sleep(0.3)

    def test_update_nonexistent(self, mgr):
        assert mgr.update_progress("nope", 10) is False

    def test_update_completed_fails(self, mgr):
        mgr.submit(TaskType.GENERIC, lambda: None, task_id="p3")
        time.sleep(0.5)
        assert mgr.update_progress("p3", 50) is False


class TestTaskManagerCallbacks:
    def test_callback_fires_on_complete(self, mgr):
        results = []
        mgr.on_task_complete(lambda r: results.append(r))
        mgr.submit(TaskType.GENERIC, lambda: "done", task_id="cb1")
        time.sleep(0.5)
        assert len(results) == 1
        assert results[0].task_id == "cb1"
        assert results[0].state == TaskState.COMPLETED

    def test_callback_fires_on_cancel(self, mgr):
        results = []
        mgr.on_task_complete(lambda r: results.append(r))
        event = threading.Event()
        mgr.submit(TaskType.GENERIC, lambda: event.wait(10), task_id="cb2")
        time.sleep(0.2)
        mgr.cancel("cb2")
        assert any(r.state == TaskState.CANCELLED for r in results)
        event.set()

    def test_callback_error_doesnt_crash(self, mgr):
        def bad_cb(r):
            raise ValueError("oops")
        mgr.on_task_complete(bad_cb)
        mgr.submit(TaskType.GENERIC, lambda: None, task_id="cb3")
        time.sleep(0.5)
        # Should not raise — error logged internally
        assert mgr.get("cb3").state == TaskState.COMPLETED


class TestTaskManagerHistoryPruning:
    def test_prune_keeps_max(self):
        mgr = TaskManager(max_workers=2, max_history=3)
        try:
            for i in range(6):
                mgr.submit(TaskType.GENERIC, lambda: None, task_id=f"h{i}")
            time.sleep(1.5)
            # Should have pruned to ~3
            assert mgr.task_count <= 4  # allow 1 margin for timing
        finally:
            mgr.shutdown(wait=True)

    def test_clear_completed(self, mgr):
        mgr.submit(TaskType.GENERIC, lambda: None, task_id="cc1")
        mgr.submit(TaskType.GENERIC, lambda: None, task_id="cc2")
        time.sleep(0.5)
        removed = mgr.clear_completed()
        assert removed >= 2
        assert mgr.task_count == 0


class TestTaskManagerShutdown:
    def test_shutdown_completes(self, mgr):
        mgr.submit(TaskType.GENERIC, lambda: None)
        time.sleep(0.3)
        mgr.shutdown(wait=True)
        # Should not raise


# ===================================================================
# Singleton
# ===================================================================

class TestSingleton:
    def test_get_returns_same(self):
        m1 = get_task_manager()
        m2 = get_task_manager()
        assert m1 is m2

    def test_reset_creates_new(self):
        m1 = get_task_manager()
        reset_task_manager()
        m2 = get_task_manager()
        assert m1 is not m2


# ===================================================================
# FastAPI endpoints
# ===================================================================

@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestTaskEndpoints:
    def test_list_empty(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["tasks"] == []

    def test_submit_task(self, client):
        resp = client.post("/api/tasks", json={
            "task_type": "generic",
            "meta": {"info": "test"},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "task_id" in data
        assert data["state"] == "queued"

        # Wait for it to complete
        time.sleep(0.5)
        resp2 = client.get(f"/api/tasks/{data['task_id']}")
        assert resp2.status_code == 200
        assert resp2.json()["state"] == "completed"

    def test_submit_invalid_type(self, client):
        resp = client.post("/api/tasks", json={
            "task_type": "invalid_type",
        })
        assert resp.status_code == 400

    def test_get_task(self, client):
        # Submit first
        resp = client.post("/api/tasks", json={"task_type": "scan"})
        tid = resp.json()["task_id"]
        time.sleep(0.5)

        resp2 = client.get(f"/api/tasks/{tid}")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["task_id"] == tid
        assert data["task_type"] == "scan"

    def test_get_task_404(self, client):
        resp = client.get("/api/tasks/nonexistent")
        assert resp.status_code == 404

    def test_cancel_task(self, client):
        # Submit a task that waits
        mgr = get_task_manager()
        event = threading.Event()
        tid = mgr.submit(TaskType.GENERIC, lambda: event.wait(30), task_id="cancel-me")
        time.sleep(0.2)

        resp = client.delete(f"/api/tasks/{tid}")
        assert resp.status_code == 200
        assert resp.json()["state"] == "cancelled"
        event.set()

    def test_cancel_404(self, client):
        resp = client.delete("/api/tasks/ghost")
        assert resp.status_code == 404

    def test_cancel_completed_409(self, client):
        resp = client.post("/api/tasks", json={"task_type": "generic"})
        tid = resp.json()["task_id"]
        time.sleep(0.5)
        resp2 = client.delete(f"/api/tasks/{tid}")
        assert resp2.status_code == 409

    def test_list_active(self, client):
        mgr = get_task_manager()
        event = threading.Event()
        mgr.submit(TaskType.GENERIC, lambda: event.wait(30), task_id="act1")
        time.sleep(0.2)

        resp = client.get("/api/tasks/active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_active"] >= 1

        event.set()
        time.sleep(0.3)

    def test_clear_completed(self, client):
        # Submit and wait for completion
        resp = client.post("/api/tasks", json={"task_type": "generic"})
        time.sleep(0.5)

        resp2 = client.delete("/api/tasks/completed")
        assert resp2.status_code == 200
        assert resp2.json()["removed"] >= 1

    def test_list_filtered_by_state(self, client):
        resp = client.post("/api/tasks", json={"task_type": "generic"})
        time.sleep(0.5)
        resp2 = client.get("/api/tasks?state=completed")
        assert resp2.status_code == 200
        data = resp2.json()
        assert all(t["state"] == "completed" for t in data["tasks"])

    def test_list_filtered_by_type(self, client):
        client.post("/api/tasks", json={"task_type": "report"})
        client.post("/api/tasks", json={"task_type": "scan"})
        time.sleep(0.5)
        resp = client.get("/api/tasks?task_type=report")
        assert resp.status_code == 200
        data = resp.json()
        assert all(t["task_type"] == "report" for t in data["tasks"])

    def test_list_invalid_state(self, client):
        resp = client.get("/api/tasks?state=invalid")
        assert resp.status_code == 400

    def test_task_meta_preserved(self, client):
        resp = client.post("/api/tasks", json={
            "task_type": "workspace",
            "meta": {"ws_id": "w1", "action": "sync"},
        })
        tid = resp.json()["task_id"]
        time.sleep(0.5)
        resp2 = client.get(f"/api/tasks/{tid}")
        assert resp2.json()["meta"]["ws_id"] == "w1"
