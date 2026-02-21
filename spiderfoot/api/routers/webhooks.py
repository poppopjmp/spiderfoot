"""
Webhook Management API Router for SpiderFoot.

CRUD endpoints for managing webhook subscriptions and viewing
delivery history.

Endpoints:
  GET    /api/webhooks              - List registered webhooks
  POST   /api/webhooks              - Register a new webhook
  GET    /api/webhooks/stats        - Delivery statistics
  GET    /api/webhooks/history      - Delivery history
  GET    /api/webhooks/{id}         - Get webhook details
  DELETE /api/webhooks/{id}         - Remove a webhook
  POST   /api/webhooks/{id}/test    - Send test event
  PATCH  /api/webhooks/{id}         - Update webhook config
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse
import ipaddress
import socket

log = logging.getLogger("spiderfoot.api.webhooks")

try:
    from fastapi import APIRouter, Depends, HTTPException, Query
    from pydantic import BaseModel, Field, field_validator

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from spiderfoot.notification_manager import get_notification_manager
from spiderfoot.webhook_dispatcher import WebhookConfig

# ── SSRF protection ──────────────────────────────────────────────

_BLOCKED_HOSTNAMES = frozenset({
    "localhost", "metadata.google.internal", "169.254.169.254",
})


def _validate_webhook_url(url: str) -> str:
    """Reject webhook URLs that target private/internal networks (SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Webhook URL must use http:// or https://")
    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("Webhook URL must have a hostname")
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Webhook URL cannot target reserved hostname: {hostname}")
    # Resolve hostname and check for private/reserved IP ranges
    try:
        for info in socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM):
            addr = info[4][0]
            ip = ipaddress.ip_address(addr)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError(
                    f"Webhook URL resolves to a private/internal IP ({addr}). "
                    "Only public addresses are allowed."
                )
    except socket.gaierror:
        pass  # DNS resolution may fail in CI, allow and let delivery fail later
    return url


# -----------------------------------------------------------------------
# Pydantic models
# -----------------------------------------------------------------------

if HAS_FASTAPI:

    class WebhookCreateRequest(BaseModel):
        """Data model for a webhook registration request."""
        url: str = Field(..., description="Webhook URL to POST to")
        secret: str = Field("", description="HMAC-SHA256 signing secret")
        event_types: list[str] = Field(
            default_factory=list,
            description="Event types to subscribe to (empty = all)",
        )
        headers: dict[str, str] = Field(
            default_factory=dict,
            description="Custom HTTP headers",
        )
        enabled: bool = True
        timeout: float = Field(10.0, ge=1.0, le=60.0)
        max_retries: int = Field(3, ge=0, le=10)
        description: str = ""

        @field_validator("url")
        @classmethod
        def _check_url(cls, v: str) -> str:
            return _validate_webhook_url(v)

    class WebhookUpdateRequest(BaseModel):
        """Data model for a webhook update request."""
        url: str | None = None
        secret: str | None = None
        event_types: list[str] | None = None
        enabled: bool | None = None
        timeout: float | None = None
        max_retries: int | None = None
        description: str | None = None

        @field_validator("url")
        @classmethod
        def _check_url(cls, v: str | None) -> str | None:
            if v is not None:
                return _validate_webhook_url(v)
            return v


# -----------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------

if not HAS_FASTAPI:

    class _StubRouter:
        """Stub router for when FastAPI dependencies are unavailable."""
        pass

    router = _StubRouter()
