# -*- coding: utf-8 -*-
"""
Scan Schedule router — Manage recurring scan schedules.

Provides REST endpoints for creating, listing, updating, and deleting
recurring scan schedules that are executed by Celery Beat.

Endpoints:
  GET    /api/schedules         - List all schedules
  POST   /api/schedules         - Create a new schedule
  GET    /api/schedules/{id}    - Get schedule details
  PUT    /api/schedules/{id}    - Update a schedule
  DELETE /api/schedules/{id}    - Delete a schedule
  POST   /api/schedules/{id}/trigger - Manually trigger a scheduled scan
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..dependencies import get_api_key

log = logging.getLogger("spiderfoot.api.schedules")

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

api_key_dep = Depends(get_api_key)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ScheduleCreateRequest(BaseModel):
    """Request body for creating a recurring scan schedule."""
    name: str = Field(..., min_length=1, max_length=200, description="Schedule name")
    target: str = Field(..., description="Scan target")
    engine: str | None = Field(None, description="Scan engine profile name")
    modules: list[str] | None = Field(None, description="Module list (overrides engine)")
    interval_hours: float = Field(24.0, ge=0.25, le=8760, description="Run every N hours")
    enabled: bool = Field(True, description="Whether the schedule is active")
    description: str = ""
    tags: list[str] = []
    notify_on_change: bool = Field(True, description="Send notification when changes detected")
    max_runs: int = Field(0, ge=0, description="Max runs (0 = unlimited)")


class ScheduleUpdateRequest(BaseModel):
    """Request body for updating a schedule — all fields optional."""
    name: str | None = Field(None, min_length=1, max_length=200, description="Schedule name")
    target: str | None = Field(None, description="Scan target")
    engine: str | None = Field(None, description="Scan engine profile name")
    modules: list[str] | None = Field(None, description="Module list (overrides engine)")
    interval_hours: float | None = Field(None, ge=0.25, le=8760, description="Run every N hours")
    enabled: bool | None = Field(None, description="Whether the schedule is active")
    description: str | None = Field(None)
    tags: list[str] | None = Field(None)
    notify_on_change: bool | None = Field(None, description="Send notification when changes detected")
    max_runs: int | None = Field(None, ge=0, description="Max runs (0 = unlimited)")


class ScheduleResponse(BaseModel):
    """Schedule detail response."""
    id: str
    name: str
    target: str
    engine: str | None = None
    modules: list[str] | None = None
    interval_hours: float
    enabled: bool
    description: str = ""
    tags: list[str] = []
    notify_on_change: bool = True
    max_runs: int = 0
    runs_completed: int = 0
    last_run_at: float | None = None
    next_run_at: float | None = None
    created_at: float = 0


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleResponse]
    total: int


# ---------------------------------------------------------------------------
# Redis-backed schedule store
# ---------------------------------------------------------------------------


def _get_redis():
    """Get Redis connection for schedule storage."""
    import redis as redis_lib
    redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
    return redis_lib.from_url(redis_url)


def _schedule_key(schedule_id: str) -> str:
    return f"sf:schedule:{schedule_id}"


def _schedule_index_key() -> str:
    return "sf:schedules:index"


def _store_schedule(data: dict[str, Any]) -> None:
    """Store a schedule in Redis."""
    r = _get_redis()
    schedule_id = data["id"]
    r.set(_schedule_key(schedule_id), json.dumps(data), ex=86400 * 365)
    r.sadd(_schedule_index_key(), schedule_id)


def _get_schedule(schedule_id: str) -> dict[str, Any] | None:
    """Get a schedule from Redis."""
    r = _get_redis()
    raw = r.get(_schedule_key(schedule_id))
    if raw:
        return json.loads(raw)
    return None


def _delete_schedule(schedule_id: str) -> bool:
    """Delete a schedule from Redis."""
    r = _get_redis()
    r.delete(_schedule_key(schedule_id))
    r.srem(_schedule_index_key(), schedule_id)
    return True


def _list_schedules() -> list[dict[str, Any]]:
    """List all schedules from Redis."""
    r = _get_redis()
    schedule_ids = r.smembers(_schedule_index_key())
    schedules = []
    for sid in schedule_ids:
        sid_str = sid.decode("utf-8") if isinstance(sid, bytes) else sid
        data = _get_schedule(sid_str)
        if data:
            schedules.append(data)
    return schedules


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=ScheduleListResponse)
async def list_schedules(
    api_key: str = api_key_dep,
) -> ScheduleListResponse:
    """List all scan schedules."""
    schedules = _list_schedules()
    return ScheduleListResponse(
        schedules=[ScheduleResponse(**s) for s in schedules],
        total=len(schedules),
    )


@router.post("", status_code=201, response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleCreateRequest,
    api_key: str = api_key_dep,
) -> ScheduleResponse:
    """Create a new recurring scan schedule."""
    schedule_id = str(uuid.uuid4())
    now = time.time()

    schedule_data = {
        "id": schedule_id,
        "name": request.name,
        "target": request.target,
        "engine": request.engine,
        "modules": request.modules,
        "interval_hours": request.interval_hours,
        "enabled": request.enabled,
        "description": request.description,
        "tags": request.tags,
        "notify_on_change": request.notify_on_change,
        "max_runs": request.max_runs,
        "runs_completed": 0,
        "last_run_at": None,
        "next_run_at": now + (request.interval_hours * 3600),
        "created_at": now,
    }

    _store_schedule(schedule_data)

    # Register with Celery Beat dynamic schedule
    try:
        _register_beat_schedule(schedule_data)
    except Exception as e:
        log.warning("Failed to register with Celery Beat: %s", e)

    log.info("Created scan schedule '%s' for target '%s'", request.name, request.target)
    return ScheduleResponse(**schedule_data)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    api_key: str = api_key_dep,
) -> ScheduleResponse:
    """Get schedule details."""
    data = _get_schedule(schedule_id)
    if not data:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ScheduleResponse(**data)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    request: ScheduleUpdateRequest,
    api_key: str = api_key_dep,
) -> ScheduleResponse:
    """Update an existing schedule (partial update — only supplied fields change)."""
    existing = _get_schedule(schedule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule not found")

    updates = request.model_dump(exclude_unset=True)
    schedule_data = {**existing, **updates}

    # Recalculate next_run_at if interval changed
    if "interval_hours" in updates:
        schedule_data["next_run_at"] = time.time() + (schedule_data["interval_hours"] * 3600)

    _store_schedule(schedule_data)
    log.info("Updated scan schedule '%s'", schedule_id)
    return ScheduleResponse(**schedule_data)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    api_key: str = api_key_dep,
) -> None:
    """Delete a schedule."""
    data = _get_schedule(schedule_id)
    if not data:
        raise HTTPException(status_code=404, detail="Schedule not found")
    _delete_schedule(schedule_id)
    log.info("Deleted scan schedule '%s'", schedule_id)


@router.post("/{schedule_id}/trigger", response_model=dict)
async def trigger_schedule(
    schedule_id: str,
    api_key: str = api_key_dep,
) -> dict[str, Any]:
    """Manually trigger a scheduled scan immediately."""
    data = _get_schedule(schedule_id)
    if not data:
        raise HTTPException(status_code=404, detail="Schedule not found")

    try:
        from spiderfoot.celery_app import is_celery_available
        if is_celery_available():
            from spiderfoot.tasks.scan import run_scan
            from spiderfoot import SpiderFootHelpers

            scan_id = SpiderFootHelpers.genScanInstanceId()
            target = data["target"]
            target_type = SpiderFootHelpers.targetTypeFromString(target)

            run_scan.apply_async(
                kwargs={
                    "scan_name": f"Scheduled: {data['name']}",
                    "scan_target": target,
                    "module_list": data.get("modules") or [],
                    "type_list": [],
                    "global_opts": {},
                },
                task_id=scan_id,
                queue="scan",
            )

            # Update last_run
            data["last_run_at"] = time.time()
            data["runs_completed"] = data.get("runs_completed", 0) + 1
            data["next_run_at"] = time.time() + (data["interval_hours"] * 3600)
            _store_schedule(data)

            return {"scan_id": scan_id, "message": "Scheduled scan triggered"}
        else:
            raise HTTPException(status_code=503, detail="Celery workers not available")
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Failed to trigger scan")
        raise HTTPException(status_code=500, detail="Failed to trigger scan")


# ---------------------------------------------------------------------------
# Celery Beat integration
# ---------------------------------------------------------------------------


def _register_beat_schedule(schedule_data: dict[str, Any]) -> None:
    """Register a schedule with Celery Beat's dynamic schedule store.

    Stores the schedule in Redis so the monitor.trigger_recurring_scans
    periodic task picks it up on its next iteration.
    """
    r = _get_redis()
    r.sadd("sf:recurring:schedules", json.dumps({
        "target": schedule_data["target"],
        "modules": schedule_data.get("modules") or [],
        "types": [],
        "options": {},
        "engine": schedule_data.get("engine"),
        "interval_seconds": schedule_data["interval_hours"] * 3600,
        "next_run": schedule_data.get("next_run_at", time.time()),
        "last_run": schedule_data.get("last_run_at"),
        "schedule_id": schedule_data["id"],
        "name": schedule_data["name"],
    }))
