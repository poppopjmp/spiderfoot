# -*- coding: utf-8 -*-
"""
Role-Based Access Control (RBAC) for SpiderFoot.

Provides both the foundational RBAC system and the enhanced RBAC with custom
roles, tenant-scoped permissions, and resource-level access control.

**Foundation layer** (used by auth middleware, API dependencies):
  - ``Role`` enum (VIEWER, ANALYST, OPERATOR, ADMIN)
  - ``has_permission()``, ``require_permission()``
  - ``UserContext`` dataclass

**Enhanced layer** (used by /rbac/v2 API endpoints):
  - ``EnhancedRBACManager`` with Redis-backed custom role CRUD
  - ``CustomRole``, ``UserRoleBinding`` dataclasses
  - ``ALL_PERMISSIONS`` comprehensive permission list
  - Tenant-scoped and resource-level permission checks

Roles (ordered by ascending privilege):
  - viewer   — Read-only access to scan results and reports
  - analyst  — Can run scans, generate reports, manage own schedules
  - operator — Full scan control, engine management, schedule management
  - admin    — Full system access including config, users, rate limits

Usage::

    from spiderfoot.auth.rbac import has_permission, require_permission

    # Check programmatically
    if has_permission("analyst", "scan:create"):
        ...

    # FastAPI dependency
    @router.post("/scans")
    async def create_scan(
        user=Depends(require_permission("scan:create")),
    ):
        ...

    # Enhanced RBAC
    from spiderfoot.auth.rbac import EnhancedRBACManager
    manager = EnhancedRBACManager(redis_client=redis)
    manager.check_permission(user_id, "scan:create", tenant_id="acme")
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.auth.rbac")


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


# ---------------------------------------------------------------------------
# Enhanced RBAC — Custom roles, tenant-scoped bindings, resource permissions
# ---------------------------------------------------------------------------
# Merged from rbac_enhanced.py (Cycle 22).

import json
import uuid
from datetime import datetime, timezone
from dataclasses import asdict

# Comprehensive permission list used by the enhanced RBAC system
ALL_PERMISSIONS = [
    # Scan operations
    "scan:read", "scan:create", "scan:update", "scan:delete", "scan:abort",
    "scan:export", "scan:schedule",
    # Data access
    "data:read", "data:export", "data:delete", "data:search",
    # Asset management
    "asset:read", "asset:create", "asset:update", "asset:delete",
    "asset:tag", "asset:link",
    # Engine management
    "engine:read", "engine:create", "engine:update", "engine:delete",
    # Schedule management
    "schedule:read", "schedule:create", "schedule:update", "schedule:delete",
    "schedule:trigger",
    # Configuration
    "config:read", "config:update",
    # User management
    "user:read", "user:create", "user:update", "user:delete",
    "user:assign_role",
    # Tenant management
    "tenant:read", "tenant:create", "tenant:update", "tenant:delete",
    "tenant:manage_quotas",
    # API key management
    "api_key:read", "api_key:create", "api_key:revoke", "api_key:delete",
    # Reports
    "report:read", "report:create", "report:export", "report:delete",
    # System
    "system:read", "system:configure", "system:audit",
    "system:metrics", "system:manage_roles",
    # Notifications
    "notification:read", "notification:configure",
    # Monitor
    "monitor:read", "monitor:create", "monitor:update", "monitor:delete",
    "monitor:check",
    # STIX/SARIF
    "stix:export", "sarif:export",
    # ASM
    "asm:read", "asm:ingest", "asm:manage",
]


@dataclass
class CustomRole:
    """A custom role definition (Redis-backed when available)."""
    role_id: str
    name: str
    description: str = ""
    permissions: list[str] = field(default_factory=list)
    inherits_from: str | None = None
    tenant_id: str = "default"
    created_at: str = ""
    created_by: str = ""
    is_system: bool = False

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UserRoleBinding:
    """Binds a user to a role within a tenant scope."""
    binding_id: str
    user_id: str
    role_id: str
    tenant_id: str = "default"
    resource_scope: str | None = None  # e.g., "scan:abc123" for per-resource
    granted_at: str = ""
    granted_by: str = ""
    expires_at: str | None = None

    def __post_init__(self):
        if not self.granted_at:
            self.granted_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc).isoformat() > self.expires_at


# Default system roles for the enhanced RBAC manager
_DEFAULT_ENHANCED_ROLES: dict[str, CustomRole] = {
    "viewer": CustomRole(
        role_id="viewer",
        name="Viewer",
        description="Read-only access to scans and data",
        permissions=[
            "scan:read", "data:read", "data:search", "asset:read",
            "engine:read", "schedule:read", "report:read",
            "monitor:read", "config:read",
        ],
        is_system=True,
    ),
    "analyst": CustomRole(
        role_id="analyst",
        name="Analyst",
        description="Can run scans, export data, and manage reports",
        permissions=[
            "scan:read", "scan:create", "scan:export",
            "data:read", "data:export", "data:search",
            "asset:read", "asset:tag",
            "engine:read", "schedule:read",
            "report:read", "report:create", "report:export",
            "monitor:read", "monitor:check",
            "stix:export", "sarif:export",
            "config:read", "notification:read",
        ],
        inherits_from="viewer",
        is_system=True,
    ),
    "operator": CustomRole(
        role_id="operator",
        name="Operator",
        description="Full scan and asset management, schedule control",
        permissions=[
            "scan:read", "scan:create", "scan:update", "scan:delete",
            "scan:abort", "scan:export", "scan:schedule",
            "data:read", "data:export", "data:delete", "data:search",
            "asset:read", "asset:create", "asset:update", "asset:delete",
            "asset:tag", "asset:link",
            "engine:read", "engine:create", "engine:update", "engine:delete",
            "schedule:read", "schedule:create", "schedule:update",
            "schedule:delete", "schedule:trigger",
            "report:read", "report:create", "report:export", "report:delete",
            "monitor:read", "monitor:create", "monitor:update",
            "monitor:delete", "monitor:check",
            "stix:export", "sarif:export",
            "asm:read", "asm:ingest", "asm:manage",
            "config:read", "notification:read", "notification:configure",
            "api_key:read", "api_key:create",
        ],
        inherits_from="analyst",
        is_system=True,
    ),
    "admin": CustomRole(
        role_id="admin",
        name="Administrator",
        description="Full system access including user and tenant management",
        permissions=list(ALL_PERMISSIONS),
        inherits_from="operator",
        is_system=True,
    ),
}


class EnhancedRBACManager:
    """Manages custom roles, bindings, and tenant-scoped permissions.

    Extends the base RBAC system with Redis-backed custom role definitions,
    tenant-scoped permission assignments, and resource-level access control.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._roles: dict[str, CustomRole] = dict(_DEFAULT_ENHANCED_ROLES)
        self._bindings: dict[str, UserRoleBinding] = {}
        self._user_bindings: dict[str, list[str]] = {}  # user_id → [binding_ids]
        self._prefix = "sf:rbac2"

    # ----- Role management -----

    def create_role(
        self,
        name: str,
        permissions: list[str],
        description: str = "",
        inherits_from: str | None = None,
        tenant_id: str = "default",
        created_by: str = "",
    ) -> CustomRole:
        """Create a custom role."""
        role_id = name.lower().replace(" ", "_")
        if role_id in self._roles:
            raise ValueError(f"Role '{role_id}' already exists")

        invalid = [p for p in permissions if p not in ALL_PERMISSIONS]
        if invalid:
            raise ValueError(f"Invalid permissions: {invalid}")

        if inherits_from and inherits_from not in self._roles:
            raise ValueError(f"Parent role '{inherits_from}' not found")

        role = CustomRole(
            role_id=role_id,
            name=name,
            description=description,
            permissions=permissions,
            inherits_from=inherits_from,
            tenant_id=tenant_id,
            created_by=created_by,
        )
        self._roles[role_id] = role

        if self._redis:
            try:
                self._redis.hset(
                    f"{self._prefix}:roles",
                    role_id,
                    json.dumps(role.to_dict()),
                )
            except Exception as e:
                log.warning("Redis RBAC storage failed: %s", e)

        log.info("Created custom role: %s with %d permissions", name, len(permissions))
        return role

    def get_role(self, role_id: str) -> CustomRole | None:
        return self._roles.get(role_id)

    def list_roles(self, include_system: bool = True) -> list[CustomRole]:
        roles = list(self._roles.values())
        if not include_system:
            roles = [r for r in roles if not r.is_system]
        return roles

    def update_role(
        self,
        role_id: str,
        permissions: list[str] | None = None,
        description: str | None = None,
    ) -> CustomRole | None:
        role = self._roles.get(role_id)
        if not role:
            return None
        if role.is_system:
            raise ValueError("Cannot modify system roles")
        if permissions is not None:
            invalid = [p for p in permissions if p not in ALL_PERMISSIONS]
            if invalid:
                raise ValueError(f"Invalid permissions: {invalid}")
            role.permissions = permissions
        if description is not None:
            role.description = description
        return role

    def delete_role(self, role_id: str) -> bool:
        role = self._roles.get(role_id)
        if not role:
            return False
        if role.is_system:
            raise ValueError("Cannot delete system roles")
        del self._roles[role_id]
        return True

    def get_effective_permissions(self, role_id: str) -> set[str]:
        """Get all permissions including inherited ones."""
        role = self._roles.get(role_id)
        if not role:
            return set()

        perms = set(role.permissions)
        visited = {role_id}
        parent_id = role.inherits_from
        while parent_id and parent_id not in visited:
            visited.add(parent_id)
            parent = self._roles.get(parent_id)
            if parent:
                perms.update(parent.permissions)
                parent_id = parent.inherits_from
            else:
                break

        return perms

    # ----- Role bindings -----

    def assign_role(
        self,
        user_id: str,
        role_id: str,
        tenant_id: str = "default",
        resource_scope: str | None = None,
        granted_by: str = "",
        expires_at: str | None = None,
    ) -> UserRoleBinding:
        """Assign a role to a user within a tenant scope."""
        if role_id not in self._roles:
            raise ValueError(f"Role '{role_id}' not found")

        binding_id = str(uuid.uuid4())[:12]
        binding = UserRoleBinding(
            binding_id=binding_id,
            user_id=user_id,
            role_id=role_id,
            tenant_id=tenant_id,
            resource_scope=resource_scope,
            granted_by=granted_by,
            expires_at=expires_at,
        )

        self._bindings[binding_id] = binding
        if user_id not in self._user_bindings:
            self._user_bindings[user_id] = []
        self._user_bindings[user_id].append(binding_id)

        log.info(
            "Assigned role %s to user %s in tenant %s",
            role_id, user_id, tenant_id,
        )
        return binding

    def revoke_binding(self, binding_id: str) -> bool:
        binding = self._bindings.pop(binding_id, None)
        if not binding:
            return False
        if binding.user_id in self._user_bindings:
            self._user_bindings[binding.user_id] = [
                b for b in self._user_bindings[binding.user_id] if b != binding_id
            ]
        return True

    def get_user_roles(
        self, user_id: str, tenant_id: str = "default"
    ) -> list[UserRoleBinding]:
        """Get all role bindings for a user in a specific tenant."""
        binding_ids = self._user_bindings.get(user_id, [])
        bindings = []
        for bid in binding_ids:
            b = self._bindings.get(bid)
            if b and b.tenant_id == tenant_id and not b.is_expired():
                bindings.append(b)
        return bindings

    def check_permission(
        self,
        user_id: str,
        permission: str,
        tenant_id: str = "default",
        resource: str | None = None,
    ) -> bool:
        """Check if a user has a specific permission in a tenant."""
        bindings = self.get_user_roles(user_id, tenant_id)

        for binding in bindings:
            if resource and binding.resource_scope:
                if binding.resource_scope != resource:
                    continue

            perms = self.get_effective_permissions(binding.role_id)
            if permission in perms:
                return True

        return False

    def get_user_permissions(
        self, user_id: str, tenant_id: str = "default"
    ) -> set[str]:
        """Get all effective permissions for a user in a tenant."""
        bindings = self.get_user_roles(user_id, tenant_id)
        all_perms: set[str] = set()
        for binding in bindings:
            all_perms.update(self.get_effective_permissions(binding.role_id))
        return all_perms
