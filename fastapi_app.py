# -*- coding: utf-8 -*-
# -----------------------------------------------------------------
# Name:         fastapi_app
# Purpose:      FastAPI interface for SpiderFoot
#
# Author:       Steve Micallef <steve@binarypool.com>
#
# Created:      Original CherryPy API: 03/05/2017
# FastAPI Port: Current Date
# Copyright:    (c) Steve Micallef
# License:      MIT
# -----------------------------------------------------------------
from typing import List, Dict, Optional, Any, Union
import json
import logging
import os
import random
import time
from copy import deepcopy
from operator import itemgetter
import multiprocessing as mp

from fastapi import FastAPI, HTTPException, Query, Path, Body, Depends, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sflib import SpiderFoot
from sfscan import startSpiderFootScanner
from spiderfoot import SpiderFootDb, SpiderFootHelpers, __version__
from spiderfoot.logger import logListenerSetup, logWorkerSetup
from spiderfoot.api_helpers import ApiHelpers

# Add this function near the top of the file after the imports

def setup_api_router(app, config, logging_queue=None):
    """Setup FastAPI router with all endpoints.
    
    Args:
        app (FastAPI): The FastAPI application instance
        config (dict): SpiderFoot configuration
        logging_queue (Queue, optional): Logging queue for multiprocessing
    """
    global loggingQueue, sfConfig
    
    # Set global variables for the module
    loggingQueue = logging_queue
    sfConfig = config
    
    # You can add more route setup code here if needed
    
    # Log successful setup
    log.info("API router setup complete")

# Add OpenAPI customization
app = FastAPI(
    title="SpiderFoot API",
    description="API for SpiderFoot OSINT reconnaissance tool",
    version=__version__,
    docs_url="/swaggerui",  # Make Swagger UI available at the same path as CherryPy
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Scans", "description": "Operations related to scans"},
        {"name": "Configuration", "description": "Operations related to configuration"},
        {"name": "Data", "description": "Operations related to data retrieval"},
        {"name": "Utilities", "description": "Utility operations"}
    ]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Global state (to be refactored later with dependency injection)
config = {}
token = random.SystemRandom().randint(0, 9999999999)
defaultConfig = {}
loggingQueue = None

# Configure logging
log = logging.getLogger("spiderfoot.fastapi_app")


# Pydantic models for request/response validation
class ScanStatusResponse(BaseModel):
    id: str
    name: str
    target: str
    created: int
    started: int
    finished: int
    status: str

class ErrorResponse(BaseModel):
    error: Dict[str, Any]

class SuccessResponse(BaseModel):
    status: str
    scan_id: str

class PingResponse(BaseModel):
    status: str
    version: str

# Additional Pydantic models for request/response bodies
class ScanStartRequest(BaseModel):
    scanname: str = Field(..., description="Name of the scan")
    scantarget: str = Field(..., description="Target for the scan")
    modulelist: Optional[str] = Field(None, description="Comma separated list of modules to use")
    typelist: Optional[str] = Field(None, description="Comma separated list of event types to select modules by")
    usecase: Optional[str] = Field(None, description="Selected module group (all, footprint, investigate, passive)")

class ScanDeleteRequest(BaseModel):
    id: str = Field(..., description="Comma separated list of scan IDs to delete")

class ScanRerunRequest(BaseModel):
    id: str = Field(..., description="Scan ID to rerun")

class ScanMultiRerunRequest(BaseModel):
    ids: str = Field(..., description="Comma separated list of scan IDs to rerun")

class ScanStopRequest(BaseModel):
    id: str = Field(..., description="Comma separated list of scan IDs to stop")

class SaveSettingsRequest(BaseModel):
    allopts: str = Field(..., description="JSON string of settings or 'RESET' to reset settings")
    token: str = Field(..., description="CSRF token from optsraw endpoint")

class SetFpRequest(BaseModel):
    id: str = Field(..., description="Scan ID")
    resultids: str = Field(..., description="Comma separated list of result IDs (hashes)")
    fp: str = Field(..., description="0 or 1")

# Additional models for more complex responses
class ScanCorrelation(BaseModel):
    id: str
    correlation: str
    rule_name: str
    rule_risk: str
    rule_id: str
    rule_description: str
    events: Optional[str]
    created: Optional[str]

class ScanConfig(BaseModel):
    meta: List
    config: Dict[str, Any]
    configdesc: Dict[str, str]

