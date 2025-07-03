from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse, Response
from typing import List, Optional
from spiderfoot import SpiderFootDb, SpiderFootHelpers, __version__
from spiderfoot.scan_service.scanner import startSpiderFootScanner
from ..dependencies import get_app_config, get_api_key, optional_auth
import csv
import openpyxl
import html
import json
import time
from io import BytesIO, StringIO
import logging
from copy import deepcopy
import multiprocessing as mp
from fastapi import Body
from spiderfoot.sflib.core import SpiderFoot
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)

api_key_dep = Depends(get_api_key)
optional_auth_dep = Depends(optional_auth)
limit_query = Query(50, ge=1, le=1000)
offset_query = Query(0, ge=0)

scan_metadata_body = Body(...)
scan_notes_body = Body(...)

# Request body models
class ScanRequest(BaseModel):
    name: str = Field(..., description="Name of the scan")
    target: str = Field(..., description="Target for the scan")
    modules: Optional[List[str]] = Field(None, description="List of module names to run")
    type_filter: Optional[List[str]] = Field(None, description="List of event types to include")
    # Add other fields as necessary for scan configuration


# Helper/background task (move from sfapi.py)


async def start_scan_background(scan_id: str, scan_name: str, target: str,
                               target_type: str, modules: list,
                               type_filter: list, config: dict):
    try:
        startSpiderFootScanner(
            None,  # TODO: pass logging queue if needed
            scan_name,
            scan_id,
            target,
            target_type,
            modules,
            config
        )
    except Exception as e:
        logger.error("Failed to start scan %s: %s", scan_id, e)


