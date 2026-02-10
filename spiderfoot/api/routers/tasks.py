"""
Task Queue API Router for SpiderFoot.

Provides REST endpoints for listing, querying, submitting, and
cancelling background tasks managed by the ``TaskManager``.

Endpoints:
  GET    /api/tasks           - List tasks (filterable by state, type)
  GET    /api/tasks/active    - List active (queued+running) tasks
  GET    /api/tasks/{task_id} - Get task status
  POST   /api/tasks           - Submit a new task
  DELETE /api/tasks/{task_id} - Cancel a task
  DELETE /api/tasks/completed - Clear completed tasks from history
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger("spiderfoot.api.tasks")

try:
    from fastapi import APIRouter, HTTPException, Query
    from pydantic import BaseModel, Field

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from spiderfoot.task_queue import (
    TaskManager,
    TaskRecord,
    TaskState,
    TaskType,
    get_task_manager,
)


# -----------------------------------------------------------------------
# Pydantic models (request / response)
# -----------------------------------------------------------------------

if HAS_FASTAPI:

    class TaskSubmitRequest(BaseModel):
        """Body for submitting a new task."""
        task_type: str = Field(
            "generic",
            description="Task type: scan, report, workspace, export, generic.",
        )
        meta: dict[str, Any] = Field(
            default_factory=dict,
            description="Arbitrary metadata attached to the task.",
        )

    class TaskResponse(BaseModel):
        """Serialised task record."""
        task_id: str
        task_type: str
        state: str
        progress: float
        meta: dict[str, Any]
        result: Any = None
        error: str | None = None
        created_at: float
        started_at: float | None = None
        completed_at: float | None = None
        elapsed_seconds: float = 0.0


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _parse_task_type(value: str) -> TaskType:
    """Convert a string to ``TaskType`` or raise 400."""
    try:
        return TaskType(value.lower())
    except ValueError:
        if not HAS_FASTAPI:
            raise
        valid = ", ".join(t.value for t in TaskType)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_type '{value}'. Valid: {valid}",
        )


def _parse_task_state(value: str) -> TaskState:
    """Convert a string to ``TaskState`` or raise 400."""
    try:
        return TaskState(value.lower())
    except ValueError:
        if not HAS_FASTAPI:
            raise
        valid = ", ".join(s.value for s in TaskState)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state '{value}'. Valid: {valid}",
        )


def _record_to_dict(record: TaskRecord) -> dict:
    """Convert a TaskRecord to an API-friendly dict."""
    return record.to_dict()


# -----------------------------------------------------------------------
# FastAPI Router
# -----------------------------------------------------------------------

if not HAS_FASTAPI:

    class _StubRouter:
        pass

    router = _StubRouter()
else:
    router = APIRouter()

    @router.get(
        "/tasks",
        summary="List tasks",
        description="List background tasks, optionally filtered by state and type.",
    )
    async def list_tasks(
        state: str | None = Query(None, description="Filter by state"),
        task_type: str | None = Query(None, description="Filter by task type"),
        limit: int = Query(50, ge=1, le=500),
    ):
        mgr = get_task_manager()
        st = _parse_task_state(state) if state else None
        tt = _parse_task_type(task_type) if task_type else None
        tasks = mgr.list_tasks(state=st, task_type=tt, limit=limit)
        return {
            "tasks": [_record_to_dict(t) for t in tasks],
            "count": len(tasks),
            "active": mgr.active_count(),
            "total": mgr.task_count,
        }

    @router.get(
        "/tasks/active",
        summary="List active tasks",
        description="Shorthand for listing queued and running tasks.",
    )
    async def list_active_tasks():
        mgr = get_task_manager()
        queued = mgr.list_tasks(state=TaskState.QUEUED, limit=100)
        running = mgr.list_tasks(state=TaskState.RUNNING, limit=100)
        active = queued + running
        active.sort(key=lambda r: r.created_at, reverse=True)
        return {
            "tasks": [_record_to_dict(t) for t in active],
            "queued": len(queued),
            "running": len(running),
            "total_active": len(active),
        }

    @router.get(
        "/tasks/{task_id}",
        summary="Get task status",
        description="Retrieve the current status and result of a specific task.",
    )
    async def get_task(task_id: str):
        mgr = get_task_manager()
        record = mgr.get(task_id)
        if record is None:
            raise HTTPException(
                status_code=404,
                detail=f"Task '{task_id}' not found.",
            )
        return _record_to_dict(record)

    @router.post(
        "/tasks",
        status_code=201,
        summary="Submit a task (low-level)",
        description=(
            "Submit a no-op placeholder task. In practice, scans and "
            "reports are submitted through their own endpoints and "
            "automatically registered with the TaskManager."
        ),
    )
    async def submit_task(body: TaskSubmitRequest):
        mgr = get_task_manager()
        tt = _parse_task_type(body.task_type)

        # Submit a no-op so the task record exists — real callers
        # use mgr.submit() directly with an actual callable.
        def _noop():
            return {"message": "placeholder task completed"}

        task_id = mgr.submit(
            task_type=tt,
            func=_noop,
            meta=body.meta,
        )
        return {"task_id": task_id, "state": "queued"}

    @router.delete(
        "/tasks/completed",
        summary="Clear completed tasks",
        description="Remove all terminal (completed/failed/cancelled) tasks from history.",
    )
    async def clear_completed():
        mgr = get_task_manager()
        count = mgr.clear_completed()
        return {"removed": count}

    @router.delete(
        "/tasks/{task_id}",
        summary="Cancel a task",
        description="Attempt to cancel a queued or running task.",
    )
    async def cancel_task(task_id: str):
        mgr = get_task_manager()
        record = mgr.get(task_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        ok = mgr.cancel(task_id)
        if not ok:
            raise HTTPException(
                status_code=409,
                detail=f"Task '{task_id}' is already in terminal state: {record.state.value}",
            )
        return {"task_id": task_id, "state": "cancelled"}