class ScanDeleteResponse(BaseModel):
    deleted: List[str]
    errors: List[Dict[str, str]]

class ScanStopResponse(BaseModel):
    stopped: List[str]
    errors: List[Dict[str, str]]

class ScanRerunResponse(BaseModel):
    status: str
    scan_id: str

class ScanMultiRerunResponse(BaseModel):
    started: List[Dict[str, str]]
    errors: List[Dict[str, str]]

class VacuumResponse(BaseModel):
    status: str
    message: str

class QueryResponse(BaseModel):
    success: bool
    data: List

# Helper functions
def jsonify_error(status_code: int, message: str) -> JSONResponse:
    """Jsonify error response.

    Args:
        status_code (int): HTTP response status code
        message (str): Error message

    Returns:
        JSONResponse: HTTP error response
    """
    return JSONResponse(
        status_code=status_code,
        content={
            'error': {
                'http_status': status_code,
                'message': message,
            }
        }
    )

# Dependency to get SpiderFootDb instance
def get_db():
    return SpiderFootDb(config)

# Routes
@app.get("/ping", response_model=PingResponse, tags=["Utilities"])
def ping():
    """For the CLI to test connectivity to this server.

    Returns:
        dict: Success and version information
    """
    return {"status": "SUCCESS", "version": __version__}

@app.get("/scanstatus/{scan_id}", response_model=Union[ScanStatusResponse, ErrorResponse], tags=["Scans"])
def scan_status(scan_id: str = Path(..., description="Scan ID"), db: SpiderFootDb = Depends(get_db)):
    """Return the status of a scan.

    Args:
        scan_id: scan ID

    Returns:
        dict: scan status or error JSON
    """
    status = db.scanInstanceGet(scan_id)
    if not status:
        raise HTTPException(status_code=404, detail="Scan ID not found.")
    
    return status

@app.get("/scanlist", response_model=List[List], tags=["Scans"])
def scan_list(db: SpiderFootDb = Depends(get_db)):
    """Return a list of all scans.

    Returns:
        list: list of scans
    """
    try:
        scanlist = db.scanInstanceList()
        retlist = []
        for scan in scanlist:
            created = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(scan[3]))
            if scan[4]:
                finished = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(scan[4]))
            else:
                finished = ""
            retlist.append([scan[0], scan[1], created, finished, scan[5]])
        return retlist
    except Exception as e:
        log.error(f"Error fetching scan list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching scan list: {e}")

@app.get("/scaneventresults/{scan_id}", tags=["Data"])
def scan_event_results(
    scan_id: str = Path(..., description="Scan ID"),
    eventType: Optional[str] = Query(None, description="Event type filter"),
    filterfp: bool = Query(False, description="Filter out false positives"),
    db: SpiderFootDb = Depends(get_db)
):
    """Return events for a scan.

    Args:
        scan_id: scan ID
        eventType: event type filter
        filterfp: filter out false positives

    Returns:
        list: list of scan events
    """
    try:
        data = db.scanResultEvent(scan_id, eventType if eventType else 'ALL', filterfp)
        retdata = []
        
        for row in data:
            lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
            retdata.append([
                lastseen,
                row[1],  # Data
                row[2],  # Module
                row[3],  # Source
                row[4],  # Event Type
                row[5],  # confidence
                row[6],  # visibility
                row[7],  # risk
                row[8],  # hash
                row[9],  # source event hash
                row[10],  # module instance ID
                row[11],  # scan instance ID
                row[13],  # false positive
                row[14],  # id
            ])
            
        return retdata
    except Exception as e:
        log.error(f"Error fetching scan results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching scan results: {e}")

@app.post("/startscan", response_model=SuccessResponse, tags=["Scans"])
def start_scan(
    request: ScanStartRequest,
    db: SpiderFootDb = Depends(get_db)
):
    """Initiate a scan.

    Args:
        request: Scan configuration parameters

    Returns:
        dict: JSON containing status and new scan ID
    """
    global config, loggingQueue
    
    # Validate input and build module list
    error, targetType, scantarget, modlist = ApiHelpers.validate_scan_input(
        request.scanname, 
        request.scantarget, 
        request.modulelist, 
        request.typelist, 
        request.usecase, 
        config
    )
    
    if error:
        raise HTTPException(status_code=error["status_code"], detail=error["message"])
    
    # Start the scan
    error, scan_id = ApiHelpers.start_scan(
        loggingQueue, 
        request.scanname,
        scantarget, 
        modlist, 
        targetType, 
        deepcopy(config)
    )
    
    if error:
        raise HTTPException(status_code=error["status_code"], detail=error["message"])
        
    log.info(f"Started scan: {request.scanname} ({scan_id}) for target {scantarget}")
    return {"status": "SUCCESS", "scan_id": scan_id}