@router.get("/scans")
async def list_scans(
    limit: int = limit_query,
    offset: int = offset_query,
    api_key: str = optional_auth_dep
):
    """
    List all scans.

    Args:
        limit (int): Max number of scans to return.
        offset (int): Offset for pagination.
        api_key (str): API key for authentication.

    Returns:
        dict: List of scans and pagination info.

    Raises:
        HTTPException: On failure.
    """
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        scans = db.scanInstanceList()
        paginated_scans = scans[offset:offset + limit]
        scan_list = []
        for scan in paginated_scans:
            scan_info = {
                "id": scan[0],
                "name": scan[1],
                "target": scan[2],
                "created": scan[3],
                "started": scan[4],
                "ended": scan[5],
                "status": scan[6],
                "result_count": scan[7] if len(scan) > 7 else 0
            }
            scan_list.append(scan_info)
        return {
            "scans": scan_list,
            "total": len(scans),
            "offset": offset,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Failed to list scans: {e}")
        raise HTTPException(status_code=500, detail="Failed to list scans") from e


@router.post("/scans", status_code=201)
async def create_scan(scan_request: ScanRequest, background_tasks: BackgroundTasks, api_key: str = api_key_dep):
    """
    Create and start a new scan.

    Args:
        scan_request: Scan creation request body (ScanRequest model).
        background_tasks (BackgroundTasks): FastAPI background tasks.
        api_key (str): API key for authentication.

    Returns:
        dict: Scan creation result.

    Raises:
        HTTPException: On failure.
    """
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        scan_id = SpiderFootHelpers.genScanInstanceId()
        target_type = SpiderFootHelpers.targetTypeFromString(scan_request.target)
        if not target_type:
            raise HTTPException(status_code=422, detail="Invalid target")
        sf = SpiderFoot(config.get_config())
        all_modules = sf.modulesProducing(['*'])
        if not scan_request.modules:
            modules = all_modules
        else:
            modules = scan_request.modules
        if not modules:
            modules = ['sfp__stor_db']
        try:
            db.scanInstanceCreate(scan_id, scan_request.name, scan_request.target)
        except Exception as e:
            logger.error("Failed to create scan instance: %s", e)
            raise HTTPException(status_code=500, detail="Unable to create scan instance in database") from e
        background_tasks.add_task(
            start_scan_background,
            scan_id,
            scan_request.name,
            scan_request.target,
            target_type,
            modules,
            scan_request.type_filter,
            config.get_config()
        )
        return {
            "id": scan_id,
            "name": scan_request.name,
            "target": scan_request.target,
            "status": "STARTING",
            "message": "Scan created and starting"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create scan: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create scan") from e


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str, api_key: str = optional_auth_dep):
    """
    Get scan details.

    Args:
        scan_id (str): Scan ID.
        api_key (str): API key for authentication.

    Returns:
        dict: Scan details.

    Raises:
        HTTPException: On failure.
    """
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        scan_info = db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        return {
            "id": scan_info[0],
            "name": scan_info[1],
            "target": scan_info[2],
            "created": scan_info[3],
            "started": scan_info[4],
            "ended": scan_info[5],
            "status": scan_info[6]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scan") from e


@router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str, api_key: str = api_key_dep):
    """
    Delete a scan.

    Args:
        scan_id (str): Scan ID.
        api_key (str): API key for authentication.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: On failure.
    """
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        scan_info = db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        db.scanInstanceDelete(scan_id)
        return {"message": "Scan deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete scan") from e


@router.delete("/scans/{scan_id}/full")
async def delete_scan_full(scan_id: str, api_key: str = api_key_dep):
    """
    Delete a scan and all related data (full parity with web UI advanced delete).

    Args:
        scan_id (str): The scan ID to delete.
        api_key (str): API key for authentication.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: If scan not found or deletion fails.
    """
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        scan_info = db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        db.scanResultDelete(scan_id)
        db.scanConfigDelete(scan_id)
        db.scanInstanceDelete(scan_id)
        return {"message": "Scan and all related data deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fully delete scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fully delete scan and related data") from e


@router.post("/scans/{scan_id}/stop")
async def stop_scan(scan_id: str, api_key: str = api_key_dep):
    """
    Stop a running scan.

    Args:
        scan_id (str): Scan ID.
        api_key (str): API key for authentication.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: On failure.
    """
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        scan_info = db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        db.scanInstanceSet(scan_id, None, None, "ABORTED")
        return {"message": "Scan stopped successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop scan") from e


@router.get("/scans/{scan_id}/events/export")
async def export_scan_event_results(
    scan_id: str,
    event_type: str = None,
    filetype: str = "csv",
    dialect: str = "excel",
    api_key: str = optional_auth_dep
):
    """
    Export scan event result data as CSV or Excel (full parity with scaneventresultexport).

    Args:
        scan_id (str): Scan ID.
        event_type (str, optional): Event type filter.
        filetype (str, optional): Export file type (csv or xlsx).
        dialect (str, optional): CSV dialect.
        api_key (str): API key for authentication.

    Returns:
        StreamingResponse: File download response.

    Raises:
        HTTPException: On error or invalid filetype.
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    # Check if scan exists before querying events
    scan = dbh.scanInstanceGet(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if event_type is None:
        event_type = "ALL"
    data = dbh.scanResultEvent(scan_id, event_type)
    rows = []
    for row in data:
        if row[4] == "ROOT":
            continue
        lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
        datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
        rows.append([
            lastseen, str(row[4]), str(row[3]), str(row[2]), row[13], datafield
        ])
    headings = ["Updated", "Type", "Module", "Source", "F/P", "Data"]
    if filetype.lower() in ["xlsx", "excel"]:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "EventResults"
        ws.append(headings)
        for row in rows:
            ws.append(row)
        with BytesIO() as f:
            wb.save(f)
            f.seek(0)
            return StreamingResponse(
                iter([f.read()]),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=SpiderFoot-{scan_id}-eventresults.xlsx",
                    "Pragma": "no-cache"
                }
            )
    if filetype.lower() == "csv":
        fileobj = StringIO()
        parser = csv.writer(fileobj, dialect=dialect)
        parser.writerow(headings)
        for row in rows:
            parser.writerow(row)
        fileobj.seek(0)
        return StreamingResponse(
            iter([fileobj.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=SpiderFoot-{scan_id}-eventresults.csv",
                "Pragma": "no-cache"
            }
        )
    raise HTTPException(status_code=400, detail="Invalid export filetype.")


@router.get("/scans/export-multi")
async def export_scan_json_multi(ids: str, api_key: str = optional_auth_dep):
    """
    Export event results for multiple scans as JSON (full parity with scanexportjsonmulti).

    Args:
        ids (str): Comma-separated scan IDs.
        api_key (str): API key for authentication.

    Returns:
        StreamingResponse: File download response.

    Raises:
        HTTPException: On error.
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    scaninfo = []
    scan_name = ""
    for scan_id in ids.split(','):
        scan = dbh.scanInstanceGet(scan_id)
        if scan is None:
            continue
        scan_name = scan[0]
        for row in dbh.scanResultEvent(scan_id):
            lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
            event_data = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
            source_data = str(row[2])
            source_module = str(row[3])
            event_type = row[4]
            false_positive = row[13] if len(row) > 13 else None
            if event_type == "ROOT":
                continue
            scaninfo.append({
                "data": event_data,
                "event_type": event_type,
                "module": source_module,
                "source_data": source_data,
                "false_positive": false_positive,
                "last_seen": lastseen,
                "scan_name": scan_name,
                "scan_target": scan[1]
            })
    if len(ids.split(',')) > 1 or scan_name == "":
        fname = "SpiderFoot.json"
    else:
        fname = scan_name + "-SpiderFoot.json"
    return StreamingResponse(
        iter([json.dumps(scaninfo, ensure_ascii=False)]),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={fname}",
            "Pragma": "no-cache"
        }
    )


