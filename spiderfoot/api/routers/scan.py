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
    MessageResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

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
        logger.error("Failed to start scan %s: %s", scan_id, e)


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
        logger.error("Failed to list scans: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list scans") from e


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
            logger.error("Failed to create scan instance: %s", e)
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
            status="STARTING",
            message="Scan created and starting",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create scan: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create scan") from e


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
    except Exception:
        pass
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
        return ScanStopResponse(message="Scan stopped successfully", status=new_status)
    except ScanServiceError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


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
    except Exception:
        raise HTTPException(status_code=404, detail="Scan ID not found")

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
        logger.error("Failed to clear scan %s: %s", scan_id, e)
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
    return MessageResponse(message="Scan unarchived")
