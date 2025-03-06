from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List
from spiderfoot import SpiderFootTarget
from sflib import SpiderFoot
from sfscan import startSpiderFootScanner
from spiderfoot import SpiderFootDb
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI()

class ScanRequest(BaseModel):
    target: str
    modules: List[str]

class APIKeyRequest(BaseModel):
    module: str
    key: str

@app.get("/")
async def read_root():
    """
    Root endpoint for the SpiderFoot API.

    Returns:
        dict: A welcome message.
    """
    return {"message": "Welcome to SpiderFoot API"}


@app.options("/start_scan")
async def options_start_scan():
    """
    Options endpoint for the start_scan route.

    Returns:
        dict: Allowed methods and headers for the start_scan route.
    """
    return {
        "Allow": "POST, OPTIONS",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

@app.options("/active_scans")
async def options_active_scans():
    """
    Options endpoint for the active_scans route.

    Returns:
        dict: Allowed methods and headers for the active_scans route.
    """
    return {
        "Allow": "GET, OPTIONS",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

@app.options("/modules")
async def options_modules():
    """
    Options endpoint for the modules route.

    Returns:
        dict: Allowed methods and headers for the modules route.
    """
    return {
        "Allow": "GET, OPTIONS",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

@app.options("/configure_module")
async def options_configure_module():
    """
    Options endpoint for the configure_module route.

    Returns:
        dict: Allowed methods and headers for the configure_module route.
    """
    return {
        "Allow": "POST, OPTIONS",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

@app.options("/export_scan_results")
async def options_export_scan_results():
    """
    Options endpoint for the export_scan_results route.

    Returns:
        dict: Allowed methods and headers for the export_scan_results route.
    """
    return {
        "Allow": "GET, OPTIONS",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

@app.options("/scan_correlations")
async def options_scan_correlations():
    """
    Options endpoint for the scan_correlations route.

    Returns:
        dict: Allowed methods and headers for the scan_correlations route.
    """
    return {
        "Allow": "GET, OPTIONS",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

@app.options("/scan_logs")
async def options_scan_logs():
    """
    Options endpoint for the scan_logs route.

    Returns:
        dict: Allowed methods and headers for the scan_logs route.
    """
    return {
        "Allow": "GET, OPTIONS",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

@app.options("/scan_summary")
async def options_scan_summary():
    """
    Options endpoint for the scan_summary route.

    Returns:
        dict: Allowed methods and headers for the scan_summary route.
    """
    return {
        "Allow": "GET, OPTIONS",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

def run_spiderfoot_scan(target: str, modules: List[str]):
    """Runs the SpiderFoot scan synchronously."""
    sf = SpiderFoot()
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
async def start_scan(scan_request: ScanRequest, background_tasks: BackgroundTasks):
    """Start a new scan with the specified target and modules."""
    try:
        scan_id = await run_spiderfoot_scan_async(scan_request.target, scan_request.modules)
        return {"scan_id": scan_id}

    except TypeError as e:
        logger.error(f"TypeError during start_scan: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error during start_scan: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.post("/stop_scan/{scan_id}")
async def stop_scan(scan_id: str):
    """Stop a running scan with the specified scan ID."""
    try:
        uuid.UUID(scan_id) #validate UUID
        dbh = SpiderFootDb()
        dbh.scanInstanceSet(scan_id, status="ABORTED")
        return {"message": "Scan stopped successfully"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scan_id format. Must be UUID.")
    except TypeError as e:
        logger.error(f"TypeError during stop_scan: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error during stop_scan: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/modules")
async def list_modules():
    """
    List all available modules.

    Returns:
        dict: A list of available modules.
    """
    try:
        sf = SpiderFoot()
        modules = sf.listModules()
        return {"modules": modules}
    except Exception as e:
        logger.error(f"Unexpected error in list_modules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_results/{scan_id}")
async def get_scan_results(scan_id: str):
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
        logger.error(f"Unexpected error in get_scan_results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/active_scans")
async def list_active_scans():
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
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_status/{scan_id}")
async def get_scan_status(scan_id: str):
    """
    Get the status of a scan with the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve the status for.

    Returns:
        dict: The status of the scan.
    """
    try:
        sf = SpiderFoot()
        status = sf.getScanStatus(scan_id)
        return {"status": status}
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_history")
async def list_scan_history():
    """
    List the history of all scans.

    Returns:
        dict: A list of scan history.
    """
    try:
        sf = SpiderFoot()
        history = sf.listScanHistory()
        return {"history": history}
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/export_scan_results/{scan_id}")
async def export_scan_results(scan_id: str, export_format: str):
    """
    Export the scan results for the specified scan ID in the specified format.

    Args:
        scan_id (str): The scan ID of the scan to export results for.
        export_format (str): The format to export the results in.

    Returns:
        dict: The exported scan results.
    """
    try:
        sf = SpiderFoot()
        exported_results = sf.exportScanResults(scan_id, export_format)
        return {"exported_results": exported_results}
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.post("/import_api_key")
async def import_api_key(api_key_request: APIKeyRequest):
    """
    Import an API key for a specific module.

    Args:
        api_key_request (APIKeyRequest): The API key request containing the module and key.

    Returns:
        dict: A message indicating the API key was imported successfully.
    """
    try:
        sf = SpiderFoot()
        sf.importApiKey(api_key_request.module, api_key_request.key)
        return {"message": "API key imported successfully"}
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/export_api_keys")
async def export_api_keys():
    """
    Export all API keys.

    Returns:
        dict: A list of exported API keys.
    """
    try:
        sf = SpiderFoot()
        api_keys = sf.exportApiKeys()
        return {"api_keys": api_keys}
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_correlations/{scan_id}")
async def get_scan_correlations(scan_id: str):
    """
    Get the scan correlations for the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve correlations for.

    Returns:
        dict: The scan correlations.
    """
    try:
        sf = SpiderFoot()
        correlations = sf.getScanCorrelations(scan_id)
        return {"correlations": correlations}
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_logs/{scan_id}")
async def get_scan_logs(scan_id: str):
    """
    Get the scan logs for the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve logs for.

    Returns:
        dict: The scan logs.
    """
    try:
        sf = SpiderFoot()
        logs = sf.getScanLogs(scan_id)
        return {"logs": logs}
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_summary/{scan_id}")
async def get_scan_summary(scan_id: str):
    """
    Get the scan summary for the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve the summary for.

    Returns:
        dict: The scan summary.
    """
    try:
        sf = SpiderFoot()
        summary = sf.getScanSummary(scan_id)
        return {"summary": summary}
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
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
