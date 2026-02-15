# -*- coding: utf-8 -*-
"""
API Key management for SpiderFoot.

Provides CRUD operations for API keys with role assignment, expiration,
and scope restrictions.  Keys are stored in Redis with HMAC-SHA256
hashing for security.

Each API key record:
  - key_id:      Short unique identifier (shown to user)
  - key_hash:    HMAC-SHA256 of the full key (for auth lookup)
  - name:        Human-friendly label
  - role:        RBAC role (viewer/analyst/operator/admin)
  - scopes:      Optional fine-grained permission overrides
  - created_at:  Unix timestamp
  - expires_at:  Optional expiry timestamp (0 = never)
  - last_used_at: Last authentication timestamp
  - enabled:     Active/revoked flag

Usage::

    from spiderfoot.api_keys import APIKeyManager

    mgr = APIKeyManager()
    key_id, full_key = mgr.create_key("My Scanner", role="analyst")
    user_ctx = mgr.authenticate(full_key)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("spiderfoot.api_keys")

# Secret used for HMAC hashing of API keys
_HMAC_SECRET = os.environ.get("SF_API_KEY_SECRET", "spiderfoot-api-key-secret").encode()

# Key prefix for easy identification
KEY_PREFIX = "sfk_"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class APIKeyRecord:
    """Stored API key metadata."""
    key_id: str
    key_hash: str
    name: str
    role: str = "viewer"
    scopes: list[str] = field(default_factory=list)
    created_at: float = 0.0
    expires_at: float = 0.0  # 0 = never expires
    last_used_at: float = 0.0
    enabled: bool = True
    created_by: str = ""
    description: str = ""

    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if self.expires_at == 0:
            return False
        return time.time() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the key is usable (enabled and not expired)."""
        return self.enabled and not self.is_expired()

    def to_dict(self, include_hash: bool = False) -> dict[str, Any]:
        """Serialize to dict (excludes hash by default for safety)."""
        d = {
            "key_id": self.key_id,
            "name": self.name,
            "role": self.role,
            "scopes": self.scopes,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_used_at": self.last_used_at,
            "enabled": self.enabled,
            "created_by": self.created_by,
            "description": self.description,
        }
        if include_hash:
            d["key_hash"] = self.key_hash
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> APIKeyRecord:
        """Deserialize from dict."""
        return cls(
            key_id=data["key_id"],
            key_hash=data.get("key_hash", ""),
            name=data.get("name", ""),
            role=data.get("role", "viewer"),
            scopes=data.get("scopes", []),
            created_at=data.get("created_at", 0),
            expires_at=data.get("expires_at", 0),
            last_used_at=data.get("last_used_at", 0),
            enabled=data.get("enabled", True),
            created_by=data.get("created_by", ""),
            description=data.get("description", ""),
        )


# ---------------------------------------------------------------------------
# Key hashing
# ---------------------------------------------------------------------------

def _hash_key(full_key: str) -> str:
    """HMAC-SHA256 hash of an API key for secure storage."""
    return hmac.new(_HMAC_SECRET, full_key.encode(), hashlib.sha256).hexdigest()


def _generate_key() -> tuple[str, str]:
    """Generate a new API key.

    Returns:
        (key_id, full_key) — key_id is the first 12 chars, full_key
        includes the prefix and 48 random hex chars.
    """
    random_part = secrets.token_hex(24)  # 48 hex chars
    full_key = f"{KEY_PREFIX}{random_part}"
    key_id = full_key[:16]  # sfk_ + first 12 hex chars
    return key_id, full_key


# ---------------------------------------------------------------------------
# Redis-backed key store
# ---------------------------------------------------------------------------

def _get_redis():
    """Get Redis connection."""
    import redis as redis_lib
    redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
    return redis_lib.from_url(redis_url)


def _key_record_key(key_id: str) -> str:
    return f"sf:apikey:{key_id}"


def _key_hash_index_key() -> str:
    return "sf:apikeys:hash_index"


def _key_list_key() -> str:
    return "sf:apikeys:list"


# ---------------------------------------------------------------------------
# API Key Manager
# ---------------------------------------------------------------------------

