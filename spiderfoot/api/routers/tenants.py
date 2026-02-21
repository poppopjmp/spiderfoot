"""Multi-tenancy API router for SpiderFoot.

Provides tenant CRUD, quota management, and usage tracking endpoints.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from ..dependencies import get_api_key, SafeId
from pydantic import BaseModel

from spiderfoot.multi_tenancy import TenantManager, TenantPlan

logger = logging.getLogger("spiderfoot.api.tenants")

router = APIRouter(dependencies=[Depends(get_api_key)])

# Singleton manager
_manager = TenantManager()


def get_manager() -> TenantManager:
    return _manager


class TenantCreateRequest(BaseModel):
    name: str
    slug: str
    plan: str = "free"
    owner_email: str = ""
    custom_quotas: dict[str, int] | None = None


class TenantUpdateRequest(BaseModel):
    name: str | None = None
    plan: str | None = None
    enabled: bool | None = None
    quotas: dict[str, int] | None = None
    settings: dict[str, Any] | None = None


@router.get("/tenants", tags=["tenants"])
async def list_tenants(include_disabled: bool = Query(False)):
    """List all tenants."""
    tenants = get_manager().list_tenants(include_disabled=include_disabled)
    return {
        "tenants": [t.to_dict() for t in tenants],
        "total": len(tenants),
    }


@router.post("/tenants", tags=["tenants"])
async def create_tenant(request: TenantCreateRequest):
    """Create a new tenant."""
    try:
        plan = TenantPlan(request.plan)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan: {request.plan}. Valid: {[p.value for p in TenantPlan]}",
        )

    try:
        tenant = get_manager().create_tenant(
            name=request.name,
            slug=request.slug,
            plan=plan,
            owner_email=request.owner_email,
            custom_quotas=request.custom_quotas,
        )
    except ValueError as e:
        logger.warning("Tenant already exists: %s", e)
        raise HTTPException(status_code=409, detail="Tenant already exists")

    logger.info("Created tenant: %s", tenant.tenant_id)
    return tenant.to_dict()


@router.get("/tenants/{tenant_id}", tags=["tenants"])
async def get_tenant(tenant_id: SafeId):
    """Get a specific tenant."""
    tenant = get_manager().get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant.to_dict()


@router.put("/tenants/{tenant_id}", tags=["tenants"])
async def update_tenant(tenant_id: SafeId, request: TenantUpdateRequest):
    """Update a tenant."""
    plan = TenantPlan(request.plan) if request.plan else None
    tenant = get_manager().update_tenant(
        tenant_id=tenant_id,
        name=request.name,
        plan=plan,
        enabled=request.enabled,
        quotas=request.quotas,
        settings=request.settings,
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant.to_dict()


@router.delete("/tenants/{tenant_id}", tags=["tenants"])
async def delete_tenant(tenant_id: SafeId):
    """Delete a tenant."""
    try:
        ok = get_manager().delete_tenant(tenant_id)
    except ValueError as e:
        logger.warning("Invalid tenant operation: %s", e)
        raise HTTPException(status_code=400, detail="Invalid tenant operation")
    if not ok:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"status": "deleted"}


@router.get("/tenants/{tenant_id}/usage", tags=["tenants"])
async def tenant_usage(tenant_id: SafeId):
    """Get resource usage for a tenant."""
    usage = get_manager().get_usage(tenant_id)
    if not usage:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return usage


@router.get("/tenants/plans/info", tags=["tenants"])
async def plan_info():
    """Get available plans and their default quotas."""
    from spiderfoot.multi_tenancy import _PLAN_QUOTAS
    return {
        "plans": [
            {
                "name": plan.value,
                "quotas": _PLAN_QUOTAS.get(plan.value, {}),
            }
            for plan in TenantPlan
        ],
    }
