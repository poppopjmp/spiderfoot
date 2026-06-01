"""In-memory fake Redis for unit tests.

A minimal, dependency-free stand-in for a Redis client supporting the string,
hash, sorted-set, and pipeline operations used across SpiderFoot's Redis-backed
components (API keys, schedules, etc.). Lets those code paths be tested without
a running Redis server.

Only the operations exercised by the code under test are implemented; extend as
needed rather than reaching for a heavier dependency.
"""
from __future__ import annotations


class FakeRedis:
    """Minimal fake Redis with hash, sorted set, string, and pipeline support."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._zsets: dict[str, dict[str, float]] = {}

    @staticmethod
    def _s(value):
        return value if isinstance(value, str) else value.decode()

    # -- strings -----------------------------------------------------------
    def set(self, key, value, ex=None, keepttl=False):
        self._store[key] = self._s(value)

    def get(self, key):
        return self._store.get(key)

    def exists(self, *keys):
        return sum(1 for k in keys if k in self._store
                   or k in self._hashes or k in self._zsets)

    def expire(self, key, seconds):
        return True  # TTL is a no-op in the fake

    def delete(self, *keys):
        for k in keys:
            self._store.pop(k, None)
            self._hashes.pop(k, None)
            self._zsets.pop(k, None)

    # -- hashes ------------------------------------------------------------
    def hset(self, name, key=None, value=None, mapping=None):
        h = self._hashes.setdefault(name, {})
        if mapping:
            h.update(mapping)
        if key is not None:
            h[key] = value

    def hget(self, name, key):
        return self._hashes.get(name, {}).get(key)

    def hgetall(self, name):
        return dict(self._hashes.get(name, {}))

    def hdel(self, name, *keys):
        h = self._hashes.get(name, {})
        for k in keys:
            h.pop(k, None)

    # -- sorted sets -------------------------------------------------------
    def zadd(self, name, mapping):
        self._zsets.setdefault(name, {}).update(mapping)

    def zrange(self, name, start, end):
        members = sorted(self._zsets.get(name, {}).items(), key=lambda x: x[1])
        keys = [m for m, _ in members]
        if end == -1:
            return keys[start:]
        return keys[start:end + 1]

    def zrangebyscore(self, name, _min, _max):
        return list(self._zsets.get(name, {}).keys())

    def zrem(self, name, *members):
        z = self._zsets.get(name, {})
        for m in members:
            z.pop(m, None)

    def zcard(self, name):
        return len(self._zsets.get(name, {}))

    # -- pipeline ----------------------------------------------------------
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

    def delete(self, *keys):
        self._ops.append(("delete", *keys))
        return self

    def zadd(self, name, mapping):
        self._ops.append(("zadd", name, mapping))
        return self

    def zrem(self, name, *members):
        self._ops.append(("zrem", name, *members))
        return self

    def execute(self):
        for op in self._ops:
            getattr(self._redis, op[0])(*op[1:])
        self._ops.clear()
