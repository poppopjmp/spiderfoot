"""Enhanced RBAC with custom roles and tenant-scoped permissions.

Extends the base RBAC system (v5.4.8) with:
- Custom role definitions stored in Redis
- Tenant-scoped permission assignments
- Resource-level permissions (per-scan, per-asset access)
- Permission delegation and inheritance
- Session-based role context
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("spiderfoot.rbac_enhanced")


# Built-in permissions (comprehensive list)
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
    """A custom role definition."""
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


# Default system roles
_DEFAULT_ROLES: dict[str, CustomRole] = {
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
    """Manages custom roles, bindings, and tenant-scoped permissions."""

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._roles: dict[str, CustomRole] = dict(_DEFAULT_ROLES)
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

        # Validate permissions
        invalid = [p for p in permissions if p not in ALL_PERMISSIONS]
        if invalid:
            raise ValueError(f"Invalid permissions: {invalid}")

        # Validate inheritance
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
                logger.warning("Redis RBAC storage failed: %s", e)

        logger.info("Created custom role: %s with %d permissions", name, len(permissions))
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
        # Walk inheritance chain
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

        logger.info(
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
            # Check resource scope if specified
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
