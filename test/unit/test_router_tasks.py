"""Tests for spiderfoot.api.routers.tasks — task-queue management API.

Uses a fresh in-memory TaskManager (the singleton is replaced per test) to cover
listing, active filtering, submission of a placeholder task, get-by-id, the
invalid task_type 400, completed-clearing, and the 404 paths — no Celery/DB.
"""
from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.tasks as tasks_mod
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.ops.task_queue import TaskManager


@pytest.fixture
def client(monkeypatch):
    mgr = TaskManager()
    monkeypatch.setattr(tasks_mod, "get_task_manager", lambda: mgr)
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(tasks_mod.router)
    return TestClient(app)


class TestList:
    def test_list_empty(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 200

    def test_active_empty(self, client):
        resp = client.get("/tasks/active")
        assert resp.status_code == 200
        assert resp.json()["total_active"] == 0


class TestSubmitAndGet:
    def test_submit_then_get(self, client):
        resp = client.post("/tasks", json={"task_type": "generic", "meta": {}})
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]
        # Give the placeholder task a moment to run, then fetch it.
        time.sleep(0.05)
        got = client.get(f"/tasks/{task_id}")
        assert got.status_code == 200
        assert got.json()["task_id"] == task_id

    def test_submit_invalid_type_400(self, client):
        resp = client.post("/tasks", json={"task_type": "not-a-type", "meta": {}})
        assert resp.status_code == 400

    def test_get_unknown_404(self, client):
        assert client.get("/tasks/nonexistent").status_code == 404


class TestClearCompleted:
    def test_clear_completed_returns_count(self, client):
        # Submit a placeholder, let it finish, then clear terminal tasks.
        client.post("/tasks", json={"task_type": "generic", "meta": {}})
        time.sleep(0.1)
        resp = client.delete("/tasks/completed")
        assert resp.status_code == 200
        assert "removed" in resp.json()

    def test_delete_unknown_404(self, client):
        assert client.delete("/tasks/nonexistent").status_code == 404