@router.get("/scans/{scan_id}/search/export")
async def export_scan_search_results(scan_id: str, event_type: str = None, value: str = None, filetype: str = "csv", dialect: str = "excel", api_key: str = Depends(optional_auth)):
    """Export search result data as CSV or Excel (full parity with scansearchresultexport)"""
    config = get_app_config()
    # Use the same searchBase logic as in sfwebui.py
    dbh = SpiderFootDb(config.get_config())
    # searchBase returns: [lastseen, data, src, module, event_type, ...]
    data = []
    for row in dbh.search({
        'scan_id': scan_id or '',
        'type': event_type or '',
        'value': value or '',
        'regex': ''
    }):
        if len(row) < 12 or row[10] == "ROOT":
            continue
        datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
        data.append([
            row[0], str(row[10]), str(row[3]), str(row[2]), row[11], datafield
        ])
    headings = ["Updated", "Type", "Module", "Source", "F/P", "Data"]
    if not data:
        raise HTTPException(status_code=404, detail="No search results found for this scan")
    if filetype.lower() in ["xlsx", "excel"]:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "SearchResults"
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
                    "Content-Disposition": f"attachment; filename=SpiderFoot-{scan_id}-searchresults.xlsx",
                    "Pragma": "no-cache"
                }
            )
    if filetype.lower() == "csv":
        fileobj = StringIO()
        parser = csv.writer(fileobj, dialect=dialect)
        parser.writerow(headings)
        for row in data:
            parser.writerow(row)
        fileobj.seek(0)
        return StreamingResponse(
            iter([fileobj.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=SpiderFoot-{scan_id}-searchresults.csv",
                "Pragma": "no-cache"
            }
        )
    raise HTTPException(status_code=400, detail="Invalid export filetype.")


@router.get("/scans/{scan_id}/viz")
async def export_scan_viz(scan_id: str, gexf: str = "0", api_key: str = Depends(optional_auth)):
    """Export entities from scan results for visualising (GEXF/graph)."""
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    data = dbh.scanResultEvent(scan_id, filterFp=True)
    scan = dbh.scanInstanceGet(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    scan_name = scan[0]
    root = scan[1]
    if gexf == "0":
        # Return JSON graph
        graph_json = SpiderFootHelpers.buildGraphJson([root], data)
        return Response(graph_json, media_type="application/json")
    # Else return GEXF
    fname = f"{scan_name}-SpiderFoot.gexf" if scan_name else "SpiderFoot.gexf"
    gexf_data = SpiderFootHelpers.buildGraphGexf([root], "SpiderFoot Export", data)
    return Response(
        gexf_data,
        media_type="application/gexf",
        headers={
            "Content-Disposition": f"attachment; filename={fname}",
            "Pragma": "no-cache"
        }
    )


@router.get("/scans/viz-multi")
async def export_scan_viz_multi(ids: str, gexf: str = "1", api_key: str = Depends(optional_auth)):
    """Export entities results from multiple scans in GEXF format."""
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    data = []
    roots = []
    scan_name = ""
    if not ids:
        raise HTTPException(status_code=400, detail="No scan IDs provided")
    for scan_id in ids.split(','):
        scan = dbh.scanInstanceGet(scan_id)
        if not scan:
            continue
        data += dbh.scanResultEvent(scan_id, filterFp=True)
        roots.append(scan[1])
        scan_name = scan[0]
    if not data:
        raise HTTPException(status_code=404, detail="No data found for these scans")
    if gexf == "0":
        # Not implemented in web UI
        raise HTTPException(status_code=501, detail="Graph JSON for multi-scan not implemented")
    fname = f"{scan_name}-SpiderFoot.gexf" if len(ids.split(',')) == 1 and scan_name else "SpiderFoot.gexf"
    gexf_data = SpiderFootHelpers.buildGraphGexf(roots, "SpiderFoot Export", data)
    return Response(
        gexf_data,
        media_type="application/gexf",
        headers={
            "Content-Disposition": f"attachment; filename={fname}",
            "Pragma": "no-cache"
        }
    )


@router.get("/scans/{scan_id}/options")
async def get_scan_options(scan_id: str, api_key: str = Depends(optional_auth)):
    """Return configuration used for the specified scan as JSON (parity with scanopts)."""
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    ret = dict()
    meta = dbh.scanInstanceGet(scan_id)
    if not meta:
        return ret
    if meta[3] != 0:
        started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(meta[3]))
    else:
        started = "Not yet"
    if meta[4] != 0:
        finished = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(meta[4]))
    else:
        finished = "Not yet"
    ret['meta'] = [meta[0], meta[1], meta[2], started, finished, meta[5]]
    ret['config'] = dbh.scanConfigGet(scan_id)
    ret['configdesc'] = dict()
    for key in list(ret['config'].keys()):
        if ':' not in key:
            globaloptdescs = config.get_config().get('__globaloptdescs__', {})
            if globaloptdescs:
                ret['configdesc'][key] = globaloptdescs.get(key, f"{key} (legacy)")
        else:
            modName, modOpt = key.split(':')
            modules = config.get_config().get('__modules__', {})
            if modName not in modules:
                continue
            if modOpt not in modules[modName].get('optdescs', {}):
                continue
            ret['configdesc'][key] = modules[modName]['optdescs'][modOpt]
    return ret


