"""In-memory (+ optional Redis) rate-limiter – lightweight stub.

Provides the ``RateLimiter`` class expected by ``security_middleware.py``.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class RateLimiter:
    """Token-bucket rate-limiter with optional Redis backend."""

    # requests-per-minute limits per tier
    _TIER_LIMITS: dict[str, int] = {
        "web": 120,
        "api": 60,
    }

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
    ) -> None:
        self.redis: Any = None
        try:
            import redis as _redis  # type: ignore[import-untyped]

            self.redis = _redis.Redis(
                host=redis_host, port=redis_port, db=redis_db,
                socket_connect_timeout=2, decode_responses=True,
            )
            self.redis.ping()
        except Exception:
            self.redis = None

        # fallback in-memory store: {client_id: [(timestamp, …), …]}
        self._memory: dict[str, list[float]] = defaultdict(list)

    # ------------------------------------------------------------------ #
    def _check_memory_limit(
        self, client_id: str, tier: str = "web",
    ) -> tuple[bool, dict[str, Any]]:
        limit = self._TIER_LIMITS.get(tier, 60)
        now = time.monotonic()
        window = 60.0  # seconds
        hits = self._memory[client_id]
        # prune old
        hits[:] = [t for t in hits if now - t < window]
        allowed = len(hits) < limit
        if allowed:
            hits.append(now)
        return allowed, {
            "limit": limit,
            "remaining": max(0, limit - len(hits)),
            "reset": int(now + window),
        }

    def _check_redis_limit(
        self, client_id: str, tier: str = "web",
    ) -> tuple[bool, dict[str, Any]]:
        if self.redis is None:
            return self._check_memory_limit(client_id, tier)
        try:
            limit = self._TIER_LIMITS.get(tier, 60)
            key = f"rl:{tier}:{client_id}"
            count = self.redis.incr(key)
            if count == 1:
                self.redis.expire(key, 60)
            ttl = self.redis.ttl(key)
            allowed = count <= limit
            return allowed, {
                "limit": limit,
                "remaining": max(0, limit - count),
                "reset": int(time.time()) + max(ttl, 0),
            }
        except Exception:
            return self._check_memory_limit(client_id, tier)
