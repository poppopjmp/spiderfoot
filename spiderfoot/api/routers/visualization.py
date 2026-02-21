"""
Visualization endpoints for SpiderFoot API.

Cycle 28 — delegates all data aggregation to ``VisualizationService``,
removing raw ``SpiderFootDb`` instantiation from the router.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, JSONResponse
import json
import logging

from ..dependencies import get_visualization_service, optional_auth, get_api_key, safe_filename
from spiderfoot import SpiderFootHelpers
from spiderfoot.reporting.visualization_service import VisualizationService, VisualizationServiceError

router = APIRouter(dependencies=[Depends(get_api_key)])
log = logging.getLogger(__name__)
optional_auth_dep = Depends(optional_auth)


# ------------------------------------------------------------------
# NOTE: static "/multi" route MUST come before "/{scan_id}" routes
# ------------------------------------------------------------------


@router.get("/visualization/graph/multi")
async def get_multi_scan_graph_data(
    scan_ids: str = Query(..., description="Comma-separated scan IDs"),
    api_key: str = optional_auth_dep,
    format: str = Query("gexf", description="Output format: json, gexf"),
    filter_type: str | None = Query(None, description="Filter by event type"),
    include_internal: bool = Query(False, description="Include internal events"),
    svc: VisualizationService = Depends(get_visualization_service),
) -> Response:
    """Generate graph visualization data for multiple scans."""
    try:
        scan_list = [s.strip() for s in scan_ids.split(",") if s.strip()]
        if not scan_list:
            raise HTTPException(status_code=400, detail="No valid scan IDs provided")

        valid_ids, all_results = svc.get_multi_scan_graph_data(
            scan_list, event_type=filter_type
        )
        if not all_results:
            raise HTTPException(status_code=404, detail="No valid scans found")

        if format.lower() == "gexf":
            graph_data = SpiderFootHelpers.buildGraphGexf(
                valid_ids, all_results, include_internal
            )
            return Response(
                content=graph_data,
                media_type="application/xml",
                headers={
                    "Content-Disposition": f"attachment; filename={safe_filename('multi_scan_graph.gexf')}"
                },
            )

        graph_data = SpiderFootHelpers.buildGraphJson(
            valid_ids, all_results, include_internal
        )
        return JSONResponse(
            content=json.loads(graph_data) if isinstance(graph_data, str) else graph_data
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to generate multi-scan graph: %s", e)
        raise HTTPException(
            status_code=500, detail="Failed to generate graph"
        )


@router.get("/visualization/graph/{scan_id}")
async def get_scan_graph_data(
    scan_id: str,
    api_key: str = optional_auth_dep,
    format: str = Query("json", description="Output format: json, gexf"),
    filter_type: str | None = Query(None, description="Filter by event type"),
    include_internal: bool = Query(False, description="Include internal events"),
    svc: VisualizationService = Depends(get_visualization_service),
) -> Response:
    """Generate graph visualization data for a scan."""
    try:
        _info, results = svc.get_graph_data(scan_id, event_type=filter_type)

        if format.lower() == "gexf":
            graph_data = SpiderFootHelpers.buildGraphGexf(
                [scan_id], results, include_internal
            )
            return Response(
                content=graph_data,
                media_type="application/xml",
                headers={
                    "Content-Disposition": f"attachment; filename={safe_filename(f'scan_{scan_id}_graph.gexf')}"
                },
            )

        graph_data = SpiderFootHelpers.buildGraphJson(
            [scan_id], results, include_internal
        )
        return JSONResponse(
            content=json.loads(graph_data) if isinstance(graph_data, str) else graph_data
        )

    except VisualizationServiceError as exc:
        log.warning("Scan not found: %s", exc)
        raise HTTPException(status_code=404, detail="Scan not found")
    except Exception as e:
        log.error("Failed to generate graph for scan %s: %s", scan_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to generate graph"
        )


@router.get("/visualization/summary/{scan_id}")
async def get_scan_summary_data(
    scan_id: str,
    api_key: str = optional_auth_dep,
    group_by: str = Query("type", description="Group results by: type, module, risk"),
    svc: VisualizationService = Depends(get_visualization_service),
) -> dict:
    """Get statistical summary data for visualization."""
    try:
        return svc.get_summary_data(scan_id, group_by=group_by)

    except VisualizationServiceError as exc:
        log.warning("Scan not found: %s", exc)
        raise HTTPException(status_code=404, detail="Scan not found")
    except Exception as e:
        log.error("Failed to get summary data for scan %s: %s", scan_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to get summary data"
        )


@router.get("/visualization/timeline/{scan_id}")
async def get_scan_timeline_data(
    scan_id: str,
    api_key: str = optional_auth_dep,
    interval: str = Query("hour", description="Time interval: hour, day, week"),
    event_type: str | None = Query(None, description="Filter by event type"),
    svc: VisualizationService = Depends(get_visualization_service),
) -> dict:
    """Get timeline data for scan events."""
    try:
        return svc.get_timeline_data(
            scan_id, interval=interval, event_type=event_type
        )

    except VisualizationServiceError as exc:
        log.warning("Scan not found: %s", exc)
        raise HTTPException(status_code=404, detail="Scan not found")
    except Exception as e:
        log.error("Failed to get timeline data for scan %s: %s", scan_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to get timeline data"
        )


@router.get("/visualization/heatmap/{scan_id}")
async def get_scan_heatmap_data(
    scan_id: str,
    api_key: str = optional_auth_dep,
    dimension_x: str = Query("module", description="X-axis dimension: module, type, risk"),
    dimension_y: str = Query("type", description="Y-axis dimension: module, type, risk"),
    svc: VisualizationService = Depends(get_visualization_service),
) -> dict:
    """Get heatmap data for scan results."""
    try:
        return svc.get_heatmap_data(
            scan_id, dimension_x=dimension_x, dimension_y=dimension_y
        )

    except VisualizationServiceError as exc:
        log.warning("Scan not found: %s", exc)
        raise HTTPException(status_code=404, detail="Scan not found")
    except Exception as e:
        log.error("Failed to get heatmap data for scan %s: %s", scan_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to get heatmap data"
        )
