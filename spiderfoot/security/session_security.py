"""Session security manager.

Provides the ``SessionManager`` class expected by ``security_middleware.py``.
Validates that the client IP and User-Agent are consistent across a session
to detect session hijacking attempts.

Supports pluggable storage backends:
  - In-memory (default, single-process)
  - Redis-backed (multi-process / distributed)

Select via ``security.session_backend`` config key or
``SF_SESSION_BACKEND`` env var ("memory" | "redis").
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any

_log = logging.getLogger("spiderfoot.security.session_security")


# ---------------------------------------------------------------------------
# Pluggable session store interface
# ---------------------------------------------------------------------------

class SessionStore(ABC):
    """Abstract interface for session data storage."""

    @abstractmethod
    def get(self, session_id: str) -> dict[str, Any] | None:
        """Return session info dict or None."""

    @abstractmethod
    def put(self, session_id: str, info: dict[str, Any], ttl: int) -> None:
        """Store session info with a TTL (seconds)."""

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        """Delete a session. Return True if it existed."""

    @abstractmethod
    def count(self) -> int:
        """Return approximate number of active sessions."""

    def cleanup(self, idle_timeout: int, max_lifetime: int) -> int:
        """Remove expired sessions. Default no-op for stores with native TTL."""
        return 0


class MemorySessionStore(SessionStore):
    """In-process dict-backed session store (single worker only)."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def get(self, session_id: str) -> dict[str, Any] | None:
        return self._data.get(session_id)

    def put(self, session_id: str, info: dict[str, Any], ttl: int) -> None:
        self._data[session_id] = info

    def delete(self, session_id: str) -> bool:
        return self._data.pop(session_id, None) is not None

    def count(self) -> int:
        return len(self._data)

    def cleanup(self, idle_timeout: int, max_lifetime: int) -> int:
        now = time.monotonic()
        expired = [
            sid for sid, info in self._data.items()
            if (now - info["last_active"] > idle_timeout)
            or (now - info.get("created_at", now) > max_lifetime)
        ]
        for sid in expired:
            del self._data[sid]
        return len(expired)


class RedisSessionStore(SessionStore):
    """Redis-backed session store for distributed deployments.

    Each session is stored as a Redis hash at ``sf:session:<id>`` with
    a TTL equal to the absolute max lifetime.  Fields are stored as
    JSON-encoded strings to preserve types.
    """

    _PREFIX = "sf:session:"

    def __init__(self, redis_url: str | None = None) -> None:
        import redis as redis_lib
        url = redis_url or os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
        self._redis = redis_lib.from_url(url)

    def _key(self, session_id: str) -> str:
        return f"{self._PREFIX}{session_id}"

    def get(self, session_id: str) -> dict[str, Any] | None:
        raw = self._redis.get(self._key(session_id))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def put(self, session_id: str, info: dict[str, Any], ttl: int) -> None:
        self._redis.setex(self._key(session_id), ttl, json.dumps(info))

    def delete(self, session_id: str) -> bool:
        return self._redis.delete(self._key(session_id)) > 0

    def count(self) -> int:
        cursor, keys = self._redis.scan(0, match=f"{self._PREFIX}*", count=1000)
        total = len(keys)
        while cursor:
            cursor, keys = self._redis.scan(cursor, match=f"{self._PREFIX}*", count=1000)
            total += len(keys)
        return total

    # cleanup is handled by Redis TTL — no-op here


class SessionManager:
    """Track and validate user sessions with IP/UA binding."""

    # Default absolute max session lifetime: 24 hours
    DEFAULT_MAX_LIFETIME: int = 86400

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._timeout: int = int(
            self.config.get("security.session_timeout", 3600)
        )
        self._max_lifetime: int = int(
            self.config.get("security.session_max_lifetime", self.DEFAULT_MAX_LIFETIME)
        )

        # Determine backend
        backend = (
            self.config.get("security.session_backend")
            or os.environ.get("SF_SESSION_BACKEND", "memory")
        ).lower()

        if backend == "redis":
            try:
                self._store: SessionStore = RedisSessionStore()
                _log.info("Session store: Redis")
            except Exception as exc:
                _log.warning("Redis session store unavailable (%s), falling back to memory", exc)
                self._store = MemorySessionStore()
        else:
            self._store = MemorySessionStore()

        # Keep a legacy reference for tests that inspect _sessions directly
        if isinstance(self._store, MemorySessionStore):
            self._sessions = self._store._data
        else:
            self._sessions: dict[str, dict[str, Any]] = {}  # type: ignore[no-redef]

    def validate_session(
        self,
        session_id: str,
        client_ip: str,
        user_agent: str,
    ) -> bool:
        """Return True if the session is known, not expired, and client matches.

        On first call for a given *session_id* the client fingerprint
        (IP + User-Agent) is registered.  Subsequent calls reject the
        session if the fingerprint changes — a strong indicator of
        session hijacking.

        Sessions are rejected if:
        - Idle timeout exceeded (``security.session_timeout``, default 1 hour)
        - Absolute lifetime exceeded (``security.session_max_lifetime``, default 24 hours)
        - Client IP changed
        - User-Agent changed
        """
        now = time.monotonic()
        info = self._store.get(session_id)
        if info is None:
            # first time — register
            new_info = {
                "ip": client_ip,
                "ua": user_agent,
                "last_active": now,
                "created_at": now,
            }
            self._store.put(session_id, new_info, self._max_lifetime)
            return True

        # Absolute lifetime check — no session lives forever
        if now - info["created_at"] > self._max_lifetime:
            _log.info(
                "Session %s: absolute lifetime exceeded (%ds)",
                session_id[:8], self._max_lifetime,
            )
            self._store.delete(session_id)
            return False

        # Idle expiry check
        if now - info["last_active"] > self._timeout:
            self._store.delete(session_id)
            return False

        # Client fingerprint validation — detect hijacking
        if info["ip"] != client_ip:
            _log.warning(
                "Session %s: IP changed from %s to %s — possible hijack",
                session_id[:8], info["ip"], client_ip,
            )
            self._store.delete(session_id)
            return False

        if info["ua"] != user_agent:
            _log.warning(
                "Session %s: User-Agent changed — possible hijack",
                session_id[:8],
            )
            self._store.delete(session_id)
            return False

        info["last_active"] = time.monotonic()
        self._store.put(session_id, info, self._max_lifetime)
        return True

    def update_session_activity(self, session_id: str) -> None:
        info = self._store.get(session_id)
        if info is not None:
            info["last_active"] = time.monotonic()
            self._store.put(session_id, info, self._max_lifetime)

    def revoke_session(self, session_id: str) -> bool:
        """Explicitly revoke a session (e.g. on logout). Returns True if it existed."""
        return self._store.delete(session_id)

    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns count of purged sessions."""
        return self._store.cleanup(self._timeout, self._max_lifetime)

    @property
    def active_count(self) -> int:
        """Return the number of currently tracked sessions."""
        return self._store.count()
