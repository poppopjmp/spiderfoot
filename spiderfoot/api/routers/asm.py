"""ASM (Attack Surface Management) API router.

Provides REST endpoints for the asset inventory, enabling
attack surface visualization, risk assessment, and asset management.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from spiderfoot.asm import (
    AssetInventory,
    AssetType,
    AssetRisk,
    AssetStatus,
)
from ..dependencies import get_api_key, SafeId

logger = logging.getLogger("spiderfoot.api.asm")

router = APIRouter(dependencies=[Depends(get_api_key)])

# Singleton inventory
_inventory = AssetInventory()


def get_inventory() -> AssetInventory:
    return _inventory


# ---------------------------------------------------------------------------
#  Request models
# ---------------------------------------------------------------------------

class IngestEventRequest(BaseModel):
    event_type: str
    data: str
    scan_id: str = ""
    module: str = ""


class IngestBatchRequest(BaseModel):
    events: list[IngestEventRequest]


class TagRequest(BaseModel):
    key: str
    value: str
    source: str = ""


class LinkRequest(BaseModel):
    asset_id_1: str
    asset_id_2: str


# ---------------------------------------------------------------------------
#  Endpoints
# ---------------------------------------------------------------------------

@router.get("/asm/assets", tags=["asm"])
async def list_assets(
    asset_type: str | None = Query(None, description="Filter by asset type"),
    risk: str | None = Query(None, description="Filter by risk level"),
    status: str | None = Query(None, description="Filter by status"),
    search: str = Query("", description="Search in asset values"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List assets in the attack surface inventory."""
    inv = get_inventory()

    at = AssetType(asset_type) if asset_type else None
    ar = AssetRisk(risk) if risk else None
    ast = AssetStatus(status) if status else None

    assets = inv.list_assets(
        asset_type=at, risk=ar, status=ast,
        search=search, limit=limit, offset=offset,
    )
    return {
        "assets": [a.to_dict() for a in assets],
        "total": inv.total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/asm/assets/{asset_id}", tags=["asm"])
async def get_asset(asset_id: SafeId):
    """Get a specific asset by ID."""
    asset = get_inventory().get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset.to_dict()


@router.get("/asm/summary", tags=["asm"])
async def asset_summary():
    """Get attack surface summary statistics."""
    return get_inventory().get_summary()


@router.post("/asm/ingest", tags=["asm"])
async def ingest_event(request: IngestEventRequest):
    """Ingest a single SpiderFoot event into the asset inventory."""
    asset = get_inventory().ingest_event(
        event_type=request.event_type,
        data=request.data,
        scan_id=request.scan_id,
        module=request.module,
    )
    if not asset:
        return {"status": "skipped", "reason": "unmapped event type"}
    return {"status": "ingested", "asset": asset.to_dict()}


@router.post("/asm/ingest/batch", tags=["asm"])
async def ingest_batch(request: IngestBatchRequest):
    """Ingest multiple events into the asset inventory."""
    inv = get_inventory()
    ingested = 0
    skipped = 0
    for event in request.events:
        asset = inv.ingest_event(
            event_type=event.event_type,
            data=event.data,
            scan_id=event.scan_id,
            module=event.module,
        )
        if asset:
            ingested += 1
        else:
            skipped += 1

    logger.info("ASM batch ingest: %d ingested, %d skipped", ingested, skipped)
    return {"ingested": ingested, "skipped": skipped, "total_assets": inv.total_count}


@router.post("/asm/assets/{asset_id}/tags", tags=["asm"])
async def add_tag(asset_id: SafeId, request: TagRequest):
    """Add a tag to an asset."""
    ok = get_inventory().add_tag(asset_id, request.key, request.value, request.source)
    if not ok:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "tagged"}


@router.post("/asm/link", tags=["asm"])
async def link_assets(request: LinkRequest):
    """Create a relationship between two assets."""
    ok = get_inventory().link_assets(request.asset_id_1, request.asset_id_2)
    if not ok:
        raise HTTPException(status_code=404, detail="One or both assets not found")
    return {"status": "linked"}


@router.delete("/asm/assets/{asset_id}", tags=["asm"])
async def delete_asset(asset_id: SafeId):
    """Delete an asset from the inventory."""
    ok = get_inventory().delete_asset(asset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "deleted"}


@router.post("/asm/assets/{asset_id}/remove", tags=["asm"])
async def mark_removed(asset_id: SafeId):
    """Mark an asset as removed from the attack surface."""
    ok = get_inventory().mark_removed(asset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "marked_removed"}


@router.get("/asm/types", tags=["asm"])
async def list_asset_types():
    """List all supported asset types."""
    return {
        "types": [{"value": t.value, "name": t.name} for t in AssetType],
    }


@router.get("/asm/risks", tags=["asm"])
async def list_risk_levels():
    """List all risk levels."""
    return {
        "risks": [{"value": r.value, "name": r.name} for r in AssetRisk],
    }
