from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import List
from spiderfoot import SpiderFootTarget
from sflib import SpiderFoot
from spiderfoot.db import SpiderFootDb
from spiderfoot.logger import logListenerSetup, logWorkerSetup
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html
import asyncio, logging
from spiderfoot import SpiderFootHelpers
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import JSONResponse, StreamingResponse
import csv
import io
import uuid

app = FastAPI()

sfConfig_API = {
    '_debug': False,  # Debug
    '_maxthreads': 3,  # Number of modules to run concurrently
    '__logging': True,  # Logging in general
    '__outputfilter': None,  # Event types to filter from modules' output
    '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',  # User-Agent to use for HTTP requests
    '_dnsserver': '',  # Override the default resolver
    '_fetchtimeout': 5,  # number of seconds before giving up on a fetch
    '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
    '_internettlds_cache': 72,
    '_genericusers': ",".join(SpiderFootHelpers.usernamesFromWordlists(['generic-usernames'])),
    '__database': f"{SpiderFootHelpers.dataPath()}/spiderfoot.db",
    '__modules__': None,  # List of modules. Will be set after start-up.
    '__correlationrules__': None,  # List of correlation rules. Will be set after start-up.
    '_socks1type': '',
    '_socks2addr': '',
    '_socks3port': '',
    '_socks4user': '',
    '_socks5pwd': '',
}

log_listener = logListenerSetup(loggingQueue=None, opts=sfConfig_API)
log = logWorkerSetup(loggingQueue=None)

class ScanRequest(BaseModel):
    target: str
    modules: List[str]

class APIKeyRequest(BaseModel):
    module: str
    key: str

security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = "admin"
    correct_password = "password"
    if credentials.username != correct_username or credentials.password != correct_password:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/")
async def read_root():
    """
    Root endpoint for the SpiderFoot API.

    Returns:
        dict: A welcome message.
    """
    return {"message": "Welcome to SpiderFoot API"}

