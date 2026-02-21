"""
Data Retention API router — manage retention policies and enforcement.

Endpoints for CRUD on retention rules, dry-run preview, enforcement,
and history/statistics.

v5.6.8
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from spiderfoot.data_retention import (
    RetentionManager,
    RetentionRule,
    RetentionAction,
    FileResourceAdapter,
    InMemoryResourceAdapter,
)
from ..dependencies import get_api_key

router = APIRouter(dependencies=[Depends(get_api_key)])

# -------------------------------------------------------------------
# Singleton manager
# -------------------------------------------------------------------
_file_adapter = FileResourceAdapter()
_manager = RetentionManager(adapter=_file_adapter)


def _get_manager() -> RetentionManager:
    return _manager


# -------------------------------------------------------------------
# Pydantic schemas
# -------------------------------------------------------------------

class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    resource: str = Field(..., description="Resource type: scans, logs, cache, exports, audit")
    max_age_days: int = Field(0, ge=0)
    max_count: int = Field(0, ge=0)
    max_size_mb: float = Field(0.0, ge=0.0)
    action: str = Field("delete", description="delete | archive | export_then_delete")
    enabled: bool = True
    exclude_pattern: str = ""


class RuleUpdate(BaseModel):
    max_age_days: int | None = None
    max_count: int | None = None
    max_size_mb: float | None = None
    action: str | None = None
    enabled: bool | None = None
    exclude_pattern: str | None = None


class DirectoryMapping(BaseModel):
    resource: str = Field(..., description="Resource name to map")
    path: str = Field(..., description="Filesystem path for the resource")


# -------------------------------------------------------------------
# Rule CRUD
# -------------------------------------------------------------------

@router.get("/retention/rules", tags=["data-retention"])
async def list_rules():
    """List all retention rules."""
    mgr = _get_manager()
    return {"rules": [r.to_dict() for r in mgr.list_rules()]}


@router.get("/retention/rules/{name}", tags=["data-retention"])
async def get_rule(name: str):
    """Get a retention rule by name."""
    mgr = _get_manager()
    rule = mgr.get_rule(name)
    if not rule:
        raise HTTPException(404, f"Rule '{name}' not found")
    return rule.to_dict()


@router.post("/retention/rules", tags=["data-retention"], status_code=201)
async def create_rule(body: RuleCreate):
    """Create a new retention rule."""
    mgr = _get_manager()
    if mgr.get_rule(body.name):
        raise HTTPException(409, f"Rule '{body.name}' already exists")

    try:
        action = RetentionAction(body.action)
    except ValueError:
        raise HTTPException(400, f"Invalid action: {body.action}")

    rule = RetentionRule(
        name=body.name,
        resource=body.resource,
        max_age_days=body.max_age_days,
        max_count=body.max_count,
        max_size_mb=body.max_size_mb,
        action=action,
        enabled=body.enabled,
        exclude_pattern=body.exclude_pattern,
    )
    mgr.add_rule(rule)
    return {"created": rule.to_dict()}


@router.patch("/retention/rules/{name}", tags=["data-retention"])
async def update_rule(name: str, body: RuleUpdate):
    """Update an existing retention rule."""
    mgr = _get_manager()
    rule = mgr.get_rule(name)
    if not rule:
        raise HTTPException(404, f"Rule '{name}' not found")

    if body.max_age_days is not None:
        rule.max_age_days = body.max_age_days
    if body.max_count is not None:
        rule.max_count = body.max_count
    if body.max_size_mb is not None:
        rule.max_size_mb = body.max_size_mb
    if body.action is not None:
        try:
            rule.action = RetentionAction(body.action)
        except ValueError:
            raise HTTPException(400, f"Invalid action: {body.action}")
    if body.enabled is not None:
        rule.enabled = body.enabled
    if body.exclude_pattern is not None:
        rule.exclude_pattern = body.exclude_pattern

    return {"updated": rule.to_dict()}


@router.delete("/retention/rules/{name}", tags=["data-retention"])
async def delete_rule(name: str):
    """Delete a retention rule."""
    mgr = _get_manager()
    if not mgr.remove_rule(name):
        raise HTTPException(404, f"Rule '{name}' not found")
    return {"deleted": name}


# -------------------------------------------------------------------
# Enforcement
# -------------------------------------------------------------------

@router.post("/retention/preview", tags=["data-retention"])
async def preview_enforcement(
    rule_name: str | None = Query(None, description="Preview a specific rule only"),
):
    """Dry-run enforcement — preview what would be cleaned up."""
    mgr = _get_manager()
    results = mgr.preview(rule_name=rule_name)
    return {
        "dry_run": True,
        "results": [r.to_dict() for r in results],
    }


@router.post("/retention/enforce", tags=["data-retention"])
async def enforce_policies(
    rule_name: str | None = Query(None, description="Enforce a specific rule only"),
):
    """Execute retention policies (irreversible)."""
    mgr = _get_manager()
    results = mgr.enforce(rule_name=rule_name)
    return {
        "executed": True,
        "results": [r.to_dict() for r in results],
    }


# -------------------------------------------------------------------
# History & statistics
# -------------------------------------------------------------------

@router.get("/retention/history", tags=["data-retention"])
async def enforcement_history(
    limit: int = Query(50, ge=1, le=500),
):
    """Get past enforcement results."""
    mgr = _get_manager()
    history = mgr.history[-limit:]
    return {"history": [r.to_dict() for r in history]}


@router.get("/retention/stats", tags=["data-retention"])
async def retention_stats():
    """Aggregate retention statistics."""
    mgr = _get_manager()
    return mgr.stats


# -------------------------------------------------------------------
# Resource directories
# -------------------------------------------------------------------

@router.post("/retention/directories", tags=["data-retention"])
async def set_directory(body: DirectoryMapping):
    """Map a resource name to a filesystem directory for file-based retention."""
    mgr = _get_manager()
    adapter = mgr.adapter
    if isinstance(adapter, FileResourceAdapter):
        adapter.set_directory(body.resource, body.path)
        return {"mapped": body.resource, "path": body.path}
    raise HTTPException(400, "Current adapter does not support directory mapping")


@router.get("/retention/actions", tags=["data-retention"])
async def list_actions():
    """List available retention actions."""
    return {
        "actions": [
            {"id": a.value, "description": {
                "delete": "Permanently remove data",
                "archive": "Move data to archive storage",
                "export_then_delete": "Export data before deleting",
            }.get(a.value, a.value)}
            for a in RetentionAction
        ]
    }


@router.get("/retention/resources", tags=["data-retention"])
async def list_resources():
    """List recognized resource types."""
    return {
        "resources": [
            {"id": "scans", "description": "Scan results and findings"},
            {"id": "logs", "description": "Scan execution and debug logs"},
            {"id": "cache", "description": "Cached module data and DNS lookups"},
            {"id": "exports", "description": "Generated export files (STIX, SARIF, CSV)"},
            {"id": "audit", "description": "API audit trail records"},
            {"id": "reports", "description": "Generated PDF/HTML reports"},
            {"id": "webhooks", "description": "Webhook delivery logs"},
            {"id": "sessions", "description": "Expired user session data"},
            {"id": "temp", "description": "Temporary processing files"},
        ]
    }