@router.post("/scans/{scan_id}/rerun")
async def rerun_scan(scan_id: str, api_key: str = Depends(get_api_key)):
    """Rerun a scan (parity with rerunscan in web UI)."""
    config = get_app_config()
    cfg = deepcopy(config.get_config())
    dbh = SpiderFootDb(cfg)
    info = dbh.scanInstanceGet(scan_id)
    if not info:
        raise HTTPException(status_code=404, detail="Invalid scan ID.")
    scanname = info[0]
    scantarget = info[1]
    if not scantarget:
        raise HTTPException(status_code=400, detail=f"Scan {scan_id} has no target defined.")
    scanconfig = dbh.scanConfigGet(scan_id)
    if not scanconfig:
        raise HTTPException(status_code=400, detail=f"Error loading config from scan: {scan_id}")
    modlist = scanconfig['_modulesenabled'].split(',')
    if "sfp__stor_stdout" in modlist:
        modlist.remove("sfp__stor_stdout")
    targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
    if not targetType:
        targetType = SpiderFootHelpers.targetTypeFromString(f'"{scantarget}"')
    if not targetType:
        raise HTTPException(status_code=400, detail=f"Cannot determine target type for scan rerun. Target '{scantarget}' is not recognized as a valid SpiderFoot target.")
    if targetType not in ["HUMAN_NAME", "BITCOIN_ADDRESS"]:
        scantarget = scantarget.lower()
    new_scan_id = SpiderFootHelpers.genScanInstanceId()
    try:
        p = mp.Process(target=startSpiderFootScanner, args=(
            None, scanname, new_scan_id, scantarget, targetType, modlist, cfg))
        p.daemon = True
        p.start()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan [{new_scan_id}] failed: {e}")
    # Wait until the scan has initialized
    while dbh.scanInstanceGet(new_scan_id) is None:
        time.sleep(1)
    return {"new_scan_id": new_scan_id, "message": "Scan rerun started"}


