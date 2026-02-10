"""
Scan router — all endpoints delegate to ``ScanService``.

Cycle 27 migrated 5 core endpoints.  Cycle 29 completes the migration
of all 25 endpoints, eliminating every raw ``SpiderFootDb`` call.
"""

from __future__ import annotations

import csv
import json
import logging
import multiprocessing as mp
import time
from copy import deepcopy
from io import BytesIO, StringIO
from typing import List, Optional

import openpyxl
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from spiderfoot import SpiderFootHelpers
from spiderfoot.scan_service.scanner import startSpiderFootScanner
from spiderfoot.scan_service_facade import ScanService, ScanServiceError
from spiderfoot.sflib.core import SpiderFoot

from ..dependencies import get_app_config, get_api_key, optional_auth, get_scan_service
from ..pagination import PaginationParams, paginate
from ..schemas import (
    ScanCreateResponse,
    ScanDeleteResponse,
    ScanStopResponse,
    ScanMetadataResponse,
    ScanNotesResponse,
    ScanRerunResponse,
    ScanCloneResponse,
    ScanTagsResponse,
    MessageResponse,
)

# Scan lifecycle hooks — best-effort, non-blocking
try:
    from spiderfoot.scan_hooks import get_scan_hooks
    _hooks = get_scan_hooks()
except Exception:
    _hooks = None  # type: ignore[assignment]

router = APIRouter()
log = logging.getLogger(__name__)

api_key_dep = Depends(get_api_key)
optional_auth_dep = Depends(optional_auth)


# -----------------------------------------------------------------------
# Request models
# -----------------------------------------------------------------------

class ScanRequest(BaseModel):
    name: str = Field(..., description="Name of the scan")
    target: str = Field(..., description="Target for the scan")
    modules: Optional[List[str]] = Field(None, description="List of module names to run")
    type_filter: Optional[List[str]] = Field(None, description="List of event types to include")


class ScheduleCreateRequest(BaseModel):
    """Request to create a recurring scan schedule."""
    name: str = Field(..., description="Schedule name")
    target: str = Field(..., description="Scan target")
    interval_minutes: int = Field(0, ge=0, description="Run every N minutes (0 = one-shot)")
    run_at: Optional[float] = Field(None, description="Unix timestamp for one-shot execution")
    modules: Optional[List[str]] = Field(None, description="Module list")
    type_filter: Optional[List[str]] = Field(None, description="Event type filter")
    max_runs: int = Field(0, ge=0, description="Max runs (0 = unlimited)")
    description: str = ""
    tags: Optional[List[str]] = None


# -----------------------------------------------------------------------
# Background task helper
# -----------------------------------------------------------------------

async def start_scan_background(
    scan_id: str,
    scan_name: str,
    target: str,
    target_type: str,
    modules: list,
    type_filter: list,
    config: dict,
):
    try:
        startSpiderFootScanner(
            None, scan_name, scan_id, target, target_type, modules, config,
        )
    except Exception as e:
        log.error("Failed to start scan %s: %s", scan_id, e)


# -----------------------------------------------------------------------
# Static routes (MUST come before parameterized routes)
# -----------------------------------------------------------------------


