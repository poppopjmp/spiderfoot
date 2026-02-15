# -*- coding: utf-8 -*-
"""
Audit log query router — Search and view security audit events.

Endpoints:
  GET  /api/audit          - Query audit events with filters
  GET  /api/audit/actions   - List available audit actions
  GET  /api/audit/stats     - Audit event statistics
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..dependencies import get_api_key

log = logging.getLogger("spiderfoot.api.audit")

router = APIRouter(prefix="/api/audit", tags=["audit"])

api_key_dep = Depends(get_api_key)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AuditEventResponse(BaseModel):
    event_id: str
    timestamp: float
    action: str
    actor: str
    actor_ip: str = ""
    resource: str
    resource_type: str
    details: dict = {}
    severity: str = "info"
    request_id: str = ""


class AuditQueryResponse(BaseModel):
    events: list[AuditEventResponse]
    total: int
    query_params: dict = {}


class AuditStatsResponse(BaseModel):
    total_events: int
    events_by_action: dict[str, int]
    events_by_severity: dict[str, int]
    events_by_actor: dict[str, int]
    time_range: dict[str, float]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=AuditQueryResponse)
async def query_audit(
    action: str | None = Query(None, description="Filter by action prefix"),
    actor: str | None = Query(None, description="Filter by actor"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    severity: str | None = Query(None, description="Filter by severity"),
    since_hours: float = Query(24.0, ge=0, le=720, description="Events from last N hours"),
    limit: int = Query(100, ge=1, le=1000),
    api_key: str = api_key_dep,
) -> AuditQueryResponse:
    """Query audit events with filters."""
    from spiderfoot.audit_log import query_audit_events

    since = time.time() - (since_hours * 3600) if since_hours > 0 else 0

    events = query_audit_events(
        action=action,
        actor=actor,
        resource_type=resource_type,
        severity=severity,
        since=since,
        limit=limit,
    )

    return AuditQueryResponse(
        events=[AuditEventResponse(**e.to_dict()) for e in events],
        total=len(events),
        query_params={
            "action": action,
            "actor": actor,
            "resource_type": resource_type,
            "severity": severity,
            "since_hours": since_hours,
            "limit": limit,
        },
    )


@router.get("/actions", response_model=dict)
async def list_audit_actions(
    api_key: str = api_key_dep,
) -> dict:
    """List all available audit action constants."""
    from spiderfoot.audit_log import Actions
    actions = {}
    for attr in dir(Actions):
        if not attr.startswith("_"):
            val = getattr(Actions, attr)
            if isinstance(val, str):
                category = val.split(".")[0] if "." in val else "other"
                if category not in actions:
                    actions[category] = []
                actions[category].append(val)
    return {"actions": actions}


@router.get("/stats", response_model=AuditStatsResponse)
async def audit_stats(
    since_hours: float = Query(24.0, ge=0, le=720, description="Stats from last N hours"),
    api_key: str = api_key_dep,
) -> AuditStatsResponse:
    """Get audit event statistics."""
    from spiderfoot.audit_log import query_audit_events

    since = time.time() - (since_hours * 3600) if since_hours > 0 else 0
    events = query_audit_events(since=since, limit=10000)

    by_action: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    min_ts = float("inf")
    max_ts = 0.0

    for e in events:
        by_action[e.action] = by_action.get(e.action, 0) + 1
        by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
        if e.actor:
            by_actor[e.actor] = by_actor.get(e.actor, 0) + 1
        if e.timestamp < min_ts:
            min_ts = e.timestamp
        if e.timestamp > max_ts:
            max_ts = e.timestamp

    return AuditStatsResponse(
        total_events=len(events),
        events_by_action=dict(sorted(by_action.items(), key=lambda x: -x[1])),
        events_by_severity=by_severity,
        events_by_actor=dict(sorted(by_actor.items(), key=lambda x: -x[1])[:20]),
        time_range={"oldest": min_ts if min_ts != float("inf") else 0, "newest": max_ts},
    )
