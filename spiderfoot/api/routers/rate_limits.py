# -*- coding: utf-8 -*-
"""
Rate Limit management router — View and modify API rate limits at runtime.

Endpoints:
  GET    /api/rate-limits         - Get current rate limit configuration
  GET    /api/rate-limits/stats   - Get rate limit statistics
  PUT    /api/rate-limits/tiers/{tier}     - Update a tier's limit
  PUT    /api/rate-limits/endpoints/{path} - Set per-endpoint override
  DELETE /api/rate-limits/endpoints/{path} - Remove per-endpoint override
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from ..dependencies import get_api_key

log = logging.getLogger("spiderfoot.api.rate_limits")

router = APIRouter(prefix="/api/rate-limits", tags=["rate-limits"])

api_key_dep = Depends(get_api_key)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RateLimitTier(BaseModel):
    """Rate limit tier configuration."""
    requests: int = Field(..., ge=1, le=10000, description="Max requests per window")
    window: float = Field(..., ge=1.0, le=86400.0, description="Window in seconds")


class TierListResponse(BaseModel):
    """Current rate limit configuration."""
    enabled: bool
    tiers: dict[str, RateLimitTier]
    endpoint_overrides: dict[str, RateLimitTier]
    exempt_paths: list[str]
    route_tier_map: dict[str, str]


class RateLimitStatsResponse(BaseModel):
    """Rate limit statistics."""
    total_requests: int = 0
    total_allowed: int = 0
    total_rejected: int = 0
    rejection_rate: float = 0.0
    uptime_seconds: float = 0.0
    rejections_by_tier: dict[str, int] = {}
    top_offenders: dict[str, int] = {}


class EndpointOverrideRequest(BaseModel):
    """Request body for setting an endpoint rate limit override."""
    requests: int = Field(..., ge=1, le=10000, description="Max requests per window")
    window: float = Field(60.0, ge=1.0, le=86400.0, description="Window in seconds")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=TierListResponse)
async def get_rate_limits(
    api_key: str = api_key_dep,
) -> TierListResponse:
    """Get the current rate limit configuration."""
    from spiderfoot.api.rate_limit_middleware import (
        get_rate_limit_config, ROUTE_TIER_MAP,
    )
    config = get_rate_limit_config()
    return TierListResponse(
        enabled=config.get("enabled", False),
        tiers={
            k: RateLimitTier(requests=v["requests"], window=v["window"])
            for k, v in config.get("tiers", {}).items()
        },
        endpoint_overrides={
            k: RateLimitTier(requests=v["requests"], window=v["window"])
            for k, v in config.get("endpoint_overrides", {}).items()
        },
        exempt_paths=config.get("exempt_paths", []),
        route_tier_map=dict(ROUTE_TIER_MAP),
    )


@router.get("/stats", response_model=RateLimitStatsResponse)
async def get_rate_limit_statistics(
    api_key: str = api_key_dep,
) -> RateLimitStatsResponse:
    """Get rate limiting statistics."""
    from spiderfoot.api.rate_limit_middleware import get_rate_limit_stats
    stats = get_rate_limit_stats()
    return RateLimitStatsResponse(**stats)


@router.put("/tiers/{tier}", response_model=dict)
async def update_tier_limit(
    tier: str = Path(..., description="Tier name (e.g. scan, data, config)"),
    body: RateLimitTier = ...,
    api_key: str = api_key_dep,
) -> dict:
    """Update a rate limit tier's configuration at runtime.

    Changes take effect immediately for new requests. Existing
    rate-limit windows are not reset.
    """
    from spiderfoot.api.rate_limit_middleware import (
        _config, _limiter, DEFAULT_TIER_LIMITS,
    )
    from spiderfoot.rate_limiter import RateLimit

    if _config is None:
        raise HTTPException(status_code=503, detail="Rate limiting not configured")

    # Update tier
    _config.tier_limits[tier] = (body.requests, body.window)
    if _limiter is not None:
        _limiter.set_limit(f"tier:{tier}", RateLimit(requests=body.requests, window=body.window))

    log.info("Updated tier '%s' rate limit: %d reqs / %.0fs", tier, body.requests, body.window)
    return {
        "tier": tier,
        "requests": body.requests,
        "window": body.window,
        "message": f"Tier '{tier}' updated",
    }


@router.put("/endpoints/{path:path}", response_model=dict)
async def set_endpoint_override(
    path: str,
    body: EndpointOverrideRequest,
    api_key: str = api_key_dep,
) -> dict:
    """Set or update a rate limit override for a specific endpoint path.

    The ``path`` should be the URL prefix (e.g. ``/api/scans/bulk/delete``).
    Overrides take priority over tier-level limits.
    """
    from spiderfoot.api.rate_limit_middleware import (
        set_endpoint_override as _set_override,
    )

    # Ensure path starts with /
    if not path.startswith("/"):
        path = "/" + path

    success = _set_override(path, body.requests, body.window)
    if not success:
        raise HTTPException(status_code=503, detail="Rate limiting not configured")

    return {
        "path": path,
        "requests": body.requests,
        "window": body.window,
        "message": f"Endpoint override set for '{path}'",
    }


@router.delete("/endpoints/{path:path}", status_code=200)
async def remove_endpoint_override(
    path: str,
    api_key: str = api_key_dep,
) -> dict:
    """Remove a per-endpoint rate limit override."""
    from spiderfoot.api.rate_limit_middleware import (
        remove_endpoint_override as _remove_override,
    )

    if not path.startswith("/"):
        path = "/" + path

    removed = _remove_override(path)
    if not removed:
        raise HTTPException(status_code=404, detail=f"No override found for '{path}'")

    return {"path": path, "message": f"Override removed for '{path}'"}


@router.post("/stats/reset", status_code=200)
async def reset_stats(
    api_key: str = api_key_dep,
) -> dict:
    """Reset rate limit statistics counters."""
    from spiderfoot.api.rate_limit_middleware import _stats, RateLimitStats
    import spiderfoot.api.rate_limit_middleware as rlm
    rlm._stats = RateLimitStats()
    log.info("Rate limit statistics reset")
    return {"message": "Statistics reset"}