@router.post("/scans/rerun-multi")
async def rerun_scan_multi(ids: str, api_key: str = Depends(get_api_key)):
    """Rerun multiple scans (parity with rerunscanmulti in web UI)."""
    config = get_app_config()
    cfg = deepcopy(config.get_config())
    dbh = SpiderFootDb(cfg)
    new_scan_ids = []
    for scan_id in ids.split(","):
        info = dbh.scanInstanceGet(scan_id)
        if not info:
            continue
        scanconfig = dbh.scanConfigGet(scan_id)
        scanname = info[0]
        scantarget = info[1]
        if not scantarget or not scanconfig:
            continue
        modlist = scanconfig['_modulesenabled'].split(',')
        if "sfp__stor_stdout" in modlist:
            modlist.remove("sfp__stor_stdout")
        targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
        if targetType is None:
            continue
        new_scan_id = SpiderFootHelpers.genScanInstanceId()
        try:
            p = mp.Process(target=startSpiderFootScanner, args=(
                None, scanname, new_scan_id, scantarget, targetType, modlist, cfg))
            p.daemon = True
            p.start()
        except Exception:
            continue
        while dbh.scanInstanceGet(new_scan_id) is None:
            time.sleep(1)
        new_scan_ids.append(new_scan_id)
    return {"new_scan_ids": new_scan_ids, "message": f"{len(new_scan_ids)} scans rerun started"}


@router.post("/scans/{scan_id}/clone")
async def clone_scan(scan_id: str, api_key: str = Depends(get_api_key)):
    """
    Clone a scan (parity with scanclone in web UI).

    Args:
        scan_id (str): The scan ID to clone.
        api_key (str): API key for authentication.

    Returns:
        dict: New scan ID and success message.

    Raises:
        HTTPException: If scan not found or clone fails.
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    info = dbh.scanInstanceGet(scan_id)
    if not info:
        raise HTTPException(status_code=404, detail="Invalid scan ID.")
    scanname = info[0] + " (Clone)"
    scantarget = info[1]
    scanconfig = dbh.scanConfigGet(scan_id)
    if not scanconfig:
        raise HTTPException(status_code=400, detail=f"Error loading config from scan: {scan_id}")
    modlist = scanconfig['_modulesenabled'].split(',')
    if "sfp__stor_stdout" in modlist:
        modlist.remove("sfp__stor_stdout")
    targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
    if not targetType:
        targetType = SpiderFootHelpers.targetTypeFromString(f'"{scantarget}"')
    if not targetType:
        raise HTTPException(status_code=400, detail=f"Cannot determine target type for scan clone. Target '{scantarget}' is not recognized as a valid SpiderFoot target.")
    if targetType not in ["HUMAN_NAME", "BITCOIN_ADDRESS"]:
        scantarget = scantarget.lower()
    new_scan_id = SpiderFootHelpers.genScanInstanceId()
    try:
        dbh.scanInstanceCreate(new_scan_id, scanname, scantarget)
        dbh.scanConfigSet(new_scan_id, scanconfig)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan [{new_scan_id}] clone failed: {e}") from e
    return {"new_scan_id": new_scan_id, "message": "Scan cloned successfully"}


@router.post("/scans/{scan_id}/results/falsepositive")
async def set_results_false_positive(scan_id: str, resultids: List[str], fp: str, api_key: str = api_key_dep):
    """
    Set a batch of results as false positive or not (parity with resultsetfp in web UI).

    Args:
        scan_id (str): Scan ID.
        resultids (List[str]): List of result IDs (hashes).
        fp (str): '0' (not FP) or '1' (FP).
        api_key (str): API key for authentication.

    Returns:
        dict: Status and message.

    Raises:
        HTTPException: On error or invalid state.
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    if fp not in ["0", "1"]:
        raise HTTPException(status_code=400, detail="No FP flag set or not set correctly.")
    # Cannot set FPs if a scan is not completed
    status = dbh.scanInstanceGet(scan_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Invalid scan ID: {scan_id}")
    if status[5] not in ["ABORTED", "FINISHED", "ERROR-FAILED"]:
        return {"status": "WARNING", "message": "Scan must be in a finished state when setting False Positives."}
    # Make sure the user doesn't set something as non-FP when the parent is set as an FP
    if fp == "0":
        data = dbh.scanElementSourcesDirect(scan_id, resultids)
        for row in data:
            if str(row[14]) == "1":
                return {"status": "WARNING", "message": f"Cannot unset element {scan_id} as False Positive if a parent element is still False Positive."}
    # Set all the children as FPs too
    childs = dbh.scanElementChildrenAll(scan_id, resultids)
    all_ids = resultids + childs
    ret = dbh.scanResultsUpdateFP(scan_id, all_ids, fp)
    if ret:
        return {"status": "SUCCESS", "message": ""}
    return {"status": "ERROR", "message": "Exception encountered."}


@router.get("/scans/{scan_id}/logs/export")
async def export_scan_logs(scan_id: str, dialect: str = "excel", api_key: str = optional_auth_dep):
    """
    Export scan logs as CSV (parity with scanexportlogs in web UI).
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    try:
        data = dbh.scanLogs(scan_id)
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
            "Pragma": "no-cache"
        }
    )


@router.get("/scans/{scan_id}/correlations/export")
async def export_scan_correlations(scan_id: str, filetype: str = "csv", dialect: str = "excel", api_key: str = optional_auth_dep):
    """
    Export scan correlation data as CSV or Excel (parity with scancorrelationsexport in web UI).
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    try:
        data = dbh.scanCorrelations(scan_id)
        scan = dbh.scanInstanceGet(scan_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Scan ID not found")
    headings = ["Rule Name", "Correlation", "Risk", "Description"]
    if filetype.lower() in ["xlsx", "excel"]:
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
                    "Pragma": "no-cache"
                }
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
                "Pragma": "no-cache"
            }
        )
    raise HTTPException(status_code=400, detail="Invalid export filetype.")


