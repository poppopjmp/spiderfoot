"""Enhanced RBAC API router.

Provides endpoints for custom role management, role bindings,
and permission checking with tenant-scoped access control.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from spiderfoot.rbac_enhanced import EnhancedRBACManager, ALL_PERMISSIONS
from ..dependencies import get_api_key

logger = logging.getLogger("spiderfoot.api.rbac_enhanced")

router = APIRouter(dependencies=[Depends(get_api_key)])

_manager = EnhancedRBACManager()


def get_manager() -> EnhancedRBACManager:
    return _manager


class CreateRoleRequest(BaseModel):
    name: str
    permissions: list[str]
    description: str = ""
    inherits_from: str | None = None
    tenant_id: str = "default"


class UpdateRoleRequest(BaseModel):
    permissions: list[str] | None = None
    description: str | None = None


class AssignRoleRequest(BaseModel):
    user_id: str
    role_id: str
    tenant_id: str = "default"
    resource_scope: str | None = None
    expires_at: str | None = None


class PermissionCheckRequest(BaseModel):
    user_id: str
    permission: str
    tenant_id: str = "default"
    resource: str | None = None


# ----- Role endpoints -----

@router.get("/rbac/v2/roles", tags=["rbac-v2"])
async def list_roles(include_system: bool = True):
    """List all roles including custom ones."""
    roles = get_manager().list_roles(include_system=include_system)
    return {
        "roles": [r.to_dict() for r in roles],
        "total": len(roles),
    }


@router.post("/rbac/v2/roles", tags=["rbac-v2"])
async def create_role(request: CreateRoleRequest):
    """Create a custom role."""
    try:
        role = get_manager().create_role(
            name=request.name,
            permissions=request.permissions,
            description=request.description,
            inherits_from=request.inherits_from,
            tenant_id=request.tenant_id,
        )
    except ValueError as e:
        logger.warning("RBAC operation failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid RBAC operation")
    return role.to_dict()


@router.get("/rbac/v2/roles/{role_id}", tags=["rbac-v2"])
async def get_role(role_id: str):
    """Get a role with its effective permissions."""
    role = get_manager().get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    effective = get_manager().get_effective_permissions(role_id)
    result = role.to_dict()
    result["effective_permissions"] = sorted(effective)
    return result


@router.put("/rbac/v2/roles/{role_id}", tags=["rbac-v2"])
async def update_role(role_id: str, request: UpdateRoleRequest):
    """Update a custom role."""
    try:
        role = get_manager().update_role(
            role_id=role_id,
            permissions=request.permissions,
            description=request.description,
        )
    except ValueError as e:
        logger.warning("RBAC operation failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid RBAC operation")
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role.to_dict()


@router.delete("/rbac/v2/roles/{role_id}", tags=["rbac-v2"])
async def delete_role(role_id: str):
    """Delete a custom role."""
    try:
        ok = get_manager().delete_role(role_id)
    except ValueError as e:
        logger.warning("RBAC operation failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid RBAC operation")
    if not ok:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"status": "deleted"}


# ----- Binding endpoints -----

@router.post("/rbac/v2/bindings", tags=["rbac-v2"])
async def assign_role(request: AssignRoleRequest):
    """Assign a role to a user."""
    try:
        binding = get_manager().assign_role(
            user_id=request.user_id,
            role_id=request.role_id,
            tenant_id=request.tenant_id,
            resource_scope=request.resource_scope,
            expires_at=request.expires_at,
        )
    except ValueError as e:
        logger.warning("RBAC operation failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid RBAC operation")
    return binding.to_dict()


@router.delete("/rbac/v2/bindings/{binding_id}", tags=["rbac-v2"])
async def revoke_binding(binding_id: str):
    """Revoke a role binding."""
    ok = get_manager().revoke_binding(binding_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Binding not found")
    return {"status": "revoked"}


@router.get("/rbac/v2/users/{user_id}/roles", tags=["rbac-v2"])
async def user_roles(user_id: str, tenant_id: str = "default"):
    """Get all roles for a user in a tenant."""
    bindings = get_manager().get_user_roles(user_id, tenant_id)
    return {
        "bindings": [b.to_dict() for b in bindings],
        "total": len(bindings),
    }


@router.get("/rbac/v2/users/{user_id}/permissions", tags=["rbac-v2"])
async def user_permissions(user_id: str, tenant_id: str = "default"):
    """Get all effective permissions for a user."""
    perms = get_manager().get_user_permissions(user_id, tenant_id)
    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "permissions": sorted(perms),
        "total": len(perms),
    }


@router.post("/rbac/v2/check", tags=["rbac-v2"])
async def check_permission(request: PermissionCheckRequest):
    """Check if a user has a specific permission."""
    allowed = get_manager().check_permission(
        user_id=request.user_id,
        permission=request.permission,
        tenant_id=request.tenant_id,
        resource=request.resource,
    )
    return {
        "allowed": allowed,
        "user_id": request.user_id,
        "permission": request.permission,
        "tenant_id": request.tenant_id,
    }


@router.get("/rbac/v2/permissions", tags=["rbac-v2"])
async def list_all_permissions():
    """List all available permissions."""
    # Group by category
    categories: dict[str, list[str]] = {}
    for perm in ALL_PERMISSIONS:
        cat = perm.split(":")[0]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(perm)
    return {
        "permissions": ALL_PERMISSIONS,
        "categories": categories,
        "total": len(ALL_PERMISSIONS),
    }