class APIKeyManager:
    """Manages API key lifecycle — create, list, authenticate, revoke."""

    def __init__(self):
        self._redis = None

    @property
    def redis(self):
        if self._redis is None:
            self._redis = _get_redis()
        return self._redis

    def create_key(
        self,
        name: str,
        role: str = "viewer",
        scopes: list[str] | None = None,
        expires_in_days: int = 0,
        created_by: str = "",
        description: str = "",
    ) -> tuple[str, str]:
        """Create a new API key.

        Args:
            name: Human-friendly name for the key.
            role: RBAC role to assign.
            scopes: Optional fine-grained permission list (overrides role).
            expires_in_days: Days until expiry (0 = never).
            created_by: Username of creator.
            description: Optional description.

        Returns:
            (key_id, full_key) — The full_key is only returned once!
        """
        from spiderfoot.rbac import parse_role
        parse_role(role)  # Validate role

        key_id, full_key = _generate_key()
        key_hash = _hash_key(full_key)
        now = time.time()

        record = APIKeyRecord(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            role=role,
            scopes=scopes or [],
            created_at=now,
            expires_at=now + (expires_in_days * 86400) if expires_in_days > 0 else 0,
            last_used_at=0,
            enabled=True,
            created_by=created_by,
            description=description,
        )

        # Store the record
        self.redis.set(
            _key_record_key(key_id),
            json.dumps(record.to_dict(include_hash=True)),
            ex=86400 * 365 * 5,  # 5 year TTL as safety net
        )
        # Hash → key_id index for O(1) auth lookups
        self.redis.hset(_key_hash_index_key(), key_hash, key_id)
        # Ordered set for listing
        self.redis.zadd(_key_list_key(), {key_id: now})

        log.info("Created API key '%s' (role=%s) for '%s'", key_id, role, name)
        return key_id, full_key

    def authenticate(self, full_key: str) -> APIKeyRecord | None:
        """Authenticate a request using a full API key.

        Args:
            full_key: The complete API key string.

        Returns:
            APIKeyRecord if valid, None if not found/invalid/expired.
        """
        key_hash = _hash_key(full_key)
        key_id_raw = self.redis.hget(_key_hash_index_key(), key_hash)
        if not key_id_raw:
            return None

        key_id = key_id_raw.decode("utf-8") if isinstance(key_id_raw, bytes) else key_id_raw
        raw = self.redis.get(_key_record_key(key_id))
        if not raw:
            return None

        record = APIKeyRecord.from_dict(json.loads(raw))

        if not record.is_valid():
            return None

        # Update last_used_at
        record.last_used_at = time.time()
        self.redis.set(
            _key_record_key(key_id),
            json.dumps(record.to_dict(include_hash=True)),
            keepttl=True,
        )

        return record

    def get_key(self, key_id: str) -> APIKeyRecord | None:
        """Get a key record by ID."""
        raw = self.redis.get(_key_record_key(key_id))
        if not raw:
            return None
        return APIKeyRecord.from_dict(json.loads(raw))

    def list_keys(self) -> list[APIKeyRecord]:
        """List all API keys (without hashes)."""
        key_ids = self.redis.zrangebyscore(_key_list_key(), "-inf", "+inf")
        records = []
        for kid in key_ids:
            kid_str = kid.decode("utf-8") if isinstance(kid, bytes) else kid
            raw = self.redis.get(_key_record_key(kid_str))
            if raw:
                records.append(APIKeyRecord.from_dict(json.loads(raw)))
        return records

    def update_key(
        self,
        key_id: str,
        name: str | None = None,
        role: str | None = None,
        scopes: list[str] | None = None,
        enabled: bool | None = None,
        description: str | None = None,
    ) -> APIKeyRecord | None:
        """Update a key's metadata."""
        record = self.get_key(key_id)
        if not record:
            return None

        if name is not None:
            record.name = name
        if role is not None:
            from spiderfoot.rbac import parse_role
            parse_role(role)
            record.role = role
        if scopes is not None:
            record.scopes = scopes
        if enabled is not None:
            record.enabled = enabled
        if description is not None:
            record.description = description

        self.redis.set(
            _key_record_key(key_id),
            json.dumps(record.to_dict(include_hash=True)),
            keepttl=True,
        )
        log.info("Updated API key '%s'", key_id)
        return record

    def revoke_key(self, key_id: str) -> bool:
        """Revoke (disable) an API key."""
        record = self.get_key(key_id)
        if not record:
            return False
        record.enabled = False
        self.redis.set(
            _key_record_key(key_id),
            json.dumps(record.to_dict(include_hash=True)),
            keepttl=True,
        )
        log.info("Revoked API key '%s'", key_id)
        return True

    def delete_key(self, key_id: str) -> bool:
        """Permanently delete an API key."""
        record = self.get_key(key_id)
        if not record:
            return False
        self.redis.delete(_key_record_key(key_id))
        self.redis.hdel(_key_hash_index_key(), record.key_hash)
        self.redis.zrem(_key_list_key(), key_id)
        log.info("Deleted API key '%s'", key_id)
        return True


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_manager: APIKeyManager | None = None


def get_api_key_manager() -> APIKeyManager:
    """Get/create the singleton APIKeyManager."""
    global _manager
    if _manager is None:
        _manager = APIKeyManager()
    return _manager