@router.get("/scans/{scan_id}/metadata")
async def get_scan_metadata(scan_id: str, api_key: str = optional_auth_dep):
    """
    Get scan metadata.
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    scan = dbh.scanInstanceGet(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    # Assume scan metadata is stored in scan config or a dedicated table/field
    metadata = dbh.scanMetadataGet(scan_id) if hasattr(dbh, 'scanMetadataGet') else {}
    return {"metadata": metadata}


@router.patch("/scans/{scan_id}/metadata")
async def update_scan_metadata(scan_id: str, metadata: dict = scan_metadata_body, api_key: str = api_key_dep):
    """
    Update scan metadata (key/value pairs).
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    scan = dbh.scanInstanceGet(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=422, detail="Metadata must be a dictionary")
    if hasattr(dbh, 'scanMetadataSet'):
        dbh.scanMetadataSet(scan_id, metadata)
    return {"success": True, "metadata": metadata}


@router.get("/scans/{scan_id}/notes")
async def get_scan_notes(scan_id: str, api_key: str = optional_auth_dep):
    """
    Get scan notes/comments.
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    scan = dbh.scanInstanceGet(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    notes = dbh.scanNotesGet(scan_id) if hasattr(dbh, 'scanNotesGet') else ""
    return {"notes": notes}


@router.patch("/scans/{scan_id}/notes")
async def update_scan_notes(scan_id: str, notes: str = scan_notes_body, api_key: str = api_key_dep):
    """
    Update scan notes/comments.
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    scan = dbh.scanInstanceGet(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if hasattr(dbh, 'scanNotesSet'):
        dbh.scanNotesSet(scan_id, notes)
    return {"success": True, "notes": notes}


@router.post("/scans/{scan_id}/archive")
async def archive_scan(scan_id: str, api_key: str = api_key_dep):
    """
    Archive a scan (set archived flag in metadata).
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    scan = dbh.scanInstanceGet(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if hasattr(dbh, 'scanMetadataGet') and hasattr(dbh, 'scanMetadataSet'):
        metadata = dbh.scanMetadataGet(scan_id) or {}
        metadata['archived'] = True
        dbh.scanMetadataSet(scan_id, metadata)
    return {"success": True, "message": "Scan archived"}


@router.post("/scans/{scan_id}/unarchive")
async def unarchive_scan(scan_id: str, api_key: str = api_key_dep):
    """
    Unarchive a scan (unset archived flag in metadata).
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    scan = dbh.scanInstanceGet(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if hasattr(dbh, 'scanMetadataGet') and hasattr(dbh, 'scanMetadataSet'):
        metadata = dbh.scanMetadataGet(scan_id) or {}
        metadata['archived'] = False
        dbh.scanMetadataSet(scan_id, metadata)
    return {"success": True, "message": "Scan unarchived"}


@router.post("/scans/{scan_id}/clear")
async def clear_scan(scan_id: str, api_key: str = api_key_dep):
    """
    Remove all results/events for a scan, but keep the scan entry.
    """
    config = get_app_config()
    dbh = SpiderFootDb(config.get_config())
    scan = dbh.scanInstanceGet(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    try:
        dbh.scanResultDelete(scan_id)
        return {"success": True, "message": "Scan results cleared (scan entry retained)"}
    except Exception as e:
        logger.error(f"Failed to clear scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear scan results") from e
