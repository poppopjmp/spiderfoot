#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         rate_limiter
# Purpose:      Standalone rate limiter service for SpiderFoot.
#               Provides per-module, per-API-key, and per-endpoint rate
#               limiting with multiple algorithms (token bucket, sliding
#               window, fixed window).
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
SpiderFoot Rate Limiter Service

Centralized rate limiting for internal and external service calls::

    from spiderfoot.rate_limiter import RateLimiterService, RateLimit

    limiter = RateLimiterService()

    # Configure limits
    limiter.set_limit("shodan_api", RateLimit(requests=1, window=1.0))
    limiter.set_limit("module:sfp_shodan", RateLimit(requests=10, window=60.0))

    # Check / consume
    if limiter.allow("shodan_api"):
        # proceed with API call
        ...
    else:
        wait = limiter.retry_after("shodan_api")

    # Use as context manager
    async with limiter.acquire("shodan_api"):
        response = await client.get(...)
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger("spiderfoot.rate_limiter")


class Algorithm(str, Enum):
    """Rate limiting algorithm."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimit:
    """Rate limit configuration for a key.

    Args:
        requests: Maximum number of requests.
        window: Time window in seconds.
        burst: Max burst above steady rate (token bucket only).
        algorithm: Rate limiting algorithm.
    """
    requests: int = 30
    window: float = 60.0
    burst: int = 0  # 0 = same as requests
    algorithm: Algorithm = Algorithm.TOKEN_BUCKET

    @property
    def effective_burst(self) -> int:
        return self.burst if self.burst > 0 else self.requests

    @property
    def rate(self) -> float:
        """Requests per second."""
        return self.requests / self.window if self.window > 0 else float("inf")


@dataclass
class LimitState:
    """Internal state for a rate limit."""
    # Token bucket
    tokens: float = 0.0
    last_refill: float = 0.0

    # Sliding window
    request_log: list = field(default_factory=list)

    # Fixed window
    window_start: float = 0.0
    window_count: int = 0

    # Stats
    total_allowed: int = 0
    total_denied: int = 0


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    key: str
    remaining: int = 0
    retry_after: float = 0.0
    limit: int = 0
    window: float = 0.0


class RateLimiterService:
    """Centralized rate limiter with multiple algorithms.

    Supports per-key rate limits for:
    - External APIs (``api:shodan``, ``api:virustotal``)
    - Modules (``module:sfp_shodan``)
    - Clients (``client:192.168.1.1``)
    - Endpoints (``endpoint:/api/scan``)
    - Custom keys
    """

    def __init__(self, default_limit: RateLimit | None = None) -> None:
        """
        Args:
            default_limit: Default limit for keys without explicit config.
        """
        self._default = default_limit or RateLimit(
            requests=60, window=60.0)
        self._limits: dict[str, RateLimit] = {}
        self._states: dict[str, LimitState] = {}
        self._lock = threading.Lock()
        self._global_enabled = True

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_limit(self, key: str, limit: RateLimit) -> None:
        """Set rate limit for a key."""
        with self._lock:
            self._limits[key] = limit
            # Reset state for clean start
            self._states.pop(key, None)
        log.debug("Set rate limit for %s: %d req / %.1fs",
                 key, limit.requests, limit.window)

    def remove_limit(self, key: str) -> bool:
        """Remove rate limit for a key (falls back to default)."""
        with self._lock:
            removed = self._limits.pop(key, None) is not None
            self._states.pop(key, None)
        return removed

    def get_limit(self, key: str) -> RateLimit:
        """Get the rate limit for a key (or default)."""
        return self._limits.get(key, self._default)

    @property
    def enabled(self) -> bool:
        return self._global_enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._global_enabled = value

    # ------------------------------------------------------------------
    # Rate checking
    # ------------------------------------------------------------------

    def allow(self, key: str) -> bool:
        """Check if a request is allowed and consume a token.

        Returns True if allowed, False if rate limited.
        """
        return self.check(key).allowed

    def check(self, key: str) -> RateLimitResult:
        """Check rate limit with full result details."""
        if not self._global_enabled:
            limit = self.get_limit(key)
            return RateLimitResult(
                allowed=True, key=key,
                remaining=limit.requests,
                limit=limit.requests,
                window=limit.window,
            )

        limit = self.get_limit(key)

        with self._lock:
            state = self._states.setdefault(key, LimitState())

            if limit.algorithm == Algorithm.TOKEN_BUCKET:
                result = self._check_token_bucket(key, limit, state)
            elif limit.algorithm == Algorithm.SLIDING_WINDOW:
                result = self._check_sliding_window(key, limit, state)
            elif limit.algorithm == Algorithm.FIXED_WINDOW:
                result = self._check_fixed_window(key, limit, state)
            else:
                result = self._check_token_bucket(key, limit, state)

            if result.allowed:
                state.total_allowed += 1
            else:
                state.total_denied += 1

        return result

    def retry_after(self, key: str) -> float:
        """Get seconds until next request would be allowed."""
        limit = self.get_limit(key)

        with self._lock:
            state = self._states.get(key)
            if not state:
                return 0.0

            if limit.algorithm == Algorithm.TOKEN_BUCKET:
                if state.tokens >= 1:
                    return 0.0
                return (1.0 - state.tokens) / limit.rate

            elif limit.algorithm == Algorithm.SLIDING_WINDOW:
                now = time.monotonic()
                cutoff = now - limit.window
                active = [t for t in state.request_log if t > cutoff]
                if len(active) < limit.requests:
                    return 0.0
                return active[0] - cutoff

            elif limit.algorithm == Algorithm.FIXED_WINDOW:
                now = time.monotonic()
                window_end = state.window_start + limit.window
                if state.window_count < limit.requests:
                    return 0.0
                return max(0.0, window_end - now)

        return 0.0

    def wait(self, key: str) -> float:
        """Block until a request is allowed. Returns wait time in seconds."""
        delay = self.retry_after(key)
        if delay > 0:
            time.sleep(delay)
        # Now consume
        self.allow(key)
        return delay

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def allow_all(self, keys: list[str]) -> bool:
        """Check multiple keys — all must be allowed."""
        results = [self.check(k) for k in keys]
        return all(r.allowed for r in results)

    def reset(self, key: str) -> None:
        """Reset rate limit state for a key."""
        with self._lock:
            self._states.pop(key, None)

    def reset_all(self) -> None:
        """Reset all rate limit states."""
        with self._lock:
            self._states.clear()

    # ------------------------------------------------------------------
    # Stats & introspection
    # ------------------------------------------------------------------

    def get_stats(self, key: str) -> dict:
        """Get stats for a key."""
        with self._lock:
            state = self._states.get(key)
            limit = self.get_limit(key)

            if not state:
                return {
                    "key": key,
                    "allowed": 0,
                    "denied": 0,
                    "limit": limit.requests,
                    "window": limit.window,
                }

            return {
                "key": key,
                "allowed": state.total_allowed,
                "denied": state.total_denied,
                "limit": limit.requests,
                "window": limit.window,
                "algorithm": limit.algorithm.value,
            }

    @property
    def all_stats(self) -> list[dict]:
        """Get stats for all tracked keys."""
        with self._lock:
            keys = set(self._limits.keys()) | set(self._states.keys())
        return [self.get_stats(k) for k in sorted(keys)]

    def cleanup(self, max_idle: float = 300.0) -> int:
        """Remove stale entries. Returns number removed."""
        now = time.monotonic()
        removed = 0
        with self._lock:
            stale = []
            for key, state in self._states.items():
                if state.last_refill > 0:
                    if now - state.last_refill > max_idle:
                        stale.append(key)
                elif state.request_log:
                    if now - state.request_log[-1] > max_idle:
                        stale.append(key)
                elif state.window_start > 0:
                    if now - state.window_start > max_idle:
                        stale.append(key)

            for key in stale:
                del self._states[key]
                removed += 1

        return removed

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    class _Acquirer:
        """Context manager that waits for rate limit clearance."""
        def __init__(self, service: "RateLimiterService", key: str) -> None:
            self._service = service
            self._key = key
            self.waited = 0.0

        def __enter__(self):
            self.waited = self._service.wait(self._key)
            return self

        def __exit__(self, *_):
            pass

    def acquire(self, key: str) -> "_Acquirer":
        """Returns context manager that blocks until allowed.

        Usage::

            with limiter.acquire("api:shodan") as ctx:
                # Guaranteed within rate limit
                response = fetch(url)
                print(f"Waited {ctx.waited:.2f}s")
        """
        return self._Acquirer(self, key)

    # ------------------------------------------------------------------
    # Pre-configured module limits
    # ------------------------------------------------------------------

    def configure_from_dict(self, config: dict[str, dict]) -> int:
        """Load rate limits from a config dictionary.

        Format::

            {
                "api:shodan": {"requests": 1, "window": 1.0},
                "module:sfp_virustotal": {"requests": 4, "window": 60.0},
            }

        Returns number of limits configured.
        """
        count = 0
        for key, params in config.items():
            try:
                algo = params.get("algorithm", "token_bucket")
                limit = RateLimit(
                    requests=params.get("requests", 30),
                    window=params.get("window", 60.0),
                    burst=params.get("burst", 0),
                    algorithm=Algorithm(algo),
                )
                self.set_limit(key, limit)
                count += 1
            except Exception as e:
                log.warning("Invalid rate limit config for %s: %s", key, e)

        return count

    # ------------------------------------------------------------------
    # Algorithm implementations
    # ------------------------------------------------------------------

    def _check_token_bucket(self, key: str, limit: RateLimit,
                            state: LimitState) -> RateLimitResult:
        now = time.monotonic()

        if state.last_refill == 0:
            state.tokens = float(limit.effective_burst)
            state.last_refill = now

        # Refill tokens
        elapsed = now - state.last_refill
        state.tokens = min(
            float(limit.effective_burst),
            state.tokens + elapsed * limit.rate
        )
        state.last_refill = now

        if state.tokens >= 1.0:
            state.tokens -= 1.0
            remaining = int(state.tokens)
            return RateLimitResult(
                allowed=True, key=key,
                remaining=remaining,
                limit=limit.requests,
                window=limit.window,
            )

        retry = (1.0 - state.tokens) / limit.rate if limit.rate > 0 else 0
        return RateLimitResult(
            allowed=False, key=key,
            remaining=0,
            retry_after=retry,
            limit=limit.requests,
            window=limit.window,
        )

    def _check_sliding_window(self, key: str, limit: RateLimit,
                              state: LimitState) -> RateLimitResult:
        now = time.monotonic()
        cutoff = now - limit.window

        # Prune old entries
        state.request_log = [t for t in state.request_log if t > cutoff]

        if len(state.request_log) < limit.requests:
            state.request_log.append(now)
            remaining = limit.requests - len(state.request_log)
            return RateLimitResult(
                allowed=True, key=key,
                remaining=remaining,
                limit=limit.requests,
                window=limit.window,
            )

        retry = state.request_log[0] - cutoff if state.request_log else 0
        return RateLimitResult(
            allowed=False, key=key,
            remaining=0,
            retry_after=max(0.0, retry),
            limit=limit.requests,
            window=limit.window,
        )

    def _check_fixed_window(self, key: str, limit: RateLimit,
                            state: LimitState) -> RateLimitResult:
        now = time.monotonic()

        # New window?
        if state.window_start == 0 or now >= state.window_start + limit.window:
            state.window_start = now
            state.window_count = 0

        if state.window_count < limit.requests:
            state.window_count += 1
            remaining = limit.requests - state.window_count
            return RateLimitResult(
                allowed=True, key=key,
                remaining=remaining,
                limit=limit.requests,
                window=limit.window,
            )

        retry = state.window_start + limit.window - now
        return RateLimitResult(
            allowed=False, key=key,
            remaining=0,
            retry_after=max(0.0, retry),
            limit=limit.requests,
            window=limit.window,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_limiter_instance: RateLimiterService | None = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiterService:
    """Get the global RateLimiterService singleton."""
    global _limiter_instance
    if _limiter_instance is None:
        with _limiter_lock:
            if _limiter_instance is None:
                _limiter_instance = RateLimiterService()
    return _limiter_instance
