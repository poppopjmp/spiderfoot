"""
Webhook Delivery API router.

Endpoints for webhook delivery management, monitoring, and replay.

v5.6.7
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from spiderfoot.webhook_delivery import WebhookDeliveryManager, RetryPolicy

_log = logging.getLogger("spiderfoot.api.webhook_delivery")

router = APIRouter()

_manager = WebhookDeliveryManager()


class CreateDeliveryRequest(BaseModel):
    """Create a webhook delivery."""
    endpoint_id: str = Field(..., description="Endpoint identifier")
    endpoint_url: str = Field(..., description="Delivery URL")
    event_type: str = Field(..., description="Event type (e.g. scan.completed)")
    payload: dict = Field(default_factory=dict)
    secret: str = Field("", description="HMAC signing secret")
    headers: dict = Field(default_factory=dict)
    timeout_seconds: int = Field(30, ge=5, le=120)
    max_retries: int = Field(5, ge=0, le=20)


class RecordAttemptRequest(BaseModel):
    """Record a delivery attempt."""
    status_code: int = Field(0, ge=0, le=599)
    response_body: str = Field("")
    error: str = Field("")
    duration_ms: float = Field(0.0, ge=0)


# ── Delivery CRUD ─────────────────────────────────────────────────────

@router.post("/webhook-delivery/deliveries")
async def create_delivery(req: CreateDeliveryRequest):
    """Create a new webhook delivery."""
    retry = RetryPolicy(max_retries=req.max_retries)
    delivery = _manager.create_delivery(
        endpoint_id=req.endpoint_id,
        endpoint_url=req.endpoint_url,
        event_type=req.event_type,
        payload=req.payload,
        secret=req.secret,
        headers=req.headers,
        retry_policy=retry,
        timeout_seconds=req.timeout_seconds,
    )
    return {"delivery": delivery.__dict__}


@router.get("/webhook-delivery/deliveries")
async def list_deliveries(
    endpoint_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List webhook deliveries with optional filters."""
    deliveries = _manager.list_deliveries(
        endpoint_id=endpoint_id,
        status=status,
        event_type=event_type,
        limit=limit,
    )
    return {"deliveries": deliveries, "total": len(deliveries)}


@router.get("/webhook-delivery/deliveries/{delivery_id}")
async def get_delivery(delivery_id: str):
    """Get a specific delivery with full attempt history."""
    delivery = _manager.get_delivery(delivery_id)
    if not delivery:
        raise HTTPException(404, "Delivery not found")
    return {"delivery": delivery.__dict__}


@router.post("/webhook-delivery/deliveries/{delivery_id}/attempt")
async def record_attempt(delivery_id: str, req: RecordAttemptRequest):
    """Record a delivery attempt result."""
    delivery = _manager.record_attempt(
        delivery_id=delivery_id,
        status_code=req.status_code,
        response_body=req.response_body,
        error=req.error,
        duration_ms=req.duration_ms,
    )
    if not delivery:
        raise HTTPException(404, "Delivery not found")
    return {"delivery": delivery.__dict__}


@router.post("/webhook-delivery/deliveries/{delivery_id}/cancel")
async def cancel_delivery(delivery_id: str):
    """Cancel a pending or retrying delivery."""
    if not _manager.cancel_delivery(delivery_id):
        raise HTTPException(400, "Cannot cancel delivery (not found or already completed)")
    return {"status": "cancelled", "delivery_id": delivery_id}


# ── Retry queue ───────────────────────────────────────────────────────

@router.get("/webhook-delivery/retries")
async def get_pending_retries():
    """Get deliveries ready for retry."""
    retries = _manager.get_pending_retries()
    return {"retries": retries, "count": len(retries)}


# ── Dead letter queue ─────────────────────────────────────────────────

@router.get("/webhook-delivery/dead-letter")
async def get_dead_letter_queue(limit: int = Query(50, ge=1, le=200)):
    """Get the dead letter queue (permanently failed deliveries)."""
    dlq = _manager.get_dead_letter_queue(limit)
    return {"dead_letters": dlq, "count": len(dlq)}


@router.post("/webhook-delivery/dead-letter/{delivery_id}/replay")
async def replay_dead_letter(delivery_id: str):
    """Replay a delivery from the dead letter queue."""
    delivery = _manager.replay_dead_letter(delivery_id)
    if not delivery:
        raise HTTPException(404, "Delivery not found")
    return {"delivery": delivery.__dict__, "status": "replayed"}


# ── Circuit breaker ───────────────────────────────────────────────────

@router.get("/webhook-delivery/circuits/{endpoint_id}")
async def get_circuit_state(endpoint_id: str):
    """Get circuit breaker state for an endpoint."""
    cb = _manager.get_circuit_state(endpoint_id)
    return {"circuit": cb.__dict__}


@router.post("/webhook-delivery/circuits/{endpoint_id}/reset")
async def reset_circuit(endpoint_id: str):
    """Manually reset a circuit breaker."""
    cb = _manager.reset_circuit(endpoint_id)
    return {"circuit": cb.__dict__, "status": "reset"}


# ── Statistics ────────────────────────────────────────────────────────

@router.get("/webhook-delivery/stats")
async def get_stats():
    """Get overall delivery statistics."""
    return {"stats": _manager.get_stats()}


@router.get("/webhook-delivery/stats/{endpoint_id}")
async def get_endpoint_stats(endpoint_id: str):
    """Get delivery stats for a specific endpoint."""
    return {"stats": _manager.get_endpoint_stats(endpoint_id)}


# ── Event types ───────────────────────────────────────────────────────

@router.get("/webhook-delivery/event-types")
async def get_event_types():
    """List supported webhook event types."""
    return {"event_types": WebhookDeliveryManager.get_event_types()}