@app.options("/{path:path}")
async def options_handler(path: str):
    """
    Options endpoint for handling HTTP OPTIONS requests.

    Args:
        path (str): The path for which the OPTIONS request is made.

    Returns:
        dict: Allowed methods and headers for the specified path.
    """
    return {
        "Allow": "GET, POST, OPTIONS",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

def run_spiderfoot_scan(target: str, modules: List[str]):
    """Runs the SpiderFoot scan synchronously."""
    sf = SpiderFoot(sfConfig_API)
    target_obj = SpiderFootTarget(target)
    sf.setTarget(target_obj)
    sf.setModules(modules)
    scan_id = startSpiderFootScanner(sf)
    return scan_id

async def run_spiderfoot_scan_async(target: str, modules: List[str]):
    """Runs the SpiderFoot scan in a separate thread/process."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, run_spiderfoot_scan, target, modules)

@app.post("/start_scan")
async def start_scan(scan_request: ScanRequest, background_tasks: BackgroundTasks, credentials: HTTPBasicCredentials = Depends(authenticate)):
    """Start a new scan with the specified target and modules."""
    try:
        scan_id = await run_spiderfoot_scan_async(scan_request.target, scan_request.modules)
        return {"scan_id": scan_id}

    except TypeError as e:
        log.error(f"TypeError during start_scan: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error during start_scan: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.post("/stop_scan/{scan_id}")
async def stop_scan(scan_id: str, credentials: HTTPBasicCredentials = Depends(authenticate)):
    """Stop a running scan with the specified scan ID."""
    try:
        uuid.UUID(scan_id) #validate UUID
        dbh = SpiderFootDb()
        dbh.scanInstanceSet(scan_id, status="ABORTED")
        return {"message": "Scan stopped successfully"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scan_id format. Must be UUID.")
    except TypeError as e:
        log.error(f"TypeError during stop_scan: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error during stop_scan: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/modules")
async def list_modules(credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    List all available modules.

    Returns:
        dict: A list of available modules.
    """
    try:
        sf = SpiderFoot(sfConfig_API)
        modules = sf.listModules()
        return {"modules": modules}
    except Exception as e:
        log.error(f"Unexpected error in list_modules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_results/{scan_id}")
async def get_scan_results(scan_id: str, credentials: HTTPBasicCredentials = Depends(authenticate)):
    """Get the scan results for the specified scan ID."""
    try:
        uuid.UUID(scan_id)  # Validate UUID
        dbh = SpiderFootDb()
        results = dbh.scanResultEvent(scan_id)

        formatted_results = []
        for result in results:
            formatted_result = {
                "module": result[0],
                "data": result[1],
                "type": result[2],
                "source": result[3],
                "falsescore": result[4],
                "generated": result[5],
                "updated": result[6],
            }
            formatted_results.append(formatted_result)

        return {"results": formatted_results}
    except Exception as e:
        log.error(f"Unexpected error in get_scan_results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/active_scans")
async def list_active_scans(credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    List all active scans.

    Returns:
        dict: A list of active scans.
    """
    try:
        dbh = SpiderFootDb()
        active_scans = dbh.scanInstanceList()
        return {"active_scans": active_scans}
    except Exception as e:
        log.error(f"Unexpected error in list_active_scans: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_status/{scan_id}")
async def get_scan_status(scan_id: str, credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    Get the status of a scan with the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve the status for.

    Returns:
        dict: The status of the scan.
    """
    try:
        sf = SpiderFoot(sfConfig_API)
        status = sf.getScanStatus(scan_id)
        return {"status": status}
    except TypeError as e:
        log.error(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_history")
async def list_scan_history(credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    List the history of all scans.

    Returns:
        dict: A list of scan history.
    """
    try:
        sf = SpiderFoot(sfConfig_API)
        history = sf.listScanHistory()
        return {"history": history}
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/export_scan_results/{scan_id}")
async def export_scan_results(scan_id: str, export_format: str, credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    Export the scan results for the specified scan ID in the specified format.

    Args:
        scan_id (str): The scan ID of the scan to export results for.
        export_format (str): The format to export the results in.

    Returns:
        dict: The exported scan results.
    """
    try:
        sf = SpiderFoot(sfConfig_API)
        exported_results = sf.exportScanResults(scan_id, export_format)
        return {"exported_results": exported_results}
    except TypeError as e:
        log.error(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.post("/import_api_key")
async def import_api_key(api_key_request: APIKeyRequest, credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    Import an API key for a specific module.

    Args:
        api_key_request (APIKeyRequest): The API key request containing the module and key.

    Returns:
        dict: A message indicating the API key was imported successfully.
    """
    try:
        sf = SpiderFoot(sfConfig_API)
        sf.importApiKey(api_key_request.module, api_key_request.key)
        return {"message": "API key imported successfully"}
    except TypeError as e:
        log.error(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/export_api_keys")
async def export_api_keys(credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    Export all API keys.

    Returns:
        dict: A list of exported API keys.
    """
    try:
        sf = SpiderFoot(sfConfig_API)
        api_keys = sf.exportApiKeys()
        return {"api_keys": api_keys}
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_correlations/{scan_id}")
async def get_scan_correlations(scan_id: str, credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    Get the scan correlations for the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve correlations for.

    Returns:
        dict: The scan correlations.
    """
    try:
        sf = SpiderFoot(sfConfig_API)
        correlations = sf.getScanCorrelations(scan_id)
        return {"correlations": correlations}
    except TypeError as e:
        log.error(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_logs/{scan_id}")
async def get_scan_logs(scan_id: str, credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    Get the scan logs for the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve logs for.

    Returns:
        dict: The scan logs.
    """
    try:
        sf = SpiderFoot(sfConfig_API)
        logs = sf.getScanLogs(scan_id)
        return {"logs": logs}
    except TypeError as e:
        log.error(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_summary/{scan_id}")
async def get_scan_summary(scan_id: str, credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    Get the scan summary for the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve the summary for.

    Returns:
        dict: The scan summary.
    """
    try:
        sf = SpiderFoot(sfConfig_API)
        summary = sf.getScanSummary(scan_id)
        return {"summary": summary}
    except TypeError as e:
        log.error(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/docs")
async def get_docs():
    """
    Get the Swagger-like documentation page.

    Returns:
        dict: A message indicating the documentation page.
    """
    return {"message": "Swagger-like documentation page"}

@app.get("/openapi.json")
async def get_openapi_schema():
    """Get the OpenAPI schema for the REST API."""
    return get_openapi(
        title="SpiderFoot REST API",
        version="5.0.3",
        description="REST API documentation for SpiderFoot",
        routes=app.routes,
    )

@app.get("/docs")
async def get_swagger_ui():
    """Get the Swagger UI for the API."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="SpiderFoot REST API")

@app.get("/export_scan_results/{scan_id}/csv")
async def export_scan_results_csv(scan_id: str, credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    Export the scan results for the specified scan ID in CSV format.

    Args:
        scan_id (str): The scan ID of the scan to export results for.

    Returns:
        StreamingResponse: The exported scan results in CSV format.
    """
    try:
        dbh = SpiderFootDb()
        results = dbh.scanResultEvent(scan_id)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["module", "data", "type", "source", "falsescore", "generated", "updated"])

        for result in results:
            writer.writerow(result)

        output.seek(0)
        return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=scan_results_{scan_id}.csv"})
    except Exception as e:
        logging.error(f"Unexpected error in export_scan_results_csv: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/export_scan_results/{scan_id}/json")
async def export_scan_results_json(scan_id: str, credentials: HTTPBasicCredentials = Depends(authenticate)):
    """
    Export the scan results for the specified scan ID in JSON format.

    Args:
        scan_id (str): The scan ID of the scan to export results for.

    Returns:
        JSONResponse: The exported scan results in JSON format.
    """
    try:
        dbh = SpiderFootDb()
        results = dbh.scanResultEvent(scan_id)

        formatted_results = []
        for result in results:
            formatted_result = {
                "module": result[0],
                "data": result[1],
                "type": result[2],
                "source": result[3],
                "falsescore": result[4],
                "generated": result[5],
                "updated": result[6],
            }
            formatted_results.append(formatted_result)

        return JSONResponse(content={"results": formatted_results})
    except Exception as e:
        logging.error(f"Unexpected error in export_scan_results_json: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request, exc):
    """
    Custom HTTP exception handler.

    Args:
        request: The request object.
        exc: The HTTP exception.

    Returns:
        JSONResponse: The custom error response.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

@app.exception_handler(Exception)
async def custom_exception_handler(request, exc):
    """
    Custom exception handler.

    Args:
        request: The request object.
        exc: The exception.

    Returns:
        JSONResponse: The custom error response.
    """
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred."},
    )
