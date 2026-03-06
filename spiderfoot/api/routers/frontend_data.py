"""Frontend Data API Router — exposes frontend_data.py service layer.

Provides endpoints for the React dashboard's advanced UI features:
  - Module health dashboard aggregation
  - Timeline event bucketing
  - Multi-dimensional result filtering with facets
  - Threat map geographic clustering
  - Scan diff summaries
  - Accessibility label registry
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..dependencies import optional_auth, get_api_key

router = APIRouter(dependencies=[Depends(get_api_key)])
log = logging.getLogger(__name__)


# ── Request/Response models ───────────────────────────────────────────


class ModuleHealthRequest(BaseModel):
    """Payload for /frontend/module-health."""
    metrics: list[dict[str, Any]] = Field(
        ...,
        description="List of module metric dicts with keys: "
                    "module_name, events_processed, events_produced, "
                    "error_count, total_duration, status",
    )


class TimelineRequest(BaseModel):
    """Payload for /frontend/timeline."""
    events: list[dict[str, Any]] = Field(
        ...,
        description="Raw event dicts with keys: timestamp, event_type, data, "
                    "module, scan_id, severity",
    )
    bucket_seconds: int = Field(3600, description="Bucket size in seconds")
    start: float | None = Field(None, description="Start timestamp filter")
    end: float | None = Field(None, description="End timestamp filter")
    event_type: str | None = Field(None, description="Filter by event type")
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=500)


class FilterRequest(BaseModel):
    """Payload for /frontend/results/filter."""
    results: list[dict[str, Any]] = Field(
        ..., description="Result dicts to filter",
    )
    event_types: list[str] | None = None
    modules: list[str] | None = None
    severity: str | None = None
    min_confidence: int | None = None
    data_pattern: str | None = None
    scan_ids: list[str] | None = None
    time_start: float | None = None
    time_end: float | None = None
    sort_key: str | None = None
    sort_order: str = "asc"
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=1, le=500)


class ThreatMapRequest(BaseModel):
    """Payload for /frontend/threat-map."""
    points: list[dict[str, Any]] = Field(
        ...,
        description="Geo data points with lat/longitude, label, event_type, "
                    "data, count, risk_level",
    )
    precision: int = Field(2, ge=0, le=6, description="Clustering precision")


class ScanDiffRequest(BaseModel):
    """Payload for /frontend/scan-diff."""
    added: list[dict[str, Any]] = Field(default_factory=list)
    removed: list[dict[str, Any]] = Field(default_factory=list)
    changed: list[dict[str, Any]] = Field(default_factory=list)
    unchanged_count: int = 0


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post(
    "/frontend/module-health",
    summary="Aggregate module health metrics for dashboard",
    tags=["frontend-data"],
)
async def module_health_dashboard(
    payload: ModuleHealthRequest,
    _auth=Depends(optional_auth),
):
    """Ingest raw module metrics and return a frontend-ready dashboard summary.

    The frontend calls this after collecting metrics from a scan to
    populate the module health panel.
    """
    try:
        from spiderfoot.services.frontend_data import ModuleHealthDashboard

        dashboard = ModuleHealthDashboard()
        for m in payload.metrics:
            dashboard.ingest(
                module_name=m.get("module_name", "unknown"),
                events_processed=m.get("events_processed", 0),
                events_produced=m.get("events_produced", 0),
                error_count=m.get("error_count", 0),
                total_duration=m.get("total_duration", 0.0),
                status=m.get("status", "unknown"),
            )
        return dashboard.get_summary()
    except Exception as e:
        log.error("Module health aggregation failed: %s", e)
        raise HTTPException(status_code=500, detail="Module health aggregation failed") from e


@router.post(
    "/frontend/timeline",
    summary="Build timeline event buckets",
    tags=["frontend-data"],
)
async def timeline_events(
    payload: TimelineRequest,
    _auth=Depends(optional_auth),
):
    """Ingest events and return time-bucketed data for the timeline chart."""
    try:
        from spiderfoot.services.frontend_data import TimelineService

        svc = TimelineService()
        added = svc.add_events(payload.events)

        events_page = svc.get_events(
            start=payload.start,
            end=payload.end,
            event_type=payload.event_type,
            page=payload.page,
            page_size=payload.page_size,
        )

        buckets = svc.bucket_by_interval(payload.bucket_seconds)

        return {
            "events_ingested": added,
            "events": events_page.to_dict(),
            "buckets": buckets,
        }
    except Exception as e:
        log.error("Timeline aggregation failed: %s", e)
        raise HTTPException(status_code=500, detail="Timeline aggregation failed") from e


@router.post(
    "/frontend/results/filter",
    summary="Multi-dimensional result filtering",
    tags=["frontend-data"],
)
async def filter_results(
    payload: FilterRequest,
    _auth=Depends(optional_auth),
):
    """Apply advanced filters to scan results and return paginated output with facets."""
    try:
        from spiderfoot.services.frontend_data import (
            ResultFilter,
            FilterCriteria,
            paginate,
            sort_dicts,
            SortOrder,
        )

        criteria = FilterCriteria(
            event_types=payload.event_types,
            modules=payload.modules,
            severity=payload.severity,
            min_confidence=payload.min_confidence,
            data_pattern=payload.data_pattern,
            scan_ids=payload.scan_ids,
            time_start=payload.time_start,
            time_end=payload.time_end,
        )

        filtered = ResultFilter.apply(payload.results, criteria)
        facets = ResultFilter.facets(filtered)

        if payload.sort_key:
            order = SortOrder.DESC if payload.sort_order == "desc" else SortOrder.ASC
            filtered = sort_dicts(filtered, payload.sort_key, order)

        page = paginate(filtered, payload.page, payload.page_size)

        return {
            "results": page.to_dict(),
            "facets": facets,
        }
    except Exception as e:
        log.error("Result filtering failed: %s", e)
        raise HTTPException(status_code=500, detail="Result filtering failed") from e


@router.post(
    "/frontend/threat-map",
    summary="Aggregate geographic threat data",
    tags=["frontend-data"],
)
async def threat_map(
    payload: ThreatMapRequest,
    _auth=Depends(optional_auth),
):
    """Ingest geo points and return clustered threat map data."""
    try:
        from spiderfoot.services.frontend_data import ThreatMapAggregator

        agg = ThreatMapAggregator()
        added = agg.add_points(payload.points)

        return {
            "total_points": agg.point_count,
            "clusters": agg.cluster(precision=payload.precision),
            "by_region": agg.by_region(),
            "risk_summary": agg.risk_summary(),
        }
    except Exception as e:
        log.error("Threat map aggregation failed: %s", e)
        raise HTTPException(status_code=500, detail="Threat map aggregation failed") from e


@router.post(
    "/frontend/scan-diff",
    summary="Format scan diff for frontend",
    tags=["frontend-data"],
)
async def scan_diff_summary(
    payload: ScanDiffRequest,
    _auth=Depends(optional_auth),
):
    """Format categorized scan changes into a frontend-ready diff summary."""
    try:
        from spiderfoot.services.frontend_data import ScanDiffSummary

        return ScanDiffSummary.from_changes(
            added=payload.added,
            removed=payload.removed,
            changed=payload.changed,
            unchanged_count=payload.unchanged_count,
        )
    except Exception as e:
        log.error("Scan diff summary failed: %s", e)
        raise HTTPException(status_code=500, detail="Scan diff summary failed") from e


@router.get(
    "/frontend/facets",
    summary="Compute result facets without filtering",
    tags=["frontend-data"],
)
async def get_facets(
    _auth=Depends(optional_auth),
):
    """Return empty facet structure for the filter UI initialization."""
    return {
        "event_types": {},
        "modules": {},
        "severities": {},
        "total": 0,
    }
