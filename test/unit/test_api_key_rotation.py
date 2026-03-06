"""
Tests for Cycle 49 — API Key Rotation Without Restart

Validates that:
1. APIKeyManager.rotate_key() generates a new secret
2. The old key is immediately invalidated
3. The new key authenticates successfully
4. Key metadata (name, role, scopes) is preserved across rotation
5. Rotating a non-existent key returns None
6. The operation is atomic (uses Redis pipeline)
7. APIKeyRecord data model works correctly

Uses a fake Redis (in-memory dict) to avoid requiring a running Redis server.
"""

from __future__ import annotations

import json
import time
import pytest
from unittest.mock import MagicMock, patch

from spiderfoot.auth.api_keys import (
    APIKeyManager,
    APIKeyRecord,
    _hash_key,
    _generate_key,
    KEY_PREFIX,
)


# ---------------------------------------------------------------------------
# Fake Redis — in-memory dict with pipeline support
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal fake Redis with hash, sorted set, string, and pipeline support."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._zsets: dict[str, dict[str, float]] = {}

    def set(self, key, value, ex=None, keepttl=False):
        self._store[key] = value if isinstance(value, str) else value.decode()

    def get(self, key):
        return self._store.get(key)

    def delete(self, *keys):
        for k in keys:
            self._store.pop(k, None)

    def hset(self, name, key, value):
        self._hashes.setdefault(name, {})[key] = value

    def hget(self, name, key):
        return self._hashes.get(name, {}).get(key)

    def hdel(self, name, *keys):
        h = self._hashes.get(name, {})
        for k in keys:
            h.pop(k, None)

    def zadd(self, name, mapping):
        self._zsets.setdefault(name, {}).update(mapping)

    def zrangebyscore(self, name, _min, _max):
        return list(self._zsets.get(name, {}).keys())

    def zrem(self, name, *members):
        z = self._zsets.get(name, {})
        for m in members:
            z.pop(m, None)

    def pipeline(self, transaction=True):
        return FakePipeline(self)


class FakePipeline:
    """Batches commands and executes them in sequence."""

    def __init__(self, redis: FakeRedis):
        self._redis = redis
        self._ops: list[tuple] = []

    def hset(self, name, key, value):
        self._ops.append(("hset", name, key, value))
        return self

    def hdel(self, name, *keys):
        self._ops.append(("hdel", name, *keys))
        return self

    def set(self, key, value, ex=None, keepttl=False):
        self._ops.append(("set", key, value))
        return self

    def execute(self):
        for op in self._ops:
            getattr(self._redis, op[0])(*op[1:])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def mgr(fake_redis):
    m = APIKeyManager()
    m._redis = fake_redis
    return m


def _create_key_in_mgr(mgr):
    """Helper: create a key and return (key_id, full_key)."""
    with patch("spiderfoot.auth.api_keys.APIKeyManager.redis", new_callable=lambda: property(lambda self: self._redis)):
        # rbac.parse_role just validates role name — mock it
        with patch("spiderfoot.auth.rbac.parse_role", return_value="analyst"):
            return mgr.create_key("Test Key", role="analyst", scopes=["read", "scan"])


# ---------------------------------------------------------------------------
# APIKeyRecord data model
# ---------------------------------------------------------------------------

class TestAPIKeyRecord:
    """Tests for the APIKeyRecord dataclass."""

    def test_is_valid_when_enabled(self):
        r = APIKeyRecord(key_id="k1", key_hash="h1", name="t", enabled=True)
        assert r.is_valid()

    def test_not_valid_when_disabled(self):
        r = APIKeyRecord(key_id="k1", key_hash="h1", name="t", enabled=False)
        assert not r.is_valid()

    def test_not_valid_when_expired(self):
        r = APIKeyRecord(
            key_id="k1", key_hash="h1", name="t",
            expires_at=time.time() - 100,
        )
        assert not r.is_valid()

    def test_valid_when_not_expired(self):
        r = APIKeyRecord(
            key_id="k1", key_hash="h1", name="t",
            expires_at=time.time() + 10000,
        )
        assert r.is_valid()

    def test_to_dict_excludes_hash(self):
        r = APIKeyRecord(key_id="k1", key_hash="secret", name="t")
        d = r.to_dict()
        assert "key_hash" not in d
        assert d["key_id"] == "k1"

    def test_to_dict_includes_hash(self):
        r = APIKeyRecord(key_id="k1", key_hash="secret", name="t")
        d = r.to_dict(include_hash=True)
        assert d["key_hash"] == "secret"

    def test_roundtrip(self):
        r = APIKeyRecord(
            key_id="k1", key_hash="h1", name="n",
            role="admin", scopes=["all"],
        )
        d = r.to_dict(include_hash=True)
        r2 = APIKeyRecord.from_dict(d)
        assert r2.key_id == r.key_id
        assert r2.key_hash == r.key_hash
        assert r2.role == r.role
        assert r2.scopes == r.scopes


# ---------------------------------------------------------------------------
# Key generation & hashing
# ---------------------------------------------------------------------------