else:
    from ..dependencies import get_api_key, SafeId

    router = APIRouter(dependencies=[Depends(get_api_key)])

    @router.get(
        "/webhooks",
        summary="List webhooks",
        description="List all registered webhook endpoints.",
    )
    async def list_webhooks() -> dict[str, Any]:
        """List all registered webhook endpoints."""
        mgr = get_notification_manager()
        hooks = mgr.list_webhooks()
        return {
            "webhooks": [h.to_dict() for h in hooks],
            "count": len(hooks),
        }

    @router.post(
        "/webhooks",
        status_code=201,
        summary="Register a webhook",
        description="Create a new webhook subscription.",
    )
    async def create_webhook(body: WebhookCreateRequest) -> dict[str, Any]:
        """Register a new webhook subscription."""
        mgr = get_notification_manager()
        cfg = WebhookConfig(
            url=body.url,
            secret=body.secret,
            event_types=body.event_types,
            headers=body.headers,
            enabled=body.enabled,
            timeout=body.timeout,
            max_retries=body.max_retries,
            description=body.description,
        )
        wid = mgr.add_webhook(cfg)
        return {"webhook_id": wid, "url": body.url, "status": "registered"}

    @router.get(
        "/webhooks/stats",
        summary="Delivery statistics",
        description="Aggregate statistics for all webhook deliveries.",
    )
    async def webhook_stats() -> dict[str, Any]:
        """Return aggregate delivery statistics for all webhooks."""
        mgr = get_notification_manager()
        return mgr.stats

    @router.get(
        "/webhooks/history",
        summary="Delivery history",
        description="Recent webhook delivery attempts.",
    )
    async def webhook_history(
        webhook_id: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
    ) -> dict[str, Any]:
        """Return recent webhook delivery attempts."""
        mgr = get_notification_manager()
        records = mgr.get_delivery_history(
            webhook_id=webhook_id, limit=limit,
        )
        return {
            "deliveries": [r.to_dict() for r in records],
            "count": len(records),
        }

    @router.get(
        "/webhooks/{webhook_id}",
        summary="Get webhook details",
    )
    async def get_webhook(webhook_id: SafeId) -> dict[str, Any]:
        """Return details for a specific webhook."""
        mgr = get_notification_manager()
        cfg = mgr.get_webhook(webhook_id)
        if cfg is None:
            raise HTTPException(status_code=404, detail="Webhook not found.")
        return cfg.to_dict()

    @router.delete(
        "/webhooks/{webhook_id}",
        summary="Remove a webhook",
    )
    async def delete_webhook(webhook_id: SafeId) -> dict[str, Any]:
        """Remove a registered webhook."""
        mgr = get_notification_manager()
        if not mgr.remove_webhook(webhook_id):
            raise HTTPException(status_code=404, detail="Webhook not found.")
        return {"webhook_id": webhook_id, "status": "removed"}

    @router.post(
        "/webhooks/{webhook_id}/test",
        summary="Send test event",
        description="Dispatch a test event to verify webhook connectivity.",
    )
    async def test_webhook(webhook_id: SafeId) -> dict[str, Any]:
        """Send a test event to verify webhook connectivity."""
        mgr = get_notification_manager()
        record = mgr.test_webhook(webhook_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Webhook not found.")
        return record.to_dict()

    @router.patch(
        "/webhooks/{webhook_id}",
        summary="Update webhook",
    )
    async def update_webhook(webhook_id: SafeId, body: WebhookUpdateRequest) -> dict[str, Any]:
        """Update configuration fields for a webhook."""
        mgr = get_notification_manager()
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update.")
        if not mgr.update_webhook(webhook_id, **updates):
            raise HTTPException(status_code=404, detail="Webhook not found.")
        return {"webhook_id": webhook_id, "status": "updated", "fields": list(updates.keys())}

    # -------------------------------------------------------------------
    # Event type discovery & filter management
    # -------------------------------------------------------------------

    # All known webhook event types grouped by category
    KNOWN_EVENT_TYPES: dict[str, list[str]] = {
        "scan": [
            "scan.created",
            "scan.started",
            "scan.completed",
            "scan.stopped",
            "scan.error",
            "scan.deleted",
            "scan.archived",
            "scan.unarchived",
            "scan.rerun",
            "scan.cloned",
        ],
        "event": [
            "event.new",
            "event.false_positive",
        ],
        "correlation": [
            "correlation.detected",
            "correlation.resolved",
        ],
        "module": [
            "module.started",
            "module.completed",
            "module.error",
            "module.timeout",
        ],
        "system": [
            "system.health_degraded",
            "system.config_changed",
            "system.api_key_rotated",
        ],
    }

    @router.get(
        "/webhooks/event-types",
        summary="List available event types",
        description="Returns all known webhook event types that can be used for filtering.",
    )
    async def list_event_types() -> dict[str, Any]:
        """Return all known webhook event types."""
        flat = []
        for category, types in KNOWN_EVENT_TYPES.items():
            for et in types:
                flat.append({
                    "event_type": et,
                    "category": category,
                    "description": et.replace(".", " ").replace("_", " ").title(),
                    "supports_wildcard": True,
                })
        return {
            "event_types": flat,
            "total": len(flat),
            "categories": list(KNOWN_EVENT_TYPES.keys()),
            "note": "Use category prefix with wildcard (e.g. 'scan.*') to subscribe to all events in a category.",
        }

    class EventFilterUpdateRequest(BaseModel):
        """Data model for updating a webhook's event type filter."""
        event_types: list[str] = Field(
            ...,
            description="New list of event types to subscribe to (empty = all events)",
        )

    @router.put(
        "/webhooks/{webhook_id}/event-filter",
        summary="Update webhook event filter",
        description="Replace the event type filter for a webhook.",
    )
    async def update_event_filter(webhook_id: SafeId, body: EventFilterUpdateRequest) -> dict[str, Any]:
        """Replace the event type filter for a webhook."""
        mgr = get_notification_manager()
        cfg = mgr.get_webhook(webhook_id)
        if cfg is None:
            raise HTTPException(status_code=404, detail="Webhook not found.")

        # Validate event types against known list
        all_known = set()
        for types in KNOWN_EVENT_TYPES.values():
            all_known.update(types)
        all_categories = set(KNOWN_EVENT_TYPES.keys())

        warnings = []
        for et in body.event_types:
            if et.endswith(".*"):
                cat = et[:-2]
                if cat not in all_categories:
                    warnings.append(f"Unknown category wildcard: {et}")
            elif et not in all_known:
                warnings.append(f"Unknown event type: {et}")

        if not mgr.update_webhook(webhook_id, event_types=body.event_types):
            raise HTTPException(status_code=500, detail="Failed to update event filter.")

        return {
            "webhook_id": webhook_id,
            "event_types": body.event_types,
            "subscribes_to_all": len(body.event_types) == 0,
            "warnings": warnings,
            "status": "updated",
        }
