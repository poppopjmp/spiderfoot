"""Multi-tenancy support for SpiderFoot.

Provides tenant isolation with:
- Tenant registry with Redis-backed storage
- Data namespace isolation (scans, assets, configs per tenant)
- Tenant-scoped API middleware
- Resource quotas and limits per tenant
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("spiderfoot.multi_tenancy")


class TenantPlan(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# Default quotas per plan
_PLAN_QUOTAS: dict[str, dict[str, int]] = {
    "free": {
        "max_scans": 10,
        "max_concurrent_scans": 1,
        "max_modules": 20,
        "max_assets": 1000,
        "max_schedules": 2,
        "max_api_keys": 2,
        "max_users": 1,
        "retention_days": 30,
    },
    "starter": {
        "max_scans": 100,
        "max_concurrent_scans": 3,
        "max_modules": 50,
        "max_assets": 10000,
        "max_schedules": 10,
        "max_api_keys": 5,
        "max_users": 5,
        "retention_days": 90,
    },
    "professional": {
        "max_scans": 1000,
        "max_concurrent_scans": 10,
        "max_modules": -1,  # unlimited
        "max_assets": 100000,
        "max_schedules": 50,
        "max_api_keys": 20,
        "max_users": 25,
        "retention_days": 365,
    },
    "enterprise": {
        "max_scans": -1,
        "max_concurrent_scans": -1,
        "max_modules": -1,
        "max_assets": -1,
        "max_schedules": -1,
        "max_api_keys": -1,
        "max_users": -1,
        "retention_days": -1,  # unlimited
    },
}


@dataclass
class Tenant:
    """Represents a tenant in the multi-tenant system."""
    tenant_id: str
    name: str
    slug: str
    plan: TenantPlan = TenantPlan.FREE
    created_at: str = ""
    updated_at: str = ""
    enabled: bool = True
    owner_email: str = ""
    quotas: dict[str, int] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.quotas:
            self.quotas = dict(_PLAN_QUOTAS.get(self.plan.value, _PLAN_QUOTAS["free"]))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["plan"] = self.plan.value
        return d

    def check_quota(self, resource: str, current_count: int) -> bool:
        """Check if a quota limit has been reached. Returns True if OK."""
        limit = self.quotas.get(resource, -1)
        if limit == -1:
            return True  # unlimited
        return current_count < limit

    def get_namespace(self) -> str:
        """Get the data namespace prefix for this tenant."""
        return f"t:{self.tenant_id}"


class TenantManager:
    """Manages tenant CRUD with Redis-backed storage."""

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._tenants: dict[str, Tenant] = {}
        self._slug_index: dict[str, str] = {}  # slug → tenant_id
        self._prefix = "sf:tenant"

        # Create default tenant
        default = Tenant(
            tenant_id="default",
            name="Default",
            slug="default",
            plan=TenantPlan.ENTERPRISE,
            owner_email="admin@localhost",
        )
        self._tenants["default"] = default
        self._slug_index["default"] = "default"

    def create_tenant(
        self,
        name: str,
        slug: str,
        plan: TenantPlan = TenantPlan.FREE,
        owner_email: str = "",
        custom_quotas: dict[str, int] | None = None,
    ) -> Tenant:
        """Create a new tenant."""
        # Validate slug
        slug = slug.lower().strip().replace(" ", "-")
        if slug in self._slug_index:
            raise ValueError(f"Tenant slug '{slug}' already exists")

        tenant_id = str(uuid.uuid4())[:12]
        quotas = dict(_PLAN_QUOTAS.get(plan.value, _PLAN_QUOTAS["free"]))
        if custom_quotas:
            quotas.update(custom_quotas)

        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            plan=plan,
            owner_email=owner_email,
            quotas=quotas,
        )

        self._tenants[tenant_id] = tenant
        self._slug_index[slug] = tenant_id

        # Persist
        if self._redis:
            try:
                self._redis.hset(
                    f"{self._prefix}:{tenant_id}",
                    mapping={"data": json.dumps(tenant.to_dict())},
                )
                self._redis.sadd(f"{self._prefix}:index", tenant_id)
                self._redis.hset(f"{self._prefix}:slugs", slug, tenant_id)
            except Exception as e:
                logger.warning("Redis tenant storage failed: %s", e)

        logger.info("Created tenant: %s (%s) plan=%s", name, tenant_id, plan.value)
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        return self._tenants.get(tenant_id)

    def get_by_slug(self, slug: str) -> Tenant | None:
        tid = self._slug_index.get(slug)
        if tid:
            return self._tenants.get(tid)
        return None

    def list_tenants(self, include_disabled: bool = False) -> list[Tenant]:
        tenants = list(self._tenants.values())
        if not include_disabled:
            tenants = [t for t in tenants if t.enabled]
        return tenants

    def update_tenant(
        self,
        tenant_id: str,
        name: str | None = None,
        plan: TenantPlan | None = None,
        enabled: bool | None = None,
        quotas: dict[str, int] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> Tenant | None:
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return None

        if name is not None:
            tenant.name = name
        if plan is not None:
            tenant.plan = plan
            # Reset quotas to plan defaults, then apply custom
            tenant.quotas = dict(_PLAN_QUOTAS.get(plan.value, _PLAN_QUOTAS["free"]))
        if enabled is not None:
            tenant.enabled = enabled
        if quotas:
            tenant.quotas.update(quotas)
        if settings:
            tenant.settings.update(settings)

        tenant.updated_at = datetime.now(timezone.utc).isoformat()

        # Persist
        if self._redis:
            try:
                self._redis.hset(
                    f"{self._prefix}:{tenant_id}",
                    mapping={"data": json.dumps(tenant.to_dict())},
                )
            except Exception:
                pass

        return tenant

    def delete_tenant(self, tenant_id: str) -> bool:
        if tenant_id == "default":
            raise ValueError("Cannot delete default tenant")
        tenant = self._tenants.pop(tenant_id, None)
        if not tenant:
            return False
        self._slug_index.pop(tenant.slug, None)
        if self._redis:
            try:
                self._redis.delete(f"{self._prefix}:{tenant_id}")
                self._redis.srem(f"{self._prefix}:index", tenant_id)
                self._redis.hdel(f"{self._prefix}:slugs", tenant.slug)
            except Exception:
                pass
        logger.info("Deleted tenant: %s (%s)", tenant.name, tenant_id)
        return True

    def get_usage(self, tenant_id: str) -> dict[str, Any]:
        """Get current resource usage for a tenant."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return {}
        # In production, these would query actual data stores
        return {
            "tenant_id": tenant_id,
            "plan": tenant.plan.value,
            "quotas": dict(tenant.quotas),
            "usage": {
                "scans": 0,
                "concurrent_scans": 0,
                "assets": 0,
                "schedules": 0,
                "api_keys": 0,
                "users": 0,
            },
        }


def namespace_key(tenant_id: str, key: str) -> str:
    """Create a tenant-namespaced key for data isolation."""
    return f"t:{tenant_id}:{key}"