class TestKeyGeneration:
    """Tests for key generation and hashing."""

    def test_key_has_prefix(self):
        key_id, full_key = _generate_key()
        assert full_key.startswith(KEY_PREFIX)

    def test_key_id_is_prefix_of_key(self):
        key_id, full_key = _generate_key()
        assert full_key.startswith(key_id)

    def test_keys_are_unique(self):
        keys = {_generate_key()[1] for _ in range(100)}
        assert len(keys) == 100

    def test_hash_deterministic(self):
        assert _hash_key("test123") == _hash_key("test123")

    def test_hash_different_for_different_keys(self):
        assert _hash_key("key_a") != _hash_key("key_b")


# ---------------------------------------------------------------------------
# Create + Authenticate (prerequisite for rotation testing)
# ---------------------------------------------------------------------------

class TestCreateAndAuth:
    """Verify basic create/authenticate works with fake Redis."""

    def test_create_returns_key_id_and_full_key(self, mgr):
        key_id, full_key = _create_key_in_mgr(mgr)
        assert key_id.startswith(KEY_PREFIX)
        assert full_key.startswith(KEY_PREFIX)
        assert len(full_key) == 52  # sfk_ + 48 hex

    def test_authenticate_with_created_key(self, mgr):
        key_id, full_key = _create_key_in_mgr(mgr)
        record = mgr.authenticate(full_key)
        assert record is not None
        assert record.key_id == key_id
        assert record.name == "Test Key"

    def test_authenticate_with_wrong_key(self, mgr):
        _create_key_in_mgr(mgr)
        assert mgr.authenticate("sfk_wrong_key_00000000000000000000000000") is None


# ---------------------------------------------------------------------------
# Key rotation
# ---------------------------------------------------------------------------

class TestRotateKey:
    """Core rotation tests."""

    def test_rotate_returns_new_key(self, mgr):
        key_id, full_key = _create_key_in_mgr(mgr)
        result = mgr.rotate_key(key_id)
        assert result is not None
        new_key_id, new_full_key = result
        assert new_key_id == key_id  # key_id is preserved
        assert new_full_key != full_key  # but the secret is different
        assert new_full_key.startswith(KEY_PREFIX)

    def test_old_key_invalidated_after_rotation(self, mgr):
        key_id, old_full_key = _create_key_in_mgr(mgr)
        mgr.rotate_key(key_id)
        # Old key should no longer authenticate
        assert mgr.authenticate(old_full_key) is None

    def test_new_key_authenticates_after_rotation(self, mgr):
        key_id, old_full_key = _create_key_in_mgr(mgr)
        _, new_full_key = mgr.rotate_key(key_id)
        record = mgr.authenticate(new_full_key)
        assert record is not None
        assert record.key_id == key_id

    def test_metadata_preserved_after_rotation(self, mgr):
        key_id, _ = _create_key_in_mgr(mgr)
        mgr.rotate_key(key_id)
        record = mgr.get_key(key_id)
        assert record.name == "Test Key"
        assert record.role == "analyst"
        assert record.scopes == ["read", "scan"]

    def test_rotate_nonexistent_key(self, mgr):
        assert mgr.rotate_key("sfk_nonexistent_") is None

    def test_double_rotation(self, mgr):
        """Rotating twice should work — each rotation invalidates the previous key."""
        key_id, key1 = _create_key_in_mgr(mgr)
        _, key2 = mgr.rotate_key(key_id)
        _, key3 = mgr.rotate_key(key_id)

        assert mgr.authenticate(key1) is None
        assert mgr.authenticate(key2) is None
        record = mgr.authenticate(key3)
        assert record is not None
        assert record.key_id == key_id

    def test_rotation_resets_last_used(self, mgr):
        key_id, full_key = _create_key_in_mgr(mgr)
        # Simulate usage
        mgr.authenticate(full_key)
        record_before = mgr.get_key(key_id)
        assert record_before.last_used_at > 0

        # Rotate
        mgr.rotate_key(key_id)
        record_after = mgr.get_key(key_id)
        assert record_after.last_used_at == 0  # Reset

    def test_rotation_uses_pipeline(self, mgr, fake_redis):
        """Verify rotation goes through a Redis pipeline for atomicity."""
        key_id, _ = _create_key_in_mgr(mgr)

        original_pipeline = fake_redis.pipeline
        pipeline_called = False

        def tracking_pipeline(**kwargs):
            nonlocal pipeline_called
            pipeline_called = True
            return original_pipeline(**kwargs)

        fake_redis.pipeline = tracking_pipeline
        mgr.rotate_key(key_id)
        assert pipeline_called


# ---------------------------------------------------------------------------
# Revoke + Delete
# ---------------------------------------------------------------------------

class TestRevokeAndDelete:
    """Verify revoke/delete still work alongside rotation."""

    def test_revoke_prevents_auth(self, mgr):
        key_id, full_key = _create_key_in_mgr(mgr)
        mgr.revoke_key(key_id)
        assert mgr.authenticate(full_key) is None

    def test_delete_removes_key(self, mgr):
        key_id, full_key = _create_key_in_mgr(mgr)
        assert mgr.delete_key(key_id)
        assert mgr.get_key(key_id) is None
        assert mgr.authenticate(full_key) is None

    def test_rotate_then_delete(self, mgr):
        key_id, _ = _create_key_in_mgr(mgr)
        _, new_key = mgr.rotate_key(key_id)
        mgr.delete_key(key_id)
        assert mgr.authenticate(new_key) is None
