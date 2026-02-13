# -*- coding: utf-8 -*-
"""
RBAC info router — View role hierarchy and permission configuration.

Endpoints:
  GET  /api/rbac            - Full RBAC configuration summary
  GET  /api/rbac/roles      - List all roles with permissions
  GET  /api/rbac/roles/{r}  - Get a specific role's permissions
  GET  /api/rbac/check      - Check if a role has a permission
  GET  /api/rbac/me         - Current user's role and permissions
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..dependencies import get_api_key

log = logging.getLogger("spiderfoot.api.rbac")

router = APIRouter(prefix="/api/rbac", tags=["rbac"])

api_key_dep = Depends(get_api_key)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RoleInfo(BaseModel):
    name: str
    level: int
    permission_count: int
    permissions: list[str]


class RBACConfigResponse(BaseModel):
    enforced: bool
    default_role: str
    roles: list[RoleInfo]
    permissions: dict[str, str]


class PermissionCheckResponse(BaseModel):
    role: str
    permission: str
    allowed: bool


class CurrentUserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    role: str
    permissions: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=RBACConfigResponse)
async def get_rbac_config(
    api_key: str = api_key_dep,
) -> RBACConfigResponse:
    """Get full RBAC configuration summary."""
    from spiderfoot.rbac import get_rbac_summary
    summary = get_rbac_summary()
    return RBACConfigResponse(
        enforced=summary["enforced"],
        default_role=summary["default_role"],
        roles=[RoleInfo(**r) for r in summary["roles"]],
        permissions=summary["permissions"],
    )


@router.get("/roles", response_model=list[RoleInfo])
async def list_roles(
    api_key: str = api_key_dep,
) -> list[RoleInfo]:
    """List all roles with their permissions."""
    from spiderfoot.rbac import get_role_hierarchy
    return [RoleInfo(**r) for r in get_role_hierarchy()]


@router.get("/roles/{role_name}", response_model=RoleInfo)
async def get_role(
    role_name: str,
    api_key: str = api_key_dep,
) -> RoleInfo:
    """Get a specific role's permissions."""
    from spiderfoot.rbac import parse_role, get_permissions, EFFECTIVE_PERMISSIONS
    try:
        role = parse_role(role_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    perms = get_permissions(role)
    return RoleInfo(
        name=role.value,
        level=role.level,
        permission_count=len(perms),
        permissions=perms,
    )


@router.get("/check", response_model=PermissionCheckResponse)
async def check_permission(
    role: str = Query(..., description="Role name"),
    permission: str = Query(..., description="Permission string (e.g. scan:create)"),
    api_key: str = api_key_dep,
) -> PermissionCheckResponse:
    """Check if a role has a specific permission."""
    from spiderfoot.rbac import has_permission
    allowed = has_permission(role, permission)
    return PermissionCheckResponse(
        role=role,
        permission=permission,
        allowed=allowed,
    )


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user(
    request: Request,
    api_key: str = api_key_dep,
) -> CurrentUserResponse:
    """Get the current user's role and permissions."""
    from spiderfoot.rbac import get_default_user, get_permissions, UserContext
    user: UserContext | None = getattr(request.state, "user", None)
    if user is None:
        user = get_default_user()
    perms = get_permissions(user.role)
    return CurrentUserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        permissions=perms,
    )
