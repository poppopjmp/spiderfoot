"""
API Rate Limiting Middleware for SpiderFoot FastAPI.

Bridges the existing ``RateLimiterService`` into FastAPI as Starlette
middleware.  Every incoming HTTP request is checked against per-tier
rate limits before reaching the router.

Features:
  - Per-client identity extraction (IP, ``X-Forwarded-For``, API key)
  - Route-tier detection from path prefix (``/api/scans`` → ``scan``)
  - 429 Too Many Requests with ``Retry-After`` header on rejection
  - ``X-RateLimit-*`` response headers on every response
  - Configurable exempt paths (health checks, WebSocket upgrade)
  - Stats endpoint for monitoring
  - Structured logging integration

Usage::

    from spiderfoot.api.rate_limit_middleware import install_rate_limiting

    install_rate_limiting(app, config)

"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("spiderfoot.api.rate_limit")

# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------

# Default tiers keyed by route prefix → (requests, window_seconds)
DEFAULT_TIER_LIMITS: dict[str, tuple] = {
    "scan": (30, 60.0),
    "data": (120, 60.0),
    "config": (30, 60.0),
    "reports": (20, 60.0),
    "health": (60, 60.0),
    "engines": (40, 60.0),
    "schedules": (30, 60.0),
    "export": (10, 60.0),
    "storage": (60, 60.0),
    "graphql": (30, 60.0),
    "auth": (10, 60.0),
    "default": (60, 60.0),
}

# Paths exempt from rate limiting
DEFAULT_EXEMPT_PATHS: set[str] = {
    "/api/health",
    "/api/health/ready",
    "/api/health/live",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
}

# Route prefix → tier name mapping
ROUTE_TIER_MAP: dict[str, str] = {
    "/api/scans": "scan",
    "/api/scan": "scan",
    "/api/data": "data",
    "/api/config": "config",
    "/api/reports": "reports",
    "/api/health": "health",
    "/api/engines": "engines",
    "/api/schedules": "schedules",
    "/api/export": "export",
    "/api/storage": "storage",
    "/api/graphql": "graphql",
    "/api/tasks": "default",
    "/api/webhooks": "default",
    "/api/workspaces": "default",
    "/api/visualization": "data",
    "/api/correlations": "data",
    "/api/rag": "data",
    "/ws/": "default",
}


@dataclass
class RateLimitConfig:
    """Configuration for the rate-limiting middleware.

    Args:
        enabled: Whether rate limiting is active.
        tier_limits: Per-tier limits as ``{tier: (requests, window_seconds)}``.
        endpoint_overrides: Per-endpoint overrides as ``{path: (requests, window_seconds)}``.
        exempt_paths: Paths to skip entirely.
        trust_forwarded: If True, use ``X-Forwarded-For`` for client IP.
        include_headers: If True, add ``X-RateLimit-*`` response headers.
        log_rejections: If True, log 429 rejections at WARNING level.
    """

    enabled: bool = True
    tier_limits: dict[str, tuple] = field(default_factory=lambda: dict(DEFAULT_TIER_LIMITS))
    endpoint_overrides: dict[str, tuple] = field(default_factory=dict)
    exempt_paths: set[str] = field(default_factory=lambda: set(DEFAULT_EXEMPT_PATHS))
    trust_forwarded: bool = True
    include_headers: bool = True
    log_rejections: bool = True

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> RateLimitConfig:
        """Build from a flat SpiderFoot config dict.

        Per-endpoint overrides can be set via the environment variable
        ``SF_API_RATE_LIMIT_ENDPOINTS`` as a semicolon-separated list of
        ``path=requests/window`` entries, e.g.:
            ``/api/scans=10/60;/api/scans/bulk/delete=5/60``
        """
        overrides: dict[str, tuple] = {}
        env_overrides = os.environ.get("SF_API_RATE_LIMIT_ENDPOINTS", "")
        if env_overrides:
            for entry in env_overrides.split(";"):
                entry = entry.strip()
                if "=" not in entry:
                    continue
                path_part, limit_part = entry.split("=", 1)
                try:
                    reqs, window = limit_part.split("/", 1)
                    overrides[path_part.strip()] = (int(reqs), float(window))
                except (ValueError, TypeError):
                    log.warning("Invalid rate limit override: %s", entry)
        return cls(
            enabled=config.get("__ratelimit_enabled", True),
            endpoint_overrides=overrides,
            trust_forwarded=config.get("__ratelimit_trust_forwarded", True),
            include_headers=config.get("__ratelimit_headers", True),
            log_rejections=config.get("__ratelimit_log_rejections", True),
        )


# -----------------------------------------------------------------------
# Client identity extraction
# -----------------------------------------------------------------------

def extract_client_identity(
    scope: dict[str, Any],
    headers: dict[str, str],
    *,
    trust_forwarded: bool = True,
) -> str:
    """Determine client identity for rate-limit keying.

    Priority:
      1. ``Authorization`` header (API key hash) — per-key limits
      2. ``X-Forwarded-For`` first hop (if trusted)
      3. Direct client IP from ASGI scope

    Returns:
        A string key like ``"apikey:abc123"`` or ``"ip:192.168.1.1"``.
    """
    # Check for API key
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token:
            # Use first 8 chars as key to avoid storing full token
            return f"apikey:{token[:8]}"

    # Forwarded IP
    if trust_forwarded:
        forwarded = headers.get("x-forwarded-for", "")
        if forwarded:
            # Take the first (client) IP
            client_ip = forwarded.split(",")[0].strip()
            if client_ip:
                return f"ip:{client_ip}"

    # Direct connection IP
    client = scope.get("client")
    if client:
        return f"ip:{client[0]}"

    return "ip:unknown"


def detect_tier(path: str) -> str:
    """Map a request path to a rate-limit tier.

    Matches the longest prefix in ``ROUTE_TIER_MAP``.

    Returns:
        Tier name (e.g. ``"scan"``, ``"data"``).
    """
    best_match = ""
    best_tier = "default"
    for prefix, tier in ROUTE_TIER_MAP.items():
        if path.startswith(prefix) and len(prefix) > len(best_match):
            best_match = prefix
            best_tier = tier
    return best_tier


# -----------------------------------------------------------------------
# Middleware statistics
# -----------------------------------------------------------------------

@dataclass
class RateLimitStats:
    """Aggregated rate-limiting statistics."""

    total_requests: int = 0
    total_allowed: int = 0
    total_rejected: int = 0
    rejections_by_tier: dict[str, int] = field(default_factory=dict)
    rejections_by_client: dict[str, int] = field(default_factory=dict)
    _start_time: float = field(default_factory=time.monotonic)

    @property
    def uptime(self) -> float:
        """Return seconds since stats collection started."""
        return time.monotonic() - self._start_time

    @property
    def rejection_rate(self) -> float:
        """Return the fraction of requests that were rejected."""
        if self.total_requests == 0:
            return 0.0
        return self.total_rejected / self.total_requests

    def record_allowed(self) -> None:
        """Record an allowed request."""
        self.total_requests += 1
        self.total_allowed += 1

    def record_rejected(self, tier: str, client: str) -> None:
        """Record a rejected request for a tier and client."""
        self.total_requests += 1
        self.total_rejected += 1
        self.rejections_by_tier[tier] = self.rejections_by_tier.get(tier, 0) + 1
        # Keep bounded — only track top offenders
        if len(self.rejections_by_client) < 100:
            self.rejections_by_client[client] = (
                self.rejections_by_client.get(client, 0) + 1
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation."""
        return {
            "total_requests": self.total_requests,
            "total_allowed": self.total_allowed,
            "total_rejected": self.total_rejected,
            "rejection_rate": round(self.rejection_rate, 4),
            "uptime_seconds": round(self.uptime, 1),
            "rejections_by_tier": dict(self.rejections_by_tier),
            "top_offenders": dict(
                sorted(
                    self.rejections_by_client.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]
            ),
        }