@app.get("/eventtypes", tags=["Data"])
def event_types(db: SpiderFootDb = Depends(get_db)):
    """List all event types.

    Returns:
        list: list of event type dictionaries [{'name': name, 'descr': descr}]
    """
    types = db.eventTypes()
    ret = list()

    for r in types:
        ret.append({'name': r[0], 'descr': r[1]})

    return sorted(ret, key=itemgetter('name'))

@app.get("/modules", tags=["Data"])
def modules():
    """List all modules.

    Returns:
        list: list of module dictionaries [{'name': name, 'descr': descr}]
    """
    global config
    
    ret = list()

    modinfo = list(config.get('__modules__', {}).keys())
    if not modinfo:
        raise HTTPException(status_code=500, detail="Module information not loaded.")

    modinfo.sort()

    for m in modinfo:
        descr = config['__modules__'][m].get('summary', 'No description available.')
        ret.append({'name': m, 'descr': descr})

    return ret

@app.get("/optsraw", tags=["Configuration"])
def opts_raw():
    """Return global and module settings as json.

    Returns:
        dict: {'token': CSRF_token, 'data': settings_dict}
    """
    global config, token
    
    ret = dict()
    token = random.SystemRandom().randint(0, 99999999)
    sf = SpiderFoot(config)
    serialized_config = sf.configSerialize(config, filterSystem=False)
    for opt in serialized_config:
        ret[opt] = serialized_config[opt]
    
    # Include modules info and correlation rules
    if '__modules__' in config:
        ret['__modules__'] = config['__modules__']
    
    if '__correlationrules__' in config:
        ret['__correlationrules__'] = config['__correlationrules__']

    return {'token': token, 'data': ret}

@app.get("/scancorrelations/{scan_id}", response_model=List[List], tags=["Data"])
def scan_correlations(scan_id: str = Path(..., description="Scan ID"), db: SpiderFootDb = Depends(get_db)):
    """Return correlations for a scan.

    Args:
        scan_id: scan ID

    Returns:
        list: list of correlations or error JSON
    """
    try:
        corrs = db.scanCorrelationList(scan_id)
        return ApiHelpers.format_scan_correlation_results(corrs)
    except Exception as e:
        log.error(f"Error fetching correlations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching correlations: {e}")

@app.get("/scanhistory/{scan_id}", response_model=List, tags=["Data"])
def scan_history(scan_id: str = Path(..., description="Scan ID"), db: SpiderFootDb = Depends(get_db)):
    """Return scan history.

    Args:
        scan_id: scan ID

    Returns:
        list: scan history data or error JSON
    """
    try:
        return db.scanResultHistory(scan_id)
    except Exception as e:
        log.error(f"Error fetching scan history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching scan history: {e}")

