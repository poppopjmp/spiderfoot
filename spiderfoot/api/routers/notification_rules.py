"""
Notification Rules Engine API router — rule CRUD, evaluation, history.

v5.7.4
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from ..dependencies import get_api_key
from pydantic import BaseModel, Field
from typing import Any

from spiderfoot.notification_rules import NotificationRulesEngine

router = APIRouter(dependencies=[Depends(get_api_key)])

_engine = NotificationRulesEngine()


# -------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------

class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    enabled: bool = True
    priority: int = Field(5, ge=1, le=10)
    conditions: list[dict] = Field(default_factory=list)
    logic: str = Field("and", description="and | or")
    channels: list[dict] = Field(
        default_factory=list,
        description='List of {"type": "slack", "config": {...}}',
    )
    cooldown_seconds: int = Field(300, ge=0)
    max_per_hour: int = Field(10, ge=1, le=1000)
    deduplicate: bool = True
    severity: str = Field("info")
    scan_ids: list[str] = Field(default_factory=list)
    tenant_id: str = ""


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    priority: int | None = None
    conditions: list[dict] | None = None
    logic: str | None = None
    channels: list[dict] | None = None
    cooldown_seconds: int | None = None
    max_per_hour: int | None = None
    severity: str | None = None


class EvaluateRequest(BaseModel):
    event: dict = Field(..., description="Event dict with type, data, module, etc.")
    scan_id: str = ""


# -------------------------------------------------------------------
# Rule CRUD
# -------------------------------------------------------------------

@router.get("/notification-rules", tags=["notification-rules"])
async def list_rules(
    enabled_only: bool = Query(False),
    severity: str | None = Query(None),
    tenant_id: str | None = Query(None),
):
    rules = _engine.list_rules(
        enabled_only=enabled_only, severity=severity, tenant_id=tenant_id,
    )
    return {"rules": [r.to_dict() for r in rules]}


@router.post("/notification-rules", tags=["notification-rules"], status_code=201)
async def create_rule(body: RuleCreate):
    r = _engine.create_rule(body.model_dump())
    return {"rule": r.to_dict()}


@router.get("/notification-rules/{rule_id}", tags=["notification-rules"])
async def get_rule(rule_id: str):
    r = _engine.get_rule(rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    return r.to_dict()


@router.patch("/notification-rules/{rule_id}", tags=["notification-rules"])
async def update_rule(rule_id: str, body: RuleUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    r = _engine.update_rule(rule_id, updates)
    if not r:
        raise HTTPException(404, "Rule not found")
    return {"updated": r.to_dict()}


@router.delete("/notification-rules/{rule_id}", tags=["notification-rules"])
async def delete_rule(rule_id: str):
    if not _engine.delete_rule(rule_id):
        raise HTTPException(404, "Rule not found")
    return {"deleted": rule_id}


# -------------------------------------------------------------------
# Evaluation
# -------------------------------------------------------------------

@router.post("/notification-rules/evaluate", tags=["notification-rules"])
async def evaluate_event(body: EvaluateRequest):
    """Evaluate an event against all enabled rules."""
    triggered = _engine.evaluate(body.event, scan_id=body.scan_id)
    return {
        "triggered": len(triggered),
        "notifications": [n.to_dict() for n in triggered],
    }


# -------------------------------------------------------------------
# History & stats
# -------------------------------------------------------------------

@router.get("/notification-rules/history", tags=["notification-rules"])
async def notification_history(
    limit: int = Query(50, ge=1, le=500),
    rule_id: str | None = Query(None),
    severity: str | None = Query(None),
):
    history = _engine.get_history(limit=limit, rule_id=rule_id, severity=severity)
    return {"history": [n.to_dict() for n in history]}


@router.get("/notification-rules/stats", tags=["notification-rules"])
async def notification_stats():
    return _engine.get_stats()


# -------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------

@router.get("/notification-rules/operators", tags=["notification-rules"])
async def list_operators():
    return {"operators": _engine.get_operators()}


@router.get("/notification-rules/channels", tags=["notification-rules"])
async def list_channels():
    return {"channels": _engine.get_channels()}