# -----------------------------------------------------------------------
# Module-level state
# -----------------------------------------------------------------------

_stats = RateLimitStats()
_limiter = None
_config: RateLimitConfig | None = None


def get_rate_limit_stats() -> dict[str, Any]:
    """Return current rate-limiting statistics (for health endpoint)."""
    return _stats.to_dict()


def get_rate_limit_config() -> dict[str, Any]:
    """Return the current rate limit configuration including per-endpoint overrides."""
    if _config is None:
        return {"enabled": False, "tiers": {}, "endpoint_overrides": {}}
    return {
        "enabled": _config.enabled,
        "tiers": {k: {"requests": v[0], "window": v[1]} for k, v in _config.tier_limits.items()},
        "endpoint_overrides": {
            k: {"requests": v[0], "window": v[1]}
            for k, v in _config.endpoint_overrides.items()
        },
        "exempt_paths": sorted(_config.exempt_paths),
    }


def set_endpoint_override(path: str, requests: int, window: float) -> bool:
    """Set a runtime rate limit override for a specific endpoint path.

    Args:
        path: The URL path prefix (e.g. ``/api/scans/bulk/delete``).
        requests: Max requests per window.
        window: Window in seconds.

    Returns:
        True if applied successfully.
    """
    global _config, _limiter
    if _config is None:
        return False
    _config.endpoint_overrides[path] = (requests, window)
    # Update limiter if available
    if _limiter is not None:
        try:
            from spiderfoot.rate_limiter import RateLimit
            _limiter.set_limit(f"endpoint:{path}", RateLimit(requests=requests, window=window))
        except Exception as e:
            log.debug("Failed to set rate limit for endpoint %s: %s", path, e)
    log.info("Endpoint rate limit override set: %s = %d/%0.0fs", path, requests, window)
    return True


