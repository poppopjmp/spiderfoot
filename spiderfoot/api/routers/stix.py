"""STIX/TAXII API router for SpiderFoot.

Provides STIX 2.1 export and TAXII 2.1 compatible endpoints for
threat intelligence sharing.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from ..dependencies import get_api_key
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from spiderfoot.stix_export import STIXExporter, TAXIIServer

logger = logging.getLogger("spiderfoot.api.stix")

router = APIRouter(dependencies=[Depends(get_api_key)])

# Singleton TAXII server instance
_taxii_server = TAXIIServer()

TAXII_CONTENT_TYPE = "application/taxii+json;version=2.1"
STIX_CONTENT_TYPE = "application/stix+json;version=2.1"


# ---------------------------------------------------------------------------
#  Request/Response models
# ---------------------------------------------------------------------------

class STIXExportRequest(BaseModel):
    scan_id: str
    scan_name: str = "SpiderFoot Scan"
    scan_target: str = ""
    events: list[dict[str, Any]] = []


class STIXExportResponse(BaseModel):
    bundle: dict[str, Any]
    object_count: int
    collection_id: str | None = None


# ---------------------------------------------------------------------------
#  STIX export endpoints
# ---------------------------------------------------------------------------

@router.post("/stix/export", response_model=STIXExportResponse, tags=["stix"])
async def export_stix_bundle(request: STIXExportRequest):
    """Export scan events as a STIX 2.1 bundle.

    Accepts a list of SpiderFoot events and converts them into
    STIX 2.1 Cyber Observable and SDO objects.
    """
    exporter = STIXExporter(
        scan_id=request.scan_id,
        scan_name=request.scan_name,
        scan_target=request.scan_target,
    )

    converted = 0
    for event in request.events:
        event_type = event.get("type", "")
        data = event.get("data", "")
        module = event.get("module", "")
        source = event.get("source", "")
        stix_id = exporter.add_event(event_type, data, module, source)
        if stix_id:
            converted += 1

    bundle = exporter.export_bundle()

    # Register with TAXII server
    collection_id = _taxii_server.add_collection(
        request.scan_id, request.scan_name, bundle
    )

    logger.info(
        "STIX export: scan=%s objects=%d converted=%d collection=%s",
        request.scan_id, exporter.object_count, converted, collection_id,
    )

    return STIXExportResponse(
        bundle=bundle,
        object_count=exporter.object_count,
        collection_id=collection_id,
    )


@router.get("/stix/event-types", tags=["stix"])
async def list_supported_event_types():
    """List SpiderFoot event types that can be converted to STIX."""
    from spiderfoot.stix_export import _EVENT_TYPE_MAP
    return {
        "supported_event_types": {
            k: v for k, v in sorted(_EVENT_TYPE_MAP.items())
        },
        "total": len(_EVENT_TYPE_MAP),
    }


# ---------------------------------------------------------------------------
#  TAXII 2.1 endpoints
# ---------------------------------------------------------------------------

@router.get("/taxii2/", tags=["taxii"])
async def taxii_discovery():
    """TAXII 2.1 discovery endpoint."""
    return JSONResponse(
        content=_taxii_server.discovery(),
        media_type=TAXII_CONTENT_TYPE,
    )


@router.get("/taxii2/root/", tags=["taxii"])
async def taxii_api_root():
    """TAXII 2.1 API root information."""
    return JSONResponse(
        content=_taxii_server.api_root(),
        media_type=TAXII_CONTENT_TYPE,
    )


@router.get("/taxii2/collections/", tags=["taxii"])
async def taxii_list_collections():
    """List all available TAXII collections (one per scan)."""
    return JSONResponse(
        content=_taxii_server.list_collections(),
        media_type=TAXII_CONTENT_TYPE,
    )


@router.get("/taxii2/collections/{collection_id}/", tags=["taxii"])
async def taxii_get_collection(collection_id: str):
    """Get a specific TAXII collection."""
    col = _taxii_server.get_collection(collection_id)
    if col is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return JSONResponse(content=col, media_type=TAXII_CONTENT_TYPE)


@router.get("/taxii2/collections/{collection_id}/objects/", tags=["taxii"])
async def taxii_get_objects(
    collection_id: str,
    added_after: str | None = Query(None, description="Filter by creation time"),
    match_type: str | None = Query(None, alias="match[type]", description="Filter by STIX type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum objects to return"),
):
    """Get STIX objects from a TAXII collection.

    Supports filtering by type and creation time per TAXII 2.1 spec.
    """
    result = _taxii_server.get_objects(
        collection_id, added_after=added_after,
        match_type=match_type, limit=limit,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return JSONResponse(content=result, media_type=STIX_CONTENT_TYPE)


@router.get("/taxii2/collections/{collection_id}/objects/{object_id}/", tags=["taxii"])
async def taxii_get_object(collection_id: str, object_id: str):
    """Get a specific STIX object by ID from a collection."""
    obj = _taxii_server.get_object_by_id(collection_id, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return JSONResponse(content=obj, media_type=STIX_CONTENT_TYPE)