@app.get("/scanopts/{scan_id}", response_model=ScanConfig, tags=["Configuration"])
def scan_options(scan_id: str = Path(..., description="Scan ID"), db: SpiderFootDb = Depends(get_db)):
    """Return configuration used for the specified scan as JSON.

    Args:
        scan_id: scan ID

    Returns:
        dict: scan options for the specified scan or error JSON
    """
    meta = db.scanInstanceGet(scan_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Scan ID not found.")

    scan_config = db.scanConfigGet(scan_id)
    if not scan_config:
        raise HTTPException(status_code=500, detail=f"Error loading config from scan: {scan_id}")
        
    return ApiHelpers.prepare_scan_options_response(scan_id, meta, scan_config, config)

@app.post("/scandelete", response_model=ScanDeleteResponse, tags=["Scans"])
def scan_delete(request: ScanDeleteRequest, db: SpiderFootDb = Depends(get_db)):
    """Delete scan(s).

    Args:
        request: request with scan ID(s) to delete

    Returns:
        dict: JSON response indicating success or failure for each ID
    """
    results = {"deleted": [], "errors": []}
    if not request.id:
        raise HTTPException(status_code=400, detail="No scan IDs provided.")

    ids = request.id.split(',')

    for scan_id in ids:
        status = db.scanInstanceGet(scan_id)
        if not status:
            results["errors"].append({"id": scan_id, "error": "Scan ID not found."})
            continue
        if status[5] in ["RUNNING", "STARTING", "STARTED"]:
            results["errors"].append({"id": scan_id, "error": "Scan is running, stop it first."})
            continue

    valid_ids_to_delete = [scan_id for scan_id in ids if not any(err['id'] == scan_id for err in results["errors"])]

    for scan_id in valid_ids_to_delete:
        log.info(f"Deleting scan: {scan_id}")
        try:
            if db.scanInstanceDelete(scan_id):
                results["deleted"].append(scan_id)
            else:
                results["errors"].append({"id": scan_id, "error": "Deletion failed unexpectedly."})
        except Exception as e:
            log.error(f"Error deleting scan {scan_id}: {e}", exc_info=True)
            results["errors"].append({"id": scan_id, "error": f"Exception during deletion: {e}"})

    return results

@app.post("/stopscan", response_model=ScanStopResponse, tags=["Scans"])
def stop_scan(request: ScanStopRequest, db: SpiderFootDb = Depends(get_db)):
    """Stop a scan.

    Args:
        request: request with scan ID(s) to stop

    Returns:
        dict: JSON response indicating success or failure for each ID
    """
    results = {"stopped": [], "errors": []}
    if not request.id:
        raise HTTPException(status_code=400, detail="No scan IDs provided.")

    ids = request.id.split(',')

    for scan_id in ids:
        status = db.scanInstanceGet(scan_id)
        if not status:
            results["errors"].append({"id": scan_id, "error": "Scan ID not found."})
            continue
        if status[5] not in ["RUNNING", "STARTING", "STARTED"]:
            results["errors"].append({"id": scan_id, "error": f"Scan not running (status: {status[5]})."})
            continue

    valid_ids_to_stop = [scan_id for scan_id in ids if not any(err['id'] == scan_id for err in results["errors"])]

    for scan_id in valid_ids_to_stop:
        log.info(f"Stopping scan: {scan_id}")
        try:
            if db.scanInstanceSet(scan_id, status='ABORT-REQUEST'):
                results["stopped"].append(scan_id)
            else:
                results["errors"].append({"id": scan_id, "error": "Failed to set ABORT-REQUEST status."})
        except Exception as e:
            log.error(f"Error requesting stop for scan {scan_id}: {e}", exc_info=True)
            results["errors"].append({"id": scan_id, "error": f"Exception requesting stop: {e}"})

    return results

@app.post("/rerunscan/{scan_id}", response_model=ScanRerunResponse, tags=["Scans"])
def rerun_scan(scan_id: str = Path(..., description="Scan ID"), db: SpiderFootDb = Depends(get_db)):
    """Rerun a scan.

    Args:
        scan_id: scan ID to rerun

    Returns:
        dict: JSON containing status and new scan ID or error JSON
    """
    # Snapshot the current configuration to be used by the scan
    cfg = deepcopy(config)
    modlist = list()
    info = db.scanInstanceGet(scan_id)

    if not info:
        raise HTTPException(status_code=404, detail="Invalid scan ID.")

    scanname = info[0]
    scantarget = info[1]

    scanconfig = db.scanConfigGet(scan_id)
    if not scanconfig:
        raise HTTPException(status_code=500, detail=f"Error loading config from scan: {scan_id}")

    modlist = scanconfig['_modulesenabled'].split(',')
    if "sfp__stor_stdout" in modlist:
        modlist.remove("sfp__stor_stdout")

    targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
    if not targetType:
        # It must then be a name, as a re-run scan should always have a clean
        # target. Put quotes around the target value and try to determine the
        # target type again.
        targetType = SpiderFootHelpers.targetTypeFromString(f'"{scantarget}"')

    if targetType not in ["HUMAN_NAME", "BITCOIN_ADDRESS"]:
        scantarget = scantarget.lower()

    # Start running a new scan
    scanId = SpiderFootHelpers.genScanInstanceId()
    try:
        p = mp.Process(target=startSpiderFootScanner, args=(
            loggingQueue, scanname, scanId, scantarget, targetType, modlist, cfg))
        p.daemon = True
        p.start()
    except Exception as e:
        log.error(f"[-] Scan [{scanId}] failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scan [{scanId}] failed to start: {e}")

    # Wait until the scan has initialized (with a timeout)
    start_time = time.time()
    while db.scanInstanceGet(scanId) is None:
        log.info("Waiting for the scan to initialize...")
        if time.time() - start_time > 30:  # 30 second timeout
            raise HTTPException(status_code=500, detail=f"Scan [{scanId}] failed to initialize within timeout.")
        time.sleep(1)

    return {"status": "SUCCESS", "scan_id": scanId}

@app.post("/rerunscanmulti", response_model=ScanMultiRerunResponse, tags=["Scans"])
def rerun_scan_multi(request: ScanMultiRerunRequest, db: SpiderFootDb = Depends(get_db)):
    """Rerun multiple scans.

    Args:
        request: request with comma separated list of scan IDs to rerun

    Returns:
        dict: JSON containing status and list of new scan IDs or errors
    """
    # Snapshot the current configuration to be used by the scan
    cfg = deepcopy(config)
    results = {"started": [], "errors": []}
    
    for scan_id in request.ids.split(","):
        info = db.scanInstanceGet(scan_id)
        if not info:
            results["errors"].append({"id": scan_id, "error": "Invalid scan ID."})
            continue

        scanconfig = db.scanConfigGet(scan_id)
        if not scanconfig:
            results["errors"].append({"id": scan_id, "error": f"Error loading config from scan: {scan_id}"})
            continue

        scanname = info[0]
        scantarget = info[1]
        targetType = None

        modlist = scanconfig['_modulesenabled'].split(',')
        if "sfp__stor_stdout" in modlist:
            modlist.remove("sfp__stor_stdout")

        targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
        if not targetType:
            targetType = SpiderFootHelpers.targetTypeFromString(f'"{scantarget}"')

        if targetType not in ["HUMAN_NAME", "BITCOIN_ADDRESS"]:
            scantarget = scantarget.lower()

        # Start running a new scan
        scanId = SpiderFootHelpers.genScanInstanceId()
        try:
            p = mp.Process(target=startSpiderFootScanner, args=(
                loggingQueue, scanname, scanId, scantarget, targetType, modlist, cfg))
            p.daemon = True
            p.start()
            results["started"].append({"original_id": scan_id, "new_id": scanId})
        except Exception as e:
            log.error(f"[-] Scan [{scanId}] failed: {e}", exc_info=True)
            results["errors"].append({"id": scan_id, "error": f"Scan [{scanId}] failed to start: {e}"})

    return results

@app.post("/resultsetfp", response_model=Union[List, ErrorResponse], tags=["Data"])
def result_set_fp(request: SetFpRequest, db: SpiderFootDb = Depends(get_db)):
    """Set a bunch of results (hashes) as false positive.

    Args:
        request: request with scan ID, result IDs, and FP value

    Returns:
        list: ['SUCCESS', message] or error JSON
    """
    if request.fp not in ["0", "1"]:
        raise HTTPException(status_code=400, detail="Invalid FP value, must be 0 or 1.")

    try:
        ids = request.resultids.split(',')
        if not ids:
            raise HTTPException(status_code=400, detail="No result IDs provided.")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result IDs format.")

    status = db.scanInstanceGet(request.id)
    if not status:
        raise HTTPException(status_code=404, detail="Scan ID not found.")

    if request.fp == "0":
        parents = db.scanElementParents(request.id, ids)
        if parents:
            parent_fps = db.scanResultGet(request.id, ids=parents)
            for p_fp in parent_fps:
                if p_fp[10] == 1:
                    raise HTTPException(status_code=400, detail=f"Cannot mark as not FP as parent element {p_fp[4]} is marked as FP.")

    childs = db.scanElementChildrenAll(request.id, ids)
    allIds = ids + childs

    try:
        ret = db.scanResultsUpdateFP(request.id, allIds, request.fp)
        if ret:
            return ["SUCCESS", f"FP status updated for {len(allIds)} elements."]
        else:
            raise HTTPException(status_code=500, detail="Failed to update FP status in database.")
    except Exception as e:
        log.error(f"Error updating FP status for scan {request.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Exception updating FP status: {e}")

@app.post("/savesettingsraw", response_model=Union[List, ErrorResponse], tags=["Configuration"])
def save_settings_raw(request: SaveSettingsRequest):
    """Save settings passed as a JSON string.

    Args:
        request: request with settings JSON and token

    Returns:
        list: ['SUCCESS', message] or error JSON
    """
    global config, token
    
    if str(request.token) != str(token):
        raise HTTPException(status_code=403, detail="Invalid token.")

    if request.allopts == "RESET":
        try:
            dbh = SpiderFootDb(config)
            dbh.configClear()
            config = deepcopy(defaultConfig)
            token = random.SystemRandom().randint(0, 99999999)
            return ["SUCCESS", "Settings reset to default."]
        except Exception as e:
            log.error(f"Error resetting settings: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error resetting settings: {e}")

    try:
        newopts = json.loads(request.allopts)
        if not isinstance(newopts, dict):
            raise ValueError("Invalid format for settings, must be a JSON object.")

        error, updated_config = ApiHelpers.save_config(config, newopts)
        if error:
            raise HTTPException(status_code=error["status_code"], detail=error["message"])
            
        config = updated_config
        token = random.SystemRandom().randint(0, 99999999)
        return ["SUCCESS", "Settings saved."]
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for settings.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Error saving settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error saving settings: {e}")

@app.get("/correlationrules", tags=["Data"])
def correlation_rules():
    """List all correlation rules.

    Returns:
        list: list of correlation rule dictionaries [{'id': id, 'name': name, 'descr': descr}]
    """
    global config
    
    ret = list()

    rules = config.get('__correlationrules__')
    if not rules:
        return ret

    for r in rules:
        meta = r.get('meta', {})
        ret.append({
            'id': r.get('id', 'Unknown ID'),
            'name': meta.get('name', 'Unknown Name'),
            'descr': meta.get('description', 'No description available.')
        })

    return sorted(ret, key=itemgetter('name'))

@app.get("/query", tags=["Utilities"])
def query(query: str = Query(..., description="SQL SELECT query")):
    """For the CLI to run SELECT queries against the database.

    Args:
        query: SQL SELECT query

    Returns:
        dict: {'success': bool, 'data': results or error message}
    """
    dbh = SpiderFootDb(config)

    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if not query.lower().strip().startswith("select"):
        raise HTTPException(status_code=403, detail="Only SELECT queries are allowed.")

    try:
        res = dbh.dbh.execute(query)
        return {"success": True, "data": res.fetchall()}
    except Exception as e:
        log.error(f"Error executing query '{query}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query execution failed: {e}")

@app.post("/vacuum", response_model=VacuumResponse, tags=["Utilities"])
def vacuum(db: SpiderFootDb = Depends(get_db)):
    """Trigger database vacuum.

    Returns:
        dict: Status of the vacuum operation
    """
    try:
        log.info("Starting database vacuum...")
        db.vacuum()
        log.info("Database vacuum finished.")
        return {"status": "SUCCESS", "message": "Database vacuum completed."}
    except Exception as e:
        log.error(f"Database vacuum failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database vacuum failed: {e}")

# Enhanced startup handler to properly load configuration
@app.on_event("startup")
async def startup_event():
    global config, defaultConfig, loggingQueue
    
    # Create a logging queue
    loggingQueue = mp.Queue()
    logListenerSetup(loggingQueue)
    log = logging.getLogger("spiderfoot.fastapi_app")
    
    # The config should be passed through environment variable
    config_json = os.environ.get('SPIDERFOOT_CONFIG')
    if config_json:
        try:
            config = json.loads(config_json)
            defaultConfig = deepcopy(config)
            log.info("Configuration loaded from environment variable")
        except json.JSONDecodeError:
            log.error("Failed to parse configuration from environment variable")
            config = {}
    else:
        # Load the configuration from file as fallback
        config_path = os.environ.get('SPIDERFOOT_CONFIG_PATH', 
                                     os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                                 "spiderfoot.cfg"))
        
        try:
            sf = SpiderFoot({})
            config = sf.loadConfig(config_path)
            defaultConfig = deepcopy(config)
            
            # Load modules and rules
            config = ApiHelpers.load_modules_and_rules(config)
            log.info("Configuration loaded from file")
        except Exception as e:
            log.error(f"Failed to load configuration: {e}", exc_info=True)
            config = {}
    
    log.info("FastAPI SpiderFoot API started")

# Add middleware for logging and error handling
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        log.debug(f"Request {request.method} {request.url.path} completed in {process_time:.4f}s with status {response.status_code}")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        log.error(f"Request {request.method} {request.url.path} failed after {process_time:.4f}s: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": {"http_status": 500, "message": str(e)}},
        )

# Add static file support for any additional documentation
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")), name="static")

# Redirect root to Swagger UI for convenience
@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/swaggerui")
