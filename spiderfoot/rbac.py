# -*- coding: utf-8 -*-
"""
Role-Based Access Control (RBAC) foundation for SpiderFoot.

Provides a role hierarchy, permission definitions, and access-control
utilities that can be used across the API, CLI, and WebUI.

Roles (ordered by ascending privilege):
  - viewer   — Read-only access to scan results and reports
  - analyst  — Can run scans, generate reports, manage own schedules
  - operator — Full scan control, engine management, schedule management
  - admin    — Full system access including config, users, rate limits

Permissions are string constants like ``scan:read``, ``scan:create``,
``config:write``, etc.  Each role inherits all permissions from the
roles below it.

Usage::

    from spiderfoot.rbac import has_permission, require_permission

    # Check programmatically
    if has_permission("analyst", "scan:create"):
        ...

    # FastAPI dependency
    @router.post("/scans")
    async def create_scan(
        user=Depends(require_permission("scan:create")),
    ):
        ...
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.rbac")


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

class Role(str, Enum):
    """User roles, ordered by ascending privilege level."""
    VIEWER = "viewer"
    ANALYST = "analyst"
    OPERATOR = "operator"
    ADMIN = "admin"

    @property
    def level(self) -> int:
        """Numeric privilege level for comparison."""
        return _ROLE_LEVELS[self]


_ROLE_LEVELS: dict[Role, int] = {
    Role.VIEWER: 10,
    Role.ANALYST: 20,
    Role.OPERATOR: 30,
    Role.ADMIN: 40,
}


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

# Permission string format: "resource:action"
# Actions: read, create, update, delete, execute, manage

PERMISSIONS: dict[str, str] = {
    # Scan operations
    "scan:read": "View scan results and metadata",
    "scan:create": "Start new scans",
    "scan:update": "Update scan configuration",
    "scan:delete": "Delete scans and results",
    "scan:abort": "Abort running scans",

    # Reports
    "report:read": "View and download reports",
    "report:create": "Generate new reports",

    # Data
    "data:read": "View scan data and events",
    "data:export": "Export scan data (CSV, JSON, etc.)",

    # Engines
    "engine:read": "View scan engine profiles",
    "engine:create": "Create new scan engines",
    "engine:update": "Update scan engine profiles",
    "engine:delete": "Delete scan engine profiles",

    # Schedules
    "schedule:read": "View scheduled scans",
    "schedule:create": "Create scheduled scans",
    "schedule:update": "Update scheduled scans",
    "schedule:delete": "Delete scheduled scans",
    "schedule:trigger": "Manually trigger scheduled scans",

    # Configuration
    "config:read": "View system configuration",
    "config:write": "Modify system configuration",

    # Rate limits
    "ratelimit:read": "View rate limit settings",
    "ratelimit:write": "Modify rate limit settings",

    # Users/API keys
    "user:read": "View users and API keys",
    "user:create": "Create users and API keys",
    "user:update": "Update users and API keys",
    "user:delete": "Delete users and API keys",

    # System
    "system:health": "View system health",
    "system:admin": "Full system administration",

    # Notifications
    "notification:read": "View notification settings",
    "notification:write": "Modify notification settings",
}


# ---------------------------------------------------------------------------
# Role → Permission mapping
# ---------------------------------------------------------------------------

# Each role's EXPLICIT permissions (inherits from roles below it)
_ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.VIEWER: {
        "scan:read",
        "report:read",
        "data:read",
        "engine:read",
        "schedule:read",
        "system:health",
        "notification:read",
    },
    Role.ANALYST: {
        "scan:create",
        "scan:update",
        "scan:abort",
        "report:create",
        "data:export",
        "schedule:create",
        "schedule:update",
        "schedule:trigger",
        "config:read",
        "ratelimit:read",
    },
    Role.OPERATOR: {
        "scan:delete",
        "engine:create",
        "engine:update",
        "engine:delete",
        "schedule:delete",
        "notification:write",
    },
    Role.ADMIN: {
        "config:write",
        "ratelimit:write",
        "user:read",
        "user:create",
        "user:update",
        "user:delete",
        "system:admin",
    },
}


def _build_effective_permissions() -> dict[Role, frozenset[str]]:
    """Build effective permission sets with inheritance.

    Each role inherits all permissions from lower-privilege roles.
    """
    effective: dict[Role, set[str]] = {}
    ordered = sorted(_ROLE_LEVELS.items(), key=lambda x: x[1])

    accumulated: set[str] = set()
    for role, _level in ordered:
        accumulated = accumulated | _ROLE_PERMISSIONS.get(role, set())
        effective[role] = set(accumulated)

    return {r: frozenset(p) for r, p in effective.items()}


# Pre-computed effective permissions for each role
EFFECTIVE_PERMISSIONS: dict[Role, frozenset[str]] = _build_effective_permissions()


# ---------------------------------------------------------------------------
# Permission checking
# ---------------------------------------------------------------------------

def parse_role(role_str: str) -> Role:
    """Parse a role string into a Role enum.

    Args:
        role_str: Role name (case-insensitive).

    Returns:
        Role enum value.

    Raises:
        ValueError: If the role string is not valid.
    """
    try:
        return Role(role_str.lower().strip())
    except ValueError:
        valid = ", ".join(r.value for r in Role)
        raise ValueError(f"Invalid role '{role_str}'. Valid roles: {valid}")


def has_permission(role: str | Role, permission: str) -> bool:
    """Check if a role has a specific permission.

    Args:
        role: Role name or Role enum.
        permission: Permission string (e.g. 'scan:create').

    Returns:
        True if the role has the permission (directly or inherited).
    """
    if isinstance(role, str):
        try:
            role = parse_role(role)
        except ValueError:
            return False

    return permission in EFFECTIVE_PERMISSIONS.get(role, frozenset())


def get_permissions(role: str | Role) -> list[str]:
    """Get all effective permissions for a role.

    Args:
        role: Role name or Role enum.

    Returns:
        Sorted list of permission strings.
    """
    if isinstance(role, str):
        role = parse_role(role)
    return sorted(EFFECTIVE_PERMISSIONS.get(role, frozenset()))


def get_role_hierarchy() -> list[dict[str, Any]]:
    """Get the full role hierarchy with descriptions.

    Returns:
        List of role dicts with name, level, and permission count.
    """
    result = []
    for role in sorted(Role, key=lambda r: r.level):
        perms = EFFECTIVE_PERMISSIONS.get(role, frozenset())
        result.append({
            "name": role.value,
            "level": role.level,
            "permission_count": len(perms),
            "permissions": sorted(perms),
        })
    return result


# ---------------------------------------------------------------------------
# User context
# ---------------------------------------------------------------------------

@dataclass
class UserContext:
    """Represents an authenticated user with role information.

    This is attached to request state or passed through the API
    dependency injection chain.
    """
    user_id: str = ""
    username: str = ""
    email: str = ""
    role: Role = Role.VIEWER
    api_key_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        """Check if this user has a specific permission."""
        return has_permission(self.role, permission)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "api_key_id": self.api_key_id,
        }


# Default role for API keys — configurable via SF_DEFAULT_ROLE
DEFAULT_ROLE = os.environ.get("SF_DEFAULT_ROLE", "admin")


def get_default_user() -> UserContext:
    """Return a default user context (for backward compatibility).

    When RBAC is not fully enforced, the default user gets the role
    configured in ``SF_DEFAULT_ROLE`` (defaults to admin).
    """
    return UserContext(
        user_id="default",
        username="admin",
        role=parse_role(DEFAULT_ROLE),
    )


# ---------------------------------------------------------------------------
# FastAPI dependency — require_permission
# ---------------------------------------------------------------------------

def require_permission(permission: str):
    """FastAPI dependency that checks for a specific permission.

    Usage::

        @router.post("/scans")
        async def create_scan(
            user: UserContext = Depends(require_permission("scan:create")),
        ):
            ...

    When RBAC enforcement is enabled (``SF_RBAC_ENFORCE=true``), this will
    return 403 Forbidden if the user lacks the permission.  When disabled,
    it returns the default user context.
    """
    from fastapi import Depends, HTTPException, Request

    enforce = os.environ.get("SF_RBAC_ENFORCE", "false").lower() in ("true", "1", "yes")

    async def _check(request: Request) -> UserContext:
        # Try to get user context from request state (set by auth middleware)
        user: UserContext | None = getattr(request.state, "user", None)

        if user is None:
            if enforce:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required",
                )
            user = get_default_user()

        if enforce and not user.has_permission(permission):
            log.warning(
                "Permission denied: user=%s role=%s permission=%s path=%s",
                user.username, user.role.value, permission, request.url.path,
            )
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: requires '{permission}'",
                headers={"X-Required-Permission": permission},
            )

        return user

    # Fix: `from __future__ import annotations` turns type hints into strings,
    # which prevents FastAPI from recognising `Request` as the special request
    # object.  We restore the real class reference so FastAPI injects it properly.
    _check.__annotations__["request"] = Request
    _check.__annotations__["return"] = UserContext

    return _check


# ---------------------------------------------------------------------------
# RBAC info endpoint helpers
# ---------------------------------------------------------------------------

def get_rbac_summary() -> dict[str, Any]:
    """Return the full RBAC configuration summary."""
    enforce = os.environ.get("SF_RBAC_ENFORCE", "false").lower() in ("true", "1", "yes")
    return {
        "enforced": enforce,
        "default_role": DEFAULT_ROLE,
        "roles": get_role_hierarchy(),
        "permissions": {k: v for k, v in sorted(PERMISSIONS.items())},
    }