@router.get("/scans/export-multi")
async def export_scan_json_multi(
    ids: str,
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Export event results for multiple scans as JSON."""
    scaninfo: list = []
    scan_name = ""

    for scan_id in ids.split(","):
        scan_id = scan_id.strip()
        if not scan_id:
            continue
        record = svc.get_scan(scan_id)
        if record is None:
            continue
        scan_name = record.name
        for row in svc.get_events(scan_id):
            if row[4] == "ROOT":
                continue
            lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
            event_data = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
            scaninfo.append({
                "data": event_data,
                "event_type": row[4],
                "module": str(row[3]),
                "source_data": str(row[2]),
                "false_positive": row[13] if len(row) > 13 else None,
                "last_seen": lastseen,
                "scan_name": record.name,
                "scan_target": record.target,
            })

    id_list = [s.strip() for s in ids.split(",") if s.strip()]
    if len(id_list) > 1 or not scan_name:
        fname = "SpiderFoot.json"
    else:
        fname = f"{scan_name}-SpiderFoot.json"

    return StreamingResponse(
        iter([json.dumps(scaninfo, ensure_ascii=False)]),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}", "Pragma": "no-cache"},
    )


@router.get("/scans/viz-multi")
async def export_scan_viz_multi(
    ids: str,
    gexf: str = "1",
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Export entities from multiple scans in GEXF format."""
    if not ids:
        raise HTTPException(status_code=400, detail="No scan IDs provided")

    data: list = []
    roots: list = []
    scan_name = ""

    for scan_id in ids.split(","):
        scan_id = scan_id.strip()
        if not scan_id:
            continue
        record = svc.get_scan(scan_id)
        if record is None:
            continue
        data += svc.get_events(scan_id, filter_fp=True)
        roots.append(record.target)
        scan_name = record.name

    if not data:
        raise HTTPException(status_code=404, detail="No data found for these scans")

    if gexf == "0":
        raise HTTPException(status_code=501, detail="Graph JSON for multi-scan not implemented")

    id_list = [s.strip() for s in ids.split(",") if s.strip()]
    fname = (
        f"{scan_name}-SpiderFoot.gexf"
        if len(id_list) == 1 and scan_name
        else "SpiderFoot.gexf"
    )
    gexf_data = SpiderFootHelpers.buildGraphGexf(roots, "SpiderFoot Export", data)
    return Response(
        gexf_data,
        media_type="application/gexf",
        headers={"Content-Disposition": f"attachment; filename={fname}", "Pragma": "no-cache"},
    )


@router.post("/scans/rerun-multi")
async def rerun_scan_multi(
    ids: str,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Rerun multiple scans."""
    config = get_app_config()
    cfg = deepcopy(config.get_config())
    dbh = svc.dbh
    new_scan_ids: list = []

    for scan_id in ids.split(","):
        scan_id = scan_id.strip()
        if not scan_id:
            continue
        record = svc.get_scan(scan_id)
        if record is None:
            continue
        scanconfig = dbh.scanConfigGet(scan_id)
        if not record.target or not scanconfig:
            continue
        modlist = scanconfig["_modulesenabled"].split(",")
        if "sfp__stor_stdout" in modlist:
            modlist.remove("sfp__stor_stdout")
        target_type = SpiderFootHelpers.targetTypeFromString(record.target)
        if target_type is None:
            continue
        new_scan_id = SpiderFootHelpers.genScanInstanceId()
        try:
            p = mp.Process(
                target=startSpiderFootScanner,
                args=(None, record.name, new_scan_id, record.target, target_type, modlist, cfg),
            )
            p.daemon = True
            p.start()
        except Exception:
            continue
        while dbh.scanInstanceGet(new_scan_id) is None:
            time.sleep(1)
        new_scan_ids.append(new_scan_id)

    return {"new_scan_ids": new_scan_ids, "message": f"{len(new_scan_ids)} scans rerun started"}


# -----------------------------------------------------------------------
# Bulk operations
# -----------------------------------------------------------------------

class BulkScanRequest(BaseModel):
    """Request body for bulk scan operations."""
    scan_ids: List[str] = Field(..., description="List of scan IDs to operate on", min_length=1, max_length=100)


@router.post("/scans/bulk/stop")
async def bulk_stop_scans(
    request: BulkScanRequest,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Stop multiple scans in one request."""
    results = {"stopped": [], "not_found": [], "already_finished": [], "errors": []}
    for scan_id in request.scan_ids:
        try:
            record = svc.get_scan(scan_id)
            if record is None:
                results["not_found"].append(scan_id)
                continue
            status = record.status if hasattr(record, "status") else str(record)
            if status in (DB_STATUS_FINISHED, DB_STATUS_ABORTED, DB_STATUS_ERROR_FAILED):
                results["already_finished"].append(scan_id)
                continue
            svc.stop_scan(scan_id)
            results["stopped"].append(scan_id)
            if _hooks:
                try:
                    _hooks.on_stopped(scan_id)
                except Exception as e:
                    log.debug("on_stopped hook failed for scan %s: %s", scan_id, e)
        except Exception as e:
            log.error("Bulk stop failed for %s: %s", scan_id, e)
            results["errors"].append({"scan_id": scan_id, "error": str(e)})
    return {
        **results,
        "summary": {
            "stopped": len(results["stopped"]),
            "not_found": len(results["not_found"]),
            "already_finished": len(results["already_finished"]),
            "errors": len(results["errors"]),
        },
    }


@router.post("/scans/bulk/delete")
async def bulk_delete_scans(
    request: BulkScanRequest,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Delete multiple scans in one request."""
    results = {"deleted": [], "not_found": [], "errors": []}
    for scan_id in request.scan_ids:
        try:
            record = svc.get_scan(scan_id)
            if record is None:
                results["not_found"].append(scan_id)
                continue
            svc.delete_scan(scan_id)
            results["deleted"].append(scan_id)
            if _hooks:
                try:
                    _hooks.on_deleted(scan_id)
                except Exception as e:
                    log.debug("on_deleted hook failed for scan %s: %s", scan_id, e)
        except Exception as e:
            log.error("Bulk delete failed for %s: %s", scan_id, e)
            results["errors"].append({"scan_id": scan_id, "error": str(e)})
    return {
        **results,
        "summary": {
            "deleted": len(results["deleted"]),
            "not_found": len(results["not_found"]),
            "errors": len(results["errors"]),
        },
    }


@router.post("/scans/bulk/archive")
async def bulk_archive_scans(
    request: BulkScanRequest,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Archive multiple scans in one request."""
    results = {"archived": [], "not_found": [], "errors": []}
    for scan_id in request.scan_ids:
        try:
            record = svc.get_scan(scan_id)
            if record is None:
                results["not_found"].append(scan_id)
                continue
            svc.archive(scan_id)
            results["archived"].append(scan_id)
            if _hooks:
                try:
                    _hooks.on_archived(scan_id)
                except Exception as e:
                    log.debug("on_archived hook failed for scan %s: %s", scan_id, e)
        except Exception as e:
            log.error("Bulk archive failed for %s: %s", scan_id, e)
            results["errors"].append({"scan_id": scan_id, "error": str(e)})
    return {
        **results,
        "summary": {
            "archived": len(results["archived"]),
            "not_found": len(results["not_found"]),
            "errors": len(results["errors"]),
        },
    }


# -----------------------------------------------------------------------
# Recurring scan schedules
# -----------------------------------------------------------------------

@router.get("/scans/schedules")
async def list_schedules(api_key: str = optional_auth_dep):
    """List all recurring scan schedules."""
    try:
        from spiderfoot.recurring_schedule import get_recurring_scheduler
        scheduler = get_recurring_scheduler()
        schedules = scheduler.list_all()
        return {
            "schedules": [s.to_dict() for s in schedules],
            "count": len(schedules),
            "stats": scheduler.stats(),
        }
    except Exception as e:
        log.error("Failed to list schedules: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list schedules") from e


@router.post("/scans/schedules", status_code=201)
async def create_schedule(
    body: ScheduleCreateRequest,
    api_key: str = api_key_dep,
):
    """Create a new recurring scan schedule."""
    if not body.interval_minutes and not body.run_at:
        raise HTTPException(
            status_code=422,
            detail="Either interval_minutes (>0) or run_at must be provided",
        )
    try:
        from spiderfoot.recurring_schedule import get_recurring_scheduler
        scheduler = get_recurring_scheduler()
        schedule = scheduler.add_schedule(
            name=body.name,
            target=body.target,
            interval_minutes=body.interval_minutes,
            run_at=body.run_at,
            modules=body.modules,
            type_filter=body.type_filter,
            max_runs=body.max_runs,
            description=body.description,
            tags=body.tags,
        )
        return {
            "schedule_id": schedule.schedule_id,
            "message": "Schedule created",
            **schedule.to_dict(),
        }
    except Exception as e:
        log.error("Failed to create schedule: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create schedule") from e


@router.get("/scans/schedules/{schedule_id}")
async def get_schedule(schedule_id: str, api_key: str = optional_auth_dep):
    """Get details of a specific scan schedule."""
    from spiderfoot.recurring_schedule import get_recurring_scheduler
    scheduler = get_recurring_scheduler()
    s = scheduler.get(schedule_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return s.to_dict()


@router.delete("/scans/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, api_key: str = api_key_dep):
    """Delete a scan schedule."""
    from spiderfoot.recurring_schedule import get_recurring_scheduler
    scheduler = get_recurring_scheduler()
    if not scheduler.remove(schedule_id):
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"schedule_id": schedule_id, "message": "Schedule deleted"}


@router.post("/scans/schedules/{schedule_id}/pause")
async def pause_schedule(schedule_id: str, api_key: str = api_key_dep):
    """Pause a recurring scan schedule."""
    from spiderfoot.recurring_schedule import get_recurring_scheduler
    scheduler = get_recurring_scheduler()
    if not scheduler.pause(schedule_id):
        raise HTTPException(status_code=404, detail="Schedule not found or not active")
    return {"schedule_id": schedule_id, "status": "paused"}


@router.post("/scans/schedules/{schedule_id}/resume")
async def resume_schedule(schedule_id: str, api_key: str = api_key_dep):
    """Resume a paused scan schedule."""
    from spiderfoot.recurring_schedule import get_recurring_scheduler
    scheduler = get_recurring_scheduler()
    if not scheduler.resume(schedule_id):
        raise HTTPException(status_code=404, detail="Schedule not found or not paused")
    s = scheduler.get(schedule_id)
    return {
        "schedule_id": schedule_id,
        "status": "active",
        "next_run_at": s.next_run_at if s else None,
    }


# -----------------------------------------------------------------------
# Parameterized (CRUD + lifecycle) routes
# -----------------------------------------------------------------------


@router.get("/scans")
async def list_scans(
    params: PaginationParams = Depends(),
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """List all scans with pagination."""
    try:
        records = svc.list_scans()
        dicts = [r.to_dict() for r in records]
        return paginate(dicts, params)
    except Exception as e:
        log.error("Failed to list scans: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list scans") from e


@router.get("/scans/search")
async def search_scans(
    target: Optional[str] = Query(None, description="Filter by target (substring match)"),
    status: Optional[str] = Query(None, description="Filter by status (RUNNING, FINISHED, ABORTED, etc.)"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    started_after: Optional[str] = Query(None, description="Scans started after this ISO timestamp"),
    started_before: Optional[str] = Query(None, description="Scans started before this ISO timestamp"),
    module: Optional[str] = Query(None, description="Scans that used this module"),
    sort_by: Optional[str] = Query("started", description="Sort field: started, target, status"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Search and filter scans by target, status, tags, date range, and module.

    Returns matching scans with facets (status counts, target summary).
    """
    try:
        records = svc.list_scans()
        dicts = [r.to_dict() for r in records]

        # Apply filters
        filtered = []
        for s in dicts:
            # Target substring match
            if target:
                scan_target = str(s.get("target", s.get("name", "")))
                if target.lower() not in scan_target.lower():
                    continue

            # Status match
            if status:
                scan_status = str(s.get("status", "")).upper()
                if scan_status != status.upper():
                    continue

            # Tag match
            if tag:
                meta = s.get("metadata", s.get("meta", {})) or {}
                scan_tags = meta.get(_TAGS_KEY, [])
                if tag.lower() not in [t.lower() for t in scan_tags]:
                    continue

            # Date range
            scan_started = s.get("started", s.get("created", 0))
            if started_after:
                try:
                    from datetime import datetime
                    threshold = datetime.fromisoformat(started_after.replace("Z", "+00:00")).timestamp()
                    if isinstance(scan_started, (int, float)) and scan_started < threshold:
                        continue
                except (ValueError, TypeError):
                    pass

            if started_before:
                try:
                    from datetime import datetime
                    threshold = datetime.fromisoformat(started_before.replace("Z", "+00:00")).timestamp()
                    if isinstance(scan_started, (int, float)) and scan_started > threshold:
                        continue
                except (ValueError, TypeError):
                    pass

            # Module filter
            if module:
                scan_modules = s.get("modules", s.get("module_list", []))
                if isinstance(scan_modules, str):
                    scan_modules = [m.strip() for m in scan_modules.split(",")]
                if module not in scan_modules:
                    continue

            filtered.append(s)

        # Build facets before pagination
        status_counts: dict = {}
        for s in filtered:
            st = str(s.get("status", "UNKNOWN")).upper()
            status_counts[st] = status_counts.get(st, 0) + 1

        # Sort
        sort_key = sort_by if sort_by in ("started", "target", "status") else "started"
        reverse = sort_order != "asc"
        filtered.sort(
            key=lambda s: s.get(sort_key, s.get("created", "")),
            reverse=reverse,
        )

        # Pagination
        total = len(filtered)
        page = filtered[offset : offset + limit]

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "scans": page,
            "facets": {
                "status": status_counts,
            },
        }
    except Exception as e:
        log.error("Failed to search scans: %s", e)
        raise HTTPException(status_code=500, detail="Failed to search scans") from e


@router.post("/scans", status_code=201, response_model=ScanCreateResponse)
async def create_scan(
    scan_request: ScanRequest,
    background_tasks: BackgroundTasks,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Create and start a new scan."""
    try:
        config = get_app_config()
        scan_id = SpiderFootHelpers.genScanInstanceId()
        target_type = SpiderFootHelpers.targetTypeFromString(scan_request.target)
        if not target_type:
            raise HTTPException(status_code=422, detail="Invalid target")

        sf = SpiderFoot(config.get_config())
        all_modules = sf.modulesProducing(["*"])
        modules = scan_request.modules if scan_request.modules else all_modules
        if not modules:
            modules = ["sfp__stor_db"]

        try:
            svc.create_scan(scan_id, scan_request.name, scan_request.target)
        except Exception as e:
            log.error("Failed to create scan instance: %s", e)
            raise HTTPException(
                status_code=500, detail="Unable to create scan instance in database"
            ) from e

        background_tasks.add_task(
            start_scan_background,
            scan_id,
            scan_request.name,
            scan_request.target,
            target_type,
            modules,
            scan_request.type_filter,
            config.get_config(),
        )
        return ScanCreateResponse(
            id=scan_id,
            name=scan_request.name,
            target=scan_request.target,
            status=DB_STATUS_STARTING,
            message="Scan created and starting",
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to create scan: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create scan") from e
    finally:
        if _hooks:
            try:
                _hooks.on_created(scan_id, scan_request.name, scan_request.target)
            except Exception as e:
                log.debug("on_created hook failed for scan %s: %s", scan_id, e)


@router.get("/scans/{scan_id}")
async def get_scan(
    scan_id: str,
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Get scan details."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    result = record.to_dict()
    try:
        result["state_machine"] = svc.get_scan_state(scan_id)
    except Exception as e:
        log.debug("Failed to retrieve state machine for scan %s: %s", scan_id, e)
    return result


@router.delete("/scans/{scan_id}", response_model=ScanDeleteResponse)
async def delete_scan(
    scan_id: str,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Delete a scan."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    svc.delete_scan(scan_id)
    if _hooks:
        try:
            _hooks.on_deleted(scan_id)
        except Exception as e:
            log.debug("on_deleted hook failed for scan %s: %s", scan_id, e)
    return ScanDeleteResponse()


@router.delete("/scans/{scan_id}/full", response_model=MessageResponse)
async def delete_scan_full(
    scan_id: str,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Delete a scan and all related data."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    svc.delete_scan_full(scan_id)
    return MessageResponse(message="Scan and all related data deleted successfully")


@router.post("/scans/{scan_id}/stop", response_model=ScanStopResponse)
async def stop_scan(
    scan_id: str,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Stop a running scan with state-machine validation."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    try:
        new_status = svc.stop_scan(scan_id)
        if _hooks:
            try:
                _hooks.on_aborted(scan_id, reason="API stop request")
            except Exception as e:
                log.debug("on_aborted hook failed for scan %s: %s", scan_id, e)
        return ScanStopResponse(message="Scan stopped successfully", status=new_status)
    except ScanServiceError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/scans/{scan_id}/retry")
async def retry_scan(
    scan_id: str,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Retry a failed or aborted scan by creating a new scan with the same configuration.

    The original scan is preserved for reference.  A new scan is created
    with the same target, modules, and configuration, and optionally
    started immediately.
    """
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    scan_dict = record.to_dict()
    status = str(scan_dict.get("status", "")).upper()

    # Only allow retry of non-running scans
    if status in (DB_STATUS_RUNNING, DB_STATUS_STARTING, DB_STATUS_STARTED):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry a scan in '{status}' state — stop it first",
        )

    try:
        from spiderfoot import SpiderFootHelpers

        # Get the original scan config
        dbh = svc._dbh if hasattr(svc, '_dbh') else None
        scan_config = {}
        original_target = scan_dict.get("target", scan_dict.get("name", ""))
        original_modules = scan_dict.get("modules", [])

        if dbh and hasattr(dbh, 'scanConfigGet'):
            try:
                scan_config = dbh.scanConfigGet(scan_id) or {}
            except Exception as e:
                log.debug("Failed to retrieve scan config for %s: %s", scan_id, e)

        new_scan_id = SpiderFootHelpers.genScanInstanceId()

        # Create the new scan entry
        if dbh and hasattr(dbh, 'scanInstanceCreate'):
            scan_name = f"{scan_dict.get('name', original_target)} (Retry)"
            dbh.scanInstanceCreate(new_scan_id, scan_name, original_target)
            if scan_config:
                dbh.scanConfigSet(new_scan_id, scan_config)

        # Copy metadata (including tags, annotations) from original
        try:
            original_meta = svc.get_metadata(scan_id) or {}
            if original_meta:
                retry_meta = dict(original_meta)
                retry_meta["_retry_of"] = scan_id
                retry_meta["_retry_reason"] = status
                svc.set_metadata(new_scan_id, retry_meta)
        except Exception as e:
            log.debug("Failed to copy metadata from scan %s to %s: %s", scan_id, new_scan_id, e)

        if _hooks:
            try:
                _hooks.on_created(new_scan_id, original_target)
            except Exception as e:
                log.debug("on_created hook failed for retry scan %s: %s", new_scan_id, e)

        return {
            "original_scan_id": scan_id,
            "original_status": status,
            "new_scan_id": new_scan_id,
            "target": original_target,
            "message": "New scan created from original configuration. Start it with POST /scans/{id}/start.",
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to retry scan %s: %s", scan_id, e)
        raise HTTPException(status_code=500, detail="Failed to retry scan") from e


# -----------------------------------------------------------------------
# Export endpoints
# -----------------------------------------------------------------------


@router.get("/scans/{scan_id}/events/export")
async def export_scan_event_results(
    scan_id: str,
    event_type: str = None,
    filetype: str = "csv",
    dialect: str = "excel",
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Export scan event result data as CSV or Excel."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    data = svc.get_events(scan_id, event_type if event_type else "ALL")
    rows = []
    for row in data:
        if row[4] == "ROOT":
            continue
        lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
        datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
        rows.append([lastseen, str(row[4]), str(row[3]), str(row[2]), row[13], datafield])

    headings = ["Updated", "Type", "Module", "Source", "F/P", "Data"]

    if filetype.lower() in ("xlsx", "excel"):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "EventResults"
        ws.append(headings)
        for r in rows:
            ws.append(r)
        with BytesIO() as f:
            wb.save(f)
            f.seek(0)
            return StreamingResponse(
                iter([f.read()]),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=SpiderFoot-{scan_id}-eventresults.xlsx",
                    "Pragma": "no-cache",
                },
            )

    if filetype.lower() == "csv":
        fileobj = StringIO()
        parser = csv.writer(fileobj, dialect=dialect)
        parser.writerow(headings)
        for r in rows:
            parser.writerow(r)
        fileobj.seek(0)
        return StreamingResponse(
            iter([fileobj.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=SpiderFoot-{scan_id}-eventresults.csv",
                "Pragma": "no-cache",
            },
        )

    raise HTTPException(status_code=400, detail="Invalid export filetype.")


@router.get("/scans/{scan_id}/search/export")
async def export_scan_search_results(
    scan_id: str,
    event_type: str = None,
    value: str = None,
    filetype: str = "csv",
    dialect: str = "excel",
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Export search result data as CSV or Excel."""
    data = []
    for row in svc.search_events(scan_id, event_type=event_type or "", value=value or ""):
        if len(row) < 12 or row[10] == "ROOT":
            continue
        datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
        data.append([row[0], str(row[10]), str(row[3]), str(row[2]), row[11], datafield])

    headings = ["Updated", "Type", "Module", "Source", "F/P", "Data"]

    if not data:
        raise HTTPException(status_code=404, detail="No search results found for this scan")

    if filetype.lower() in ("xlsx", "excel"):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "SearchResults"
        ws.append(headings)
        for r in data:
            ws.append(r)
        with BytesIO() as f:
            wb.save(f)
            f.seek(0)
            return StreamingResponse(
                iter([f.read()]),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=SpiderFoot-{scan_id}-searchresults.xlsx",
                    "Pragma": "no-cache",
                },
            )

    if filetype.lower() == "csv":
        fileobj = StringIO()
        parser = csv.writer(fileobj, dialect=dialect)
        parser.writerow(headings)
        for r in data:
            parser.writerow(r)
        fileobj.seek(0)
        return StreamingResponse(
            iter([fileobj.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=SpiderFoot-{scan_id}-searchresults.csv",
                "Pragma": "no-cache",
            },
        )

    raise HTTPException(status_code=400, detail="Invalid export filetype.")


@router.get("/scans/{scan_id}/viz")
async def export_scan_viz(
    scan_id: str,
    gexf: str = "0",
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Export entities from scan results for visualising (GEXF/graph)."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    data = svc.get_events(scan_id, filter_fp=True)

    if gexf == "0":
        graph_json = SpiderFootHelpers.buildGraphJson([record.target], data)
        return Response(graph_json, media_type="application/json")

    fname = f"{record.name}-SpiderFoot.gexf" if record.name else "SpiderFoot.gexf"
    gexf_data = SpiderFootHelpers.buildGraphGexf([record.target], "SpiderFoot Export", data)
    return Response(
        gexf_data,
        media_type="application/gexf",
        headers={"Content-Disposition": f"attachment; filename={fname}", "Pragma": "no-cache"},
    )


@router.get("/scans/{scan_id}/logs/export")
async def export_scan_logs(
    scan_id: str,
    dialect: str = "excel",
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Export scan logs as CSV."""
    try:
        data = svc.get_scan_logs(scan_id)
    except Exception as e:
        log.debug("Failed to export scan logs for %s: %s", scan_id, e)
        raise HTTPException(status_code=404, detail="Scan ID not found") from e

    if not data:
        raise HTTPException(status_code=404, detail="No scan logs found")

    fileobj = StringIO()
    parser = csv.writer(fileobj, dialect=dialect)
    parser.writerow(["Date", "Component", "Type", "Event", "Event ID"])
    for row in data:
        parser.writerow([str(x) for x in row])
    fileobj.seek(0)
    return StreamingResponse(
        iter([fileobj.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=SpiderFoot-{scan_id}.log.csv",
            "Pragma": "no-cache",
        },
    )


@router.get("/scans/{scan_id}/timeline")
async def get_scan_timeline(
    scan_id: str,
    limit: int = Query(200, ge=1, le=5000, description="Max timeline entries"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Get a chronological timeline of events for a scan.

    Returns events ordered by timestamp with module attribution,
    useful for understanding scan progression and discovery order.
    """
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    try:
        events = svc.get_events(scan_id) or []

        timeline = []
        for row in events:
            if isinstance(row, dict):
                et = row.get("type", row.get("eventType", ""))
                data = str(row.get("data", ""))
                module = row.get("module", "")
                ts = row.get("generated", row.get("lastSeen", 0))
            elif isinstance(row, (list, tuple)):
                ts = row[0] if len(row) > 0 else 0
                data = str(row[1]) if len(row) > 1 else ""
                module = str(row[3]) if len(row) > 3 else ""
                et = str(row[4]) if len(row) > 4 else ""
            else:
                continue

            if et == "ROOT":
                continue
            if event_type and et != event_type:
                continue

            # Clean up SFURL markers
            data = data.replace("<SFURL>", "").replace("</SFURL>", "")

            timeline.append({
                "timestamp": ts,
                "event_type": et,
                "data": data[:500],  # Truncate large data
                "module": module,
            })

        # Sort by timestamp (ascending = chronological)
        timeline.sort(key=lambda e: e["timestamp"])
        timeline = timeline[:limit]

        # Summary statistics
        type_counts = {}
        module_counts = {}
        for entry in timeline:
            type_counts[entry["event_type"]] = type_counts.get(entry["event_type"], 0) + 1
            module_counts[entry["module"]] = module_counts.get(entry["module"], 0) + 1

        return {
            "scan_id": scan_id,
            "total_events": len(events),
            "timeline_entries": len(timeline),
            "timeline": timeline,
            "summary": {
                "event_types": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
                "modules": dict(sorted(module_counts.items(), key=lambda x: -x[1])),
                "first_event": timeline[0]["timestamp"] if timeline else None,
                "last_event": timeline[-1]["timestamp"] if timeline else None,
            },
        }
    except Exception as e:
        log.error("Failed to get scan timeline for %s: %s", scan_id, e)
        raise HTTPException(status_code=500, detail="Failed to build scan timeline") from e


@router.get("/scans/{scan_id}/dedup")
async def detect_duplicate_events(
    scan_id: str,
    threshold: int = Query(2, ge=2, le=100, description="Min occurrences to flag as duplicate"),
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Detect duplicate events in scan results.

    Finds events with identical (event_type, data) pairs across modules,
    helping identify redundant data collection and module overlap.
    """
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    try:
        events = svc.get_events(scan_id) or []

        # Build fingerprint → occurrences map
        fingerprints: dict = {}  # (event_type, data_hash) → list of sources
        for row in events:
            if isinstance(row, dict):
                et = row.get("type", row.get("eventType", ""))
                data = str(row.get("data", ""))
                module = row.get("module", "")
            elif isinstance(row, (list, tuple)):
                data = str(row[1]) if len(row) > 1 else ""
                module = str(row[3]) if len(row) > 3 else ""
                et = str(row[4]) if len(row) > 4 else ""
            else:
                continue

            if et == "ROOT":
                continue

            key = (et, data[:500])
            if key not in fingerprints:
                fingerprints[key] = []
            fingerprints[key].append(module)

        # Filter to duplicates only
        duplicates = []
        for (et, data_preview), modules in fingerprints.items():
            if len(modules) >= threshold:
                duplicates.append({
                    "event_type": et,
                    "data": data_preview[:200],
                    "occurrences": len(modules),
                    "modules": list(set(modules)),
                })

        duplicates.sort(key=lambda d: -d["occurrences"])

        total_events = len(events)
        total_dup_events = sum(d["occurrences"] for d in duplicates)

        return {
            "scan_id": scan_id,
            "total_events": total_events,
            "unique_fingerprints": len(fingerprints),
            "duplicate_groups": len(duplicates),
            "duplicate_event_count": total_dup_events,
            "dedup_ratio": round(1 - len(fingerprints) / max(total_events, 1), 4),
            "duplicates": duplicates[:200],
        }
    except Exception as e:
        log.error("Failed to detect duplicates for %s: %s", scan_id, e)
        raise HTTPException(status_code=500, detail="Failed to detect duplicates") from e


@router.get("/scans/{scan_id}/correlations/export")
async def export_scan_correlations(
    scan_id: str,
    filetype: str = "csv",
    dialect: str = "excel",
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Export scan correlation data as CSV or Excel."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    try:
        data = svc.get_correlations(scan_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Scan ID not found")

    headings = ["Rule Name", "Correlation", "Risk", "Description"]

    if filetype.lower() in ("xlsx", "excel"):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Correlations"
        ws.append(headings)
        for row in data:
            ws.append(row)
        with BytesIO() as f:
            wb.save(f)
            f.seek(0)
            return StreamingResponse(
                iter([f.read()]),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=SpiderFoot-{scan_id}-correlations.xlsx",
                    "Pragma": "no-cache",
                },
            )

    if filetype.lower() == "csv":
        fileobj = StringIO()
        parser = csv.writer(fileobj, dialect=dialect)
        parser.writerow(headings)
        for row in data:
            parser.writerow([str(x) for x in row])
        fileobj.seek(0)
        return StreamingResponse(
            iter([fileobj.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=SpiderFoot-{scan_id}-correlations.csv",
                "Pragma": "no-cache",
            },
        )

    raise HTTPException(status_code=400, detail="Invalid export filetype.")


# -----------------------------------------------------------------------
# Lifecycle (rerun, clone)
# -----------------------------------------------------------------------


@router.get("/scans/{scan_id}/options")
async def get_scan_options(
    scan_id: str,
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Return configuration used for the specified scan."""
    config = get_app_config()
    ret = svc.get_scan_options(scan_id, config.get_config())
    return ret


@router.post("/scans/{scan_id}/rerun", response_model=ScanRerunResponse)
async def rerun_scan(
    scan_id: str,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Rerun a scan."""
    config = get_app_config()
    cfg = deepcopy(config.get_config())
    dbh = svc.dbh

    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Invalid scan ID.")
    if not record.target:
        raise HTTPException(status_code=400, detail=f"Scan {scan_id} has no target defined.")

    scanconfig = dbh.scanConfigGet(scan_id)
    if not scanconfig:
        raise HTTPException(status_code=400, detail=f"Error loading config from scan: {scan_id}")

    modlist = scanconfig["_modulesenabled"].split(",")
    if "sfp__stor_stdout" in modlist:
        modlist.remove("sfp__stor_stdout")

    target_type = SpiderFootHelpers.targetTypeFromString(record.target)
    if not target_type:
        target_type = SpiderFootHelpers.targetTypeFromString(f'"{record.target}"')
    if not target_type:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot determine target type for scan rerun. Target '{record.target}' is not recognized.",
        )

    scantarget = record.target
    if target_type not in ("HUMAN_NAME", "BITCOIN_ADDRESS"):
        scantarget = scantarget.lower()

    new_scan_id = SpiderFootHelpers.genScanInstanceId()
    try:
        p = mp.Process(
            target=startSpiderFootScanner,
            args=(None, record.name, new_scan_id, scantarget, target_type, modlist, cfg),
        )
        p.daemon = True
        p.start()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan [{new_scan_id}] failed: {e}")

    while dbh.scanInstanceGet(new_scan_id) is None:
        time.sleep(1)

    return ScanRerunResponse(new_scan_id=new_scan_id)


@router.post("/scans/{scan_id}/clone", response_model=ScanCloneResponse)
async def clone_scan(
    scan_id: str,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Clone a scan configuration (without running it)."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Invalid scan ID.")

    dbh = svc.dbh
    scanconfig = dbh.scanConfigGet(scan_id)
    if not scanconfig:
        raise HTTPException(status_code=400, detail=f"Error loading config from scan: {scan_id}")

    modlist = scanconfig["_modulesenabled"].split(",")
    if "sfp__stor_stdout" in modlist:
        modlist.remove("sfp__stor_stdout")

    target_type = SpiderFootHelpers.targetTypeFromString(record.target)
    if not target_type:
        target_type = SpiderFootHelpers.targetTypeFromString(f'"{record.target}"')
    if not target_type:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot determine target type for scan clone. Target '{record.target}' is not recognized.",
        )

    scantarget = record.target
    if target_type not in ("HUMAN_NAME", "BITCOIN_ADDRESS"):
        scantarget = scantarget.lower()

    new_scan_id = SpiderFootHelpers.genScanInstanceId()
    try:
        dbh.scanInstanceCreate(new_scan_id, f"{record.name} (Clone)", scantarget)
        dbh.scanConfigSet(new_scan_id, scanconfig)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan [{new_scan_id}] clone failed: {e}") from e

    return ScanCloneResponse(new_scan_id=new_scan_id)


# -----------------------------------------------------------------------
# Event annotations (per-result notes/comments)
# -----------------------------------------------------------------------

_ANNOTATIONS_KEY = "_annotations"


@router.get("/scans/{scan_id}/annotations")
async def list_event_annotations(
    scan_id: str,
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """List all event annotations for a scan.

    Annotations are operator notes attached to individual scan result
    events, identified by result ID.
    """
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    meta = svc.get_metadata(scan_id) or {}
    annotations = meta.get(_ANNOTATIONS_KEY, {})
    return {
        "scan_id": scan_id,
        "total": len(annotations),
        "annotations": annotations,
    }


@router.put("/scans/{scan_id}/annotations/{result_id}")
async def set_event_annotation(
    scan_id: str,
    result_id: str,
    note: str = Body(..., embed=True, max_length=2000),
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Add or update an annotation on a specific scan result event.

    Args:
        result_id: The unique ID of the scan result event.
        note: The annotation text (max 2000 chars).
    """
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    import time as _time
    meta = svc.get_metadata(scan_id) or {}
    annotations = meta.get(_ANNOTATIONS_KEY, {})

    is_new = result_id not in annotations
    annotations[result_id] = {
        "note": note.strip(),
        "updated_at": _time.time(),
    }
    meta[_ANNOTATIONS_KEY] = annotations
    svc.set_metadata(scan_id, meta)

    return {
        "scan_id": scan_id,
        "result_id": result_id,
        "action": "created" if is_new else "updated",
        "annotation": annotations[result_id],
    }


@router.delete("/scans/{scan_id}/annotations/{result_id}")
async def delete_event_annotation(
    scan_id: str,
    result_id: str,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Remove an annotation from a scan result event."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    meta = svc.get_metadata(scan_id) or {}
    annotations = meta.get(_ANNOTATIONS_KEY, {})

    if result_id not in annotations:
        raise HTTPException(status_code=404, detail="Annotation not found")

    del annotations[result_id]
    meta[_ANNOTATIONS_KEY] = annotations
    svc.set_metadata(scan_id, meta)

    return {"scan_id": scan_id, "result_id": result_id, "deleted": True}


# -----------------------------------------------------------------------
# Results management
# -----------------------------------------------------------------------


@router.post("/scans/{scan_id}/results/falsepositive")
async def set_results_false_positive(
    scan_id: str,
    resultids: List[str] = Body(...),
    fp: str = Body(...),
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Set a batch of results as false positive or not."""
    if fp not in ("0", "1"):
        raise HTTPException(status_code=400, detail="No FP flag set or not set correctly.")

    try:
        return svc.set_false_positive(scan_id, resultids, fp)
    except ScanServiceError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/scans/{scan_id}/clear", response_model=MessageResponse)
async def clear_scan(
    scan_id: str,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Remove all results/events for a scan, keeping the scan entry."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    try:
        svc.clear_results(scan_id)
        return MessageResponse(message="Scan results cleared (scan entry retained)")
    except Exception as e:
        log.error("Failed to clear scan %s: %s", scan_id, e)
        raise HTTPException(status_code=500, detail="Failed to clear scan results") from e


# -----------------------------------------------------------------------
# Metadata / notes / archive
# -----------------------------------------------------------------------


@router.get("/scans/{scan_id}/metadata", response_model=ScanMetadataResponse)
async def get_scan_metadata(
    scan_id: str,
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Get scan metadata."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanMetadataResponse(metadata=svc.get_metadata(scan_id))


@router.patch("/scans/{scan_id}/metadata")
async def update_scan_metadata(
    scan_id: str,
    metadata: dict = Body(...),
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Update scan metadata (key/value pairs)."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=422, detail="Metadata must be a dictionary")
    svc.set_metadata(scan_id, metadata)
    return {"success": True, "metadata": metadata}


@router.get("/scans/{scan_id}/notes", response_model=ScanNotesResponse)
async def get_scan_notes(
    scan_id: str,
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Get scan notes/comments."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanNotesResponse(notes=svc.get_notes(scan_id))


@router.patch("/scans/{scan_id}/notes")
async def update_scan_notes(
    scan_id: str,
    notes: str = Body(...),
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Update scan notes/comments."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    svc.set_notes(scan_id, notes)
    return {"success": True, "notes": notes}


@router.post("/scans/{scan_id}/archive", response_model=MessageResponse)
async def archive_scan(
    scan_id: str,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Archive a scan."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    svc.archive(scan_id)
    if _hooks:
        try:
            _hooks.on_archived(scan_id)
        except Exception:
            pass
    return MessageResponse(message="Scan archived")


@router.post("/scans/{scan_id}/unarchive", response_model=MessageResponse)
async def unarchive_scan(
    scan_id: str,
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Unarchive a scan."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    svc.unarchive(scan_id)
    if _hooks:
        try:
            _hooks.on_unarchived(scan_id)
        except Exception:
            pass
    return MessageResponse(message="Scan unarchived")


# -----------------------------------------------------------------------
# Scan tags / labels
# -----------------------------------------------------------------------

_TAGS_KEY = "_tags"


@router.get("/scans/{scan_id}/tags", response_model=ScanTagsResponse)
async def get_scan_tags(
    scan_id: str,
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Get all tags for a scan."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    meta = svc.get_metadata(scan_id) or {}
    tags = meta.get(_TAGS_KEY, [])
    return ScanTagsResponse(scan_id=scan_id, tags=tags)


@router.put("/scans/{scan_id}/tags", response_model=ScanTagsResponse)
async def set_scan_tags(
    scan_id: str,
    tags: List[str] = Body(..., description="Complete list of tags to set"),
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Replace all tags for a scan."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    # Normalize: strip, lowercase, deduplicate, remove empty
    clean = sorted(set(t.strip().lower() for t in tags if t.strip()))
    if len(clean) > 50:
        raise HTTPException(status_code=422, detail="Maximum 50 tags per scan")
    meta = svc.get_metadata(scan_id) or {}
    meta[_TAGS_KEY] = clean
    svc.set_metadata(scan_id, meta)
    return ScanTagsResponse(scan_id=scan_id, tags=clean, message="Tags updated")


@router.post("/scans/{scan_id}/tags", response_model=ScanTagsResponse)
async def add_scan_tags(
    scan_id: str,
    tags: List[str] = Body(..., description="Tags to add"),
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Add tags to a scan (merges with existing)."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    meta = svc.get_metadata(scan_id) or {}
    existing = set(meta.get(_TAGS_KEY, []))
    new_tags = set(t.strip().lower() for t in tags if t.strip())
    merged = sorted(existing | new_tags)
    if len(merged) > 50:
        raise HTTPException(status_code=422, detail="Maximum 50 tags per scan")
    meta[_TAGS_KEY] = merged
    svc.set_metadata(scan_id, meta)
    added = sorted(new_tags - existing)
    return ScanTagsResponse(
        scan_id=scan_id, tags=merged,
        message=f"Added {len(added)} tag(s)" if added else "No new tags added",
    )


@router.delete("/scans/{scan_id}/tags", response_model=ScanTagsResponse)
async def remove_scan_tags(
    scan_id: str,
    tags: List[str] = Body(..., description="Tags to remove"),
    api_key: str = api_key_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Remove specific tags from a scan."""
    record = svc.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    meta = svc.get_metadata(scan_id) or {}
    existing = set(meta.get(_TAGS_KEY, []))
    to_remove = set(t.strip().lower() for t in tags if t.strip())
    remaining = sorted(existing - to_remove)
    removed = sorted(existing & to_remove)
    meta[_TAGS_KEY] = remaining
    svc.set_metadata(scan_id, meta)
    return ScanTagsResponse(
        scan_id=scan_id, tags=remaining,
        message=f"Removed {len(removed)} tag(s)" if removed else "No matching tags found",
    )
from spiderfoot.scan_state_map import (
    DB_STATUS_ABORTED,
    DB_STATUS_ERROR_FAILED,
    DB_STATUS_FINISHED,
    DB_STATUS_RUNNING,
    DB_STATUS_STARTED,
    DB_STATUS_STARTING,
)


# -----------------------------------------------------------------------
# Scan comparison
# -----------------------------------------------------------------------


@router.get("/scans/compare")
async def compare_scans(
    scan_a: str = Query(..., description="First scan ID"),
    scan_b: str = Query(..., description="Second scan ID"),
    api_key: str = optional_auth_dep,
    svc: ScanService = Depends(get_scan_service),
):
    """Compare two scans and return the diff of their findings.

    Returns event types and data that are:
    - **only_in_a**: found in scan A but not scan B
    - **only_in_b**: found in scan B but not scan A
    - **common**: found in both scans

    Useful for tracking changes between re-scans of the same target.
    """
    # Verify both scans exist
    rec_a = svc.get_scan(scan_a)
    rec_b = svc.get_scan(scan_b)
    if rec_a is None:
        raise HTTPException(status_code=404, detail=f"Scan '{scan_a}' not found")
    if rec_b is None:
        raise HTTPException(status_code=404, detail=f"Scan '{scan_b}' not found")

    try:
        # Get events for both scans
        events_a = svc.get_events(scan_a) or []
        events_b = svc.get_events(scan_b) or []

        # Build sets of (eventType, data) tuples for comparison
        def _event_key(e):
            if isinstance(e, dict):
                return (e.get("type", e.get("eventType", "")), str(e.get("data", "")))
            return (getattr(e, "eventType", ""), str(getattr(e, "data", "")))

        set_a = set(_event_key(e) for e in events_a)
        set_b = set(_event_key(e) for e in events_b)

        only_a = set_a - set_b
        only_b = set_b - set_a
        common = set_a & set_b

        # Group by event type
        def _group_by_type(items):
            grouped = {}
            for etype, data in items:
                grouped.setdefault(etype, []).append(data)
            return grouped

        # Type-level summary
        types_a = set(t for t, _ in set_a)
        types_b = set(t for t, _ in set_b)

        return {
            "scan_a": {"id": scan_a, "total_events": len(events_a)},
            "scan_b": {"id": scan_b, "total_events": len(events_b)},
            "summary": {
                "only_in_a": len(only_a),
                "only_in_b": len(only_b),
                "common": len(common),
                "new_event_types_in_b": sorted(types_b - types_a),
                "removed_event_types_in_b": sorted(types_a - types_b),
            },
            "diff": {
                "only_in_a": _group_by_type(sorted(only_a)[:500]),
                "only_in_b": _group_by_type(sorted(only_b)[:500]),
            },
        }
    except Exception as e:
        log.error("Failed to compare scans %s vs %s: %s", scan_a, scan_b, e)
        raise HTTPException(status_code=500, detail="Scan comparison failed") from e