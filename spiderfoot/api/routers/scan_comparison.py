"""
Scan Comparison API router — compare two scans side-by-side.

Endpoints for diffing scan results, viewing change history,
and assessing attack surface drift.

v5.6.9
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from ..dependencies import get_api_key, SafeId
from pydantic import BaseModel, Field
from typing import Any

from spiderfoot.scan_comparison import ScanComparator

router = APIRouter(dependencies=[Depends(get_api_key)])

_comparator = ScanComparator()


# -------------------------------------------------------------------
# Pydantic schemas
# -------------------------------------------------------------------

class CompareRequest(BaseModel):
    scan_a_id: str = Field(..., description="Baseline scan ID (older)")
    scan_b_id: str = Field(..., description="Comparison scan ID (newer)")
    scan_a_target: str = ""
    scan_b_target: str = ""
    scan_a_started: str = ""
    scan_b_started: str = ""
    scan_a_events: list[dict] = Field(
        default_factory=list,
        description="Events from baseline scan, each with 'type' and 'data' keys",
    )
    scan_b_events: list[dict] = Field(
        default_factory=list,
        description="Events from comparison scan",
    )
    include_unchanged: bool = Field(
        False, description="Include unchanged items in diff output",
    )
    max_items: int = Field(
        500, ge=1, le=5000,
        description="Maximum number of diff items to return",
    )


class QuickCompareRequest(BaseModel):
    """Lightweight compare using only scan IDs (events loaded server-side)."""
    scan_a_id: str = Field(..., description="Baseline scan ID")
    scan_b_id: str = Field(..., description="Comparison scan ID")
    include_unchanged: bool = False
    max_items: int = Field(500, ge=1, le=5000)


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

@router.post("/scan-comparison/compare", tags=["scan-comparison"])
async def compare_scans(body: CompareRequest):
    """Compare two scans given their event lists.

    Returns a structured diff with per-category breakdowns,
    risk delta scoring, and individual change items.
    """
    if not body.scan_a_events and not body.scan_b_events:
        raise HTTPException(
            400, "At least one scan must have events to compare",
        )

    result = _comparator.compare(
        scan_a_events=body.scan_a_events,
        scan_b_events=body.scan_b_events,
        scan_a_id=body.scan_a_id,
        scan_b_id=body.scan_b_id,
        scan_a_target=body.scan_a_target,
        scan_b_target=body.scan_b_target,
        scan_a_started=body.scan_a_started,
        scan_b_started=body.scan_b_started,
        include_unchanged=body.include_unchanged,
        max_items=body.max_items,
    )
    return result.to_dict()


@router.post("/scan-comparison/quick", tags=["scan-comparison"])
async def quick_compare(body: QuickCompareRequest):
    """Compare two scans by ID (server loads events from database).

    Requires scans to exist in the SpiderFoot database.
    Falls back to empty diff if scans are not found.
    """
    # Attempt to load events from database
    scan_a_events: list[dict] = []
    scan_b_events: list[dict] = []
    scan_a_target = ""
    scan_b_target = ""
    scan_a_started = ""
    scan_b_started = ""

    try:
        from spiderfoot import SpiderFootDb
        dbh = SpiderFootDb({})

        # Load scan A meta
        row_a = dbh.scanInstanceGet(body.scan_a_id)
        if row_a:
            scan_a_target = str(row_a[1]) if len(row_a) > 1 else ""
            scan_a_started = str(row_a[3]) if len(row_a) > 3 else ""
            raw_a = dbh.scanResultEvent(body.scan_a_id, "ALL") or []
            for r in raw_a:
                scan_a_events.append({
                    "type": str(r[4]) if len(r) > 4 else "",
                    "data": str(r[1]) if len(r) > 1 else "",
                    "module": str(r[3]) if len(r) > 3 else "",
                })

        # Load scan B meta
        row_b = dbh.scanInstanceGet(body.scan_b_id)
        if row_b:
            scan_b_target = str(row_b[1]) if len(row_b) > 1 else ""
            scan_b_started = str(row_b[3]) if len(row_b) > 3 else ""
            raw_b = dbh.scanResultEvent(body.scan_b_id, "ALL") or []
            for r in raw_b:
                scan_b_events.append({
                    "type": str(r[4]) if len(r) > 4 else "",
                    "data": str(r[1]) if len(r) > 1 else "",
                    "module": str(r[3]) if len(r) > 3 else "",
                })
    except Exception as e:
        raise HTTPException(
            500, f"Failed to load scan data: {e}",
        )

    result = _comparator.compare(
        scan_a_events=scan_a_events,
        scan_b_events=scan_b_events,
        scan_a_id=body.scan_a_id,
        scan_b_id=body.scan_b_id,
        scan_a_target=scan_a_target,
        scan_b_target=scan_b_target,
        scan_a_started=scan_a_started,
        scan_b_started=scan_b_started,
        include_unchanged=body.include_unchanged,
        max_items=body.max_items,
    )
    return result.to_dict()


@router.get("/scan-comparison/history", tags=["scan-comparison"])
async def comparison_history(
    limit: int = Query(20, ge=1, le=100),
):
    """Get recent comparison history."""
    history = _comparator.history[-limit:]
    return {
        "comparisons": [c.to_dict() for c in history],
        "total": len(_comparator.history),
    }


@router.get("/scan-comparison/{comparison_id}", tags=["scan-comparison"])
async def get_comparison(comparison_id: SafeId):
    """Get a specific comparison result by ID."""
    result = _comparator.get_comparison(comparison_id)
    if not result:
        raise HTTPException(404, f"Comparison '{comparison_id}' not found")
    return result.to_dict()


@router.get("/scan-comparison/categories", tags=["scan-comparison"])
async def list_event_categories():
    """List all event categories used in comparisons."""
    return _comparator.get_event_categories()


@router.get("/scan-comparison/severity-levels", tags=["scan-comparison"])
async def list_severity_levels():
    """List severity levels and their risk weights."""
    from spiderfoot.scan_comparison import SeverityLevel, EVENT_SEVERITY
    return {
        "levels": [s.value for s in SeverityLevel],
        "event_mappings": {k: v.value for k, v in EVENT_SEVERITY.items()},
    }