def remove_endpoint_override(path: str) -> bool:
    """Remove a per-endpoint rate limit override."""
    global _config
    if _config is None:
        return False
    if path in _config.endpoint_overrides:
        del _config.endpoint_overrides[path]
        log.info("Endpoint rate limit override removed: %s", path)
        return True
    return False


def reset_rate_limit_state() -> None:
    """Reset module state (for testing)."""
    global _stats, _limiter, _config
    _stats = RateLimitStats()
    _limiter = None
    _config = None


# -----------------------------------------------------------------------
# Starlette Middleware
# -----------------------------------------------------------------------

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response, JSONResponse

    HAS_STARLETTE = True
except ImportError:
    HAS_STARLETTE = False


if HAS_STARLETTE:

    class RateLimitMiddleware(BaseHTTPMiddleware):
        """Starlette/FastAPI middleware for API rate limiting.

        Checks each request against ``RateLimiterService`` and returns
        ``429 Too Many Requests`` with ``Retry-After`` when the limit
        is exceeded.

        Response headers (when enabled):
          - ``X-RateLimit-Limit``: Max requests in the window
          - ``X-RateLimit-Remaining``: Requests remaining
          - ``X-RateLimit-Reset``: Seconds until the window resets
          - ``Retry-After``: Seconds to wait (only on 429)
        """

        def __init__(
            self,
            app: Any,
            *,
            rate_config: RateLimitConfig | None = None,
        ) -> None:
            """Initialize the RateLimitMiddleware."""
            super().__init__(app)
            self._config = rate_config or RateLimitConfig()
            self._setup_limiter()

        def _setup_limiter(self) -> None:
            """Initialize the RateLimiterService with tier configs."""
            global _limiter, _config
            from spiderfoot.rate_limiter import RateLimiterService, RateLimit

            _config = self._config
            _limiter = RateLimiterService()

            for tier, (requests, window) in self._config.tier_limits.items():
                _limiter.set_limit(
                    f"tier:{tier}",
                    RateLimit(requests=requests, window=window),
                )

            # Register per-endpoint overrides
            for path, (requests, window) in self._config.endpoint_overrides.items():
                _limiter.set_limit(
                    f"endpoint:{path}",
                    RateLimit(requests=requests, window=window),
                )

            log.info(
                "Rate limiting initialized with %d tiers, %d endpoint overrides",
                len(self._config.tier_limits),
                len(self._config.endpoint_overrides),
            )

        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            """Process a request through rate limiting."""
            if not self._config.enabled:
                return await call_next(request)

            path = request.url.path

            # Skip exempt paths
            for exempt in self._config.exempt_paths:
                if path.startswith(exempt):
                    return await call_next(request)

            # Identify client and tier
            headers = {k.decode(): v.decode() for k, v in request.scope.get("headers", [])}
            client_id = extract_client_identity(
                request.scope, headers,
                trust_forwarded=self._config.trust_forwarded,
            )

            # Check for per-endpoint override (longest match wins)
            endpoint_key = None
            best_ep_match = ""
            for ep_path in self._config.endpoint_overrides:
                if path.startswith(ep_path) and len(ep_path) > len(best_ep_match):
                    best_ep_match = ep_path
                    endpoint_key = f"endpoint:{ep_path}"

            tier = detect_tier(path)

            # Use endpoint-specific limit if available, otherwise tier
            if endpoint_key:
                limit_key = endpoint_key
                client_key = f"{endpoint_key}:{client_id}"
            else:
                limit_key = f"tier:{tier}"
                client_key = f"{limit_key}:{client_id}"

            # Ensure per-client key inherits the tier's limit
            if client_key not in _limiter._limits:
                _limiter.set_limit(client_key, _limiter.get_limit(limit_key))

            # Check tier-level limit using the limiter
            result = _limiter.check(client_key)

            if not result.allowed:
                # Rejected
                retry_after = max(1.0, result.retry_after)
                _stats.record_rejected(tier, client_id)

                if self._config.log_rejections:
                    req_id = ""
                    try:
                        from spiderfoot.request_tracing import get_request_id
                        req_id = get_request_id() or ""
                    except ImportError:
                        pass

                    log.warning(
                        "Rate limited: client=%s tier=%s path=%s retry_after=%.1fs request_id=%s",
                        client_id, tier, path, retry_after, req_id,
                    )

                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "detail": f"Rate limit exceeded for tier '{tier}'",
                        "retry_after": round(retry_after, 1),
                    },
                )
                response.headers["Retry-After"] = str(int(retry_after))
                if self._config.include_headers:
                    limit_cfg = _limiter.get_limit(limit_key)
                    response.headers["X-RateLimit-Limit"] = str(limit_cfg.requests)
                    response.headers["X-RateLimit-Remaining"] = "0"
                    response.headers["X-RateLimit-Reset"] = str(int(retry_after))
                return response

            # Allowed
            _stats.record_allowed()
            response = await call_next(request)

            # Add rate-limit headers
            if self._config.include_headers:
                limit_cfg = _limiter.get_limit(limit_key)
                response.headers["X-RateLimit-Limit"] = str(limit_cfg.requests)
                response.headers["X-RateLimit-Remaining"] = str(
                    max(0, result.remaining)
                )
                response.headers["X-RateLimit-Reset"] = str(
                    int(limit_cfg.window)
                )

            return response


# -----------------------------------------------------------------------
# Installation helper
# -----------------------------------------------------------------------


def install_rate_limiting(
    app: Any,
    config: dict[str, Any] | None = None,
) -> bool:
    """Install rate-limiting middleware on a FastAPI/Starlette app.

    Args:
        app: FastAPI or Starlette application.
        config: Optional SpiderFoot config dict.

    Returns:
        True if middleware was installed, False on error.
    """
    if not HAS_STARLETTE:
        log.warning("Starlette not available — rate limiting disabled")
        return False

    try:
        rate_config = RateLimitConfig.from_dict(config or {})
        app.add_middleware(RateLimitMiddleware, rate_config=rate_config)
        log.info("Rate limiting middleware installed (enabled=%s)", rate_config.enabled)
        return True
    except Exception as e:
        log.error("Failed to install rate limiting: %s", e)
        return False
