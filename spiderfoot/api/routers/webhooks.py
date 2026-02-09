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
from typing import Any, Dict, List, Optional

log = logging.getLogger("spiderfoot.api.webhooks")

try:
    from fastapi import APIRouter, HTTPException, Query
    from pydantic import BaseModel, Field

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from spiderfoot.notification_manager import get_notification_manager
from spiderfoot.webhook_dispatcher import WebhookConfig


# -----------------------------------------------------------------------
# Pydantic models
# -----------------------------------------------------------------------

if HAS_FASTAPI:

    class WebhookCreateRequest(BaseModel):
        url: str = Field(..., description="Webhook URL to POST to")
        secret: str = Field("", description="HMAC-SHA256 signing secret")
        event_types: List[str] = Field(
            default_factory=list,
            description="Event types to subscribe to (empty = all)",
        )
        headers: Dict[str, str] = Field(
            default_factory=dict,
            description="Custom HTTP headers",
        )
        enabled: bool = True
        timeout: float = Field(10.0, ge=1.0, le=60.0)
        max_retries: int = Field(3, ge=0, le=10)
        description: str = ""

    class WebhookUpdateRequest(BaseModel):
        url: Optional[str] = None
        secret: Optional[str] = None
        event_types: Optional[List[str]] = None
        enabled: Optional[bool] = None
        timeout: Optional[float] = None
        max_retries: Optional[int] = None
        description: Optional[str] = None


# -----------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------

if not HAS_FASTAPI:

    class _StubRouter:
        pass

    router = _StubRouter()
else:
    router = APIRouter()

    @router.get(
        "/webhooks",
        summary="List webhooks",
        description="List all registered webhook endpoints.",
    )
    async def list_webhooks():
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
    async def create_webhook(body: WebhookCreateRequest):
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
    async def webhook_stats():
        mgr = get_notification_manager()
        return mgr.stats

    @router.get(
        "/webhooks/history",
        summary="Delivery history",
        description="Recent webhook delivery attempts.",
    )
    async def webhook_history(
        webhook_id: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=500),
    ):
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
    async def get_webhook(webhook_id: str):
        mgr = get_notification_manager()
        cfg = mgr.get_webhook(webhook_id)
        if cfg is None:
            raise HTTPException(status_code=404, detail="Webhook not found.")
        return cfg.to_dict()

    @router.delete(
        "/webhooks/{webhook_id}",
        summary="Remove a webhook",
    )
    async def delete_webhook(webhook_id: str):
        mgr = get_notification_manager()
        if not mgr.remove_webhook(webhook_id):
            raise HTTPException(status_code=404, detail="Webhook not found.")
        return {"webhook_id": webhook_id, "status": "removed"}

    @router.post(
        "/webhooks/{webhook_id}/test",
        summary="Send test event",
        description="Dispatch a test event to verify webhook connectivity.",
    )
    async def test_webhook(webhook_id: str):
        mgr = get_notification_manager()
        record = mgr.test_webhook(webhook_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Webhook not found.")
        return record.to_dict()

    @router.patch(
        "/webhooks/{webhook_id}",
        summary="Update webhook",
    )
    async def update_webhook(webhook_id: str, body: WebhookUpdateRequest):
        mgr = get_notification_manager()
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update.")
        if not mgr.update_webhook(webhook_id, **updates):
            raise HTTPException(status_code=404, detail="Webhook not found.")
        return {"webhook_id": webhook_id, "status": "updated", "fields": list(updates.keys())}
