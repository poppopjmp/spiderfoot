from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import BaseModel
from typing import List
import asyncio
import uuid
import csv
import io

from spiderfoot import SpiderFootHelpers
from spiderfoot.__version__ import __version__
from spiderfoot.scan_controller import start_spiderfoot_scanner, SpiderFootScanController
from spiderfoot.target import SpiderFootTarget
from spiderfoot.db import SpiderFootDb
from spiderfoot.logger import logListenerSetup, logWorkerSetup

app = FastAPI()

config = {
    "token": "",  # Set your token here if you want to use authentication
}

sfConfig_API = {
    "_debug": False,  # Debug
    "_maxthreads": 3,  # Number of modules to run concurrently
    "__logging": True,  # Logging in general
    "__outputfilter": None,  # Event types to filter from modules' output
    # User-Agent to use for HTTP requests
    "_useragent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0",
    "_dnsserver": "",  # Override the default resolver
    "_fetchtimeout": 5,  # number of seconds before giving up on a fetch
    "_internettlds": "https://publicsuffix.org/list/effective_tld_names.dat",
    "_internettlds_cache": 72,
    "_genericusers": ",".join(
        SpiderFootHelpers.usernamesFromWordlists(["generic-usernames"])
    ),
    "__database": f"{SpiderFootHelpers.dataPath()}/spiderfoot.db",
    "__modules__": None,  # List of modules. Will be set after start-up.
    # List of correlation rules. Will be set after start-up.
    "__correlationrules__": None,
    "_socks1type": "",
    "_socks2addr": "",
    "_socks3port": "",
    "_socks4user": "",
    "_socks5pwd": "",
}

try:
    log_listener = logListenerSetup(loggingQueue=None, opts=sfConfig_API)
    log = logWorkerSetup(loggingQueue=None)
except Exception as e:
    print(f"Error setting up logging: {e}")
    log = None


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
    if (
        credentials.username != correct_username or
        credentials.password != correct_password
    ):
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
        "Access-Control-Allow-Headers": "Content-Type",
    }


def initialize_spiderfoot(use_postgresql: bool = False):
    """
    Initialize and configure the SpiderFoot instance.

    Args:
        use_postgresql (bool): Whether to use PostgreSQL as the database.

    Returns:
        SpiderFoot: The initialized SpiderFoot instance.
    """
    sfConfig_API = {
        "_debug": False,
        "_maxthreads": 3,
        "__logging": True,
        "__outputfilter": None,
        "_useragent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0",
        "_dnsserver": "",
        "_fetchtimeout": 5,
        "_internettlds": "https://publicsuffix.org/list/effective_tld_names.dat",
        "_internettlds_cache": 72,
        "_genericusers": ",".join(
            SpiderFootHelpers.usernamesFromWordlists(["generic-usernames"])
        ),
        "__database": (
            "postgresql://user:password@localhost/spiderfoot"
            if use_postgresql
            else f"{SpiderFootHelpers.dataPath()}/spiderfoot.db"
        ),
        "__modules__": None,
        "__correlationrules__": None,
        "_socks1type": "",
        "_socks2addr": "",
        "_socks3port": "",
        "_socks4user": "",
        "_socks5pwd": "",
    }
    return SpiderFoot(sfConfig_API)


def handle_database_interactions(use_postgresql: bool = False):
    """
    Handle the database interactions required by SpiderFoot.

    Args:
        use_postgresql (bool): Whether to use PostgreSQL as the database.

    Returns:
        SpiderFootDb: The database handler.
    """
    sf = initialize_spiderfoot(use_postgresql)
    return SpiderFootDb(sf.config)


def run_spiderfoot_scan(target: str, modules: List[str], use_postgresql: bool = False):
    """Runs the SpiderFoot scan synchronously."""
    sf = initialize_spiderfoot(use_postgresql)
    target_obj = SpiderFootTarget(target)
    sf.setTarget(target_obj)
    sf.setModules(modules)
    scan_id = start_spiderfoot_scanner(sf)
    return scan_id


async def run_spiderfoot_scan_async(
    target: str, modules: List[str], use_postgresql: bool = False
):
    """Runs the SpiderFoot scan in a separate thread/process."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, run_spiderfoot_scan, target, modules, use_postgresql
    )


@app.post("/start_scan")
async def start_scan(
    scan_request: ScanRequest,
    background_tasks: BackgroundTasks,
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """Start a new scan with the specified target and modules."""
    try:
        scan_id = await run_spiderfoot_scan_async(
            scan_request.target, scan_request.modules, use_postgresql
        )
        return {"scan_id": scan_id}

    except TypeError as e:
        log.error(f"TypeError during start_scan: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error during start_scan: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/stop_scan/{scan_id}")
async def stop_scan(
    scan_id: str,
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """Stop a running scan with the specified scan ID."""
    try:
        uuid.UUID(scan_id)  # validate UUID
        dbh = handle_database_interactions(use_postgresql)
        dbh.scanInstanceSet(scan_id, status="ABORTED")
        return {"message": "Scan stopped successfully"}
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid scan_id format. Must be UUID."
        )
    except TypeError as e:
        log.error(f"TypeError during stop_scan: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error during stop_scan: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/modules")
async def list_modules(
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    List all available modules.

    Returns:
        dict: A list of available modules.
    """
    try:
        sf = initialize_spiderfoot(use_postgresql)
        modules = sf.listModules()
        return {"modules": modules}
    except Exception as e:
        log.error(f"Unexpected error in list_modules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/scan_results/{scan_id}")
async def get_scan_results(
    scan_id: str,
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """Get the scan results for the specified scan ID."""
    try:
        uuid.UUID(scan_id)  # Validate UUID
        dbh = handle_database_interactions(use_postgresql)
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
async def list_active_scans(
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    List all active scans.

    Returns:
        dict: A list of active scans.
    """
    try:
        dbh = handle_database_interactions(use_postgresql)
        active_scans = dbh.scanInstanceList()
        return {"active_scans": active_scans}
    except Exception as e:
        log.error(f"Unexpected error in list_active_scans: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/scan_status/{scan_id}")
async def get_scan_status(
    scan_id: str,
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    Get the status of a scan with the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve the status for.

    Returns:
        dict: The status of the scan.
    """
    try:
        sf = initialize_spiderfoot(use_postgresql)
        status = sf.getScanStatus(scan_id)
        return {"status": status}
    except TypeError as e:
        log.error(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/scan_history")
async def list_scan_history(
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    List the history of all scans.

    Returns:
        dict: A list of scan history.
    """
    try:
        sf = initialize_spiderfoot(use_postgresql)
        history = sf.listScanHistory()
        return {"history": history}
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/export_scan_results/{scan_id}")
async def export_scan_results(
    scan_id: str,
    export_format: str,
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    Export the scan results for the specified scan ID in the specified format.

    Args:
        scan_id (str): The scan ID of the scan to export results for.
        export_format (str): The format to export the results in.

    Returns:
        dict: The exported scan results.
    """
    try:
        sf = initialize_spiderfoot(use_postgresql)
        exported_results = sf.exportScanResults(scan_id, export_format)
        return {"exported_results": exported_results}
    except TypeError as e:
        log.error(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/import_api_key")
async def import_api_key(
    api_key_request: APIKeyRequest,
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    Import an API key for a specific module.

    Args:
        api_key_request (APIKeyRequest): The API key request containing the module and key.

    Returns:
        dict: A message indicating the API key was imported successfully.
    """
    try:
        sf = initialize_spiderfoot(use_postgresql)
        sf.importApiKey(api_key_request.module, api_key_request.key)
        return {"message": "API key imported successfully"}
    except TypeError as e:
        log.error(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/export_api_keys")
async def export_api_keys(
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    Export all API keys.

    Returns:
        dict: A list of exported API keys.
    """
    try:
        sf = initialize_spiderfoot(use_postgresql)
        api_keys = sf.exportApiKeys()
        return {"api_keys": api_keys}
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/scan_correlations/{scan_id}")
async def get_scan_correlations(
    scan_id: str,
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    Get the scan correlations for the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve correlations for.

    Returns:
        dict: The scan correlations.
    """
    try:
        sf = initialize_spiderfoot(use_postgresql)
        correlations = sf.getScanCorrelations(scan_id)
        return {"correlations": correlations}
    except TypeError as e:
        log.error(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/scan_logs/{scan_id}")
async def get_scan_logs(
    scan_id: str,
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    Get the scan logs for the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve logs for.

    Returns:
        dict: The scan logs.
    """
    try:
        sf = initialize_spiderfoot(use_postgresql)
        logs = sf.getScanLogs(scan_id)
        return {"logs": logs}
    except TypeError as e:
        log.error(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/scan_summary/{scan_id}")
async def get_scan_summary(
    scan_id: str,
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    Get the scan summary for the specified scan ID.

    Args:
        scan_id (str): The scan ID of the scan to retrieve the summary for.

    Returns:
        dict: The scan summary.
    """
    try:
        sf = initialize_spiderfoot(use_postgresql)
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
        version=__version__,
        description="REST API documentation for SpiderFoot",
        routes=app.routes,
    )


@app.get("/docs")
async def get_swagger_ui():
    """Get the Swagger UI for the API."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="SpiderFoot REST API")


@app.get("/export_scan_results/{scan_id}/csv")
async def export_scan_results_csv(
    scan_id: str,
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    Export the scan results for the specified scan ID in CSV format.

    Args:
        scan_id (str): The scan ID of the scan to export results for.

    Returns:
        StreamingResponse: The exported scan results in CSV format.
    """
    try:
        dbh = handle_database_interactions(use_postgresql)
        results = dbh.scanResultEvent(scan_id)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["module", "data", "type", "source",
                "falsescore", "generated", "updated"]
        )

        for result in results:
            writer.writerow(result)

        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=scan_results_{scan_id}.csv"
            },
        )
    except Exception as e:
        log.error(
            f"Unexpected error in export_scan_results_csv: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/export_scan_results/{scan_id}/json")
async def export_scan_results_json(
    scan_id: str,
    credentials: HTTPBasicCredentials = Depends(authenticate),
    use_postgresql: bool = False,
):
    """
    Export the scan results for the specified scan ID in JSON format.

    Args:
        scan_id (str): The scan ID of the scan to export results for.

    Returns:
        JSONResponse: The exported scan results in JSON format.
    """
    try:
        dbh = handle_database_interactions(use_postgresql)
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
        log.error(
            f"Unexpected error in export_scan_results_json: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail:str(e)) from e


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


def handle_scan_status(scan_id: str):
    """
    Handle the scan status and results retrieval.

    Args:
        scan_id (str): The scan ID of the scan to retrieve the status for.

    Returns:
        dict: The scan status and results.
    """
    dbh = handle_database_interactions()
    status = dbh.scanInstanceGet(scan_id)
    results = dbh.scanResultEvent(scan_id)
    return {"status": status, "results": results}


def handle_correlation_rules(scan_id: str):
    """
    Handle the correlation rules and their execution.

    Args:
        scan_id (str): The scan ID of the scan to execute correlation rules for.

    Returns:
        dict: The correlation rules and their execution results.
    """
    dbh = handle_database_interactions()
    correlations = dbh.scanCorrelate(scan_id)
    return {"correlations": correlations}


def handle_logging_and_error_handling():
    """
    Handle the logging and error handling mechanisms required by SpiderFoot.
    """
    log_listener = logListenerSetup(loggingQueue=None, opts=sfConfig_API)
    log = logWorkerSetup(loggingQueue=None)
    return log_listener, log


def error_page(message, status_code=404) -> JSONResponse:
    """Create a JSON error response.

    Args:
        message: Error message
        status_code: HTTP status code

    Returns:
        JSONResponse: A formatted JSON error response
    """
    message_dict = {"error": message, "status_code": status_code}
    return JSONResponse(status_code=status_code, content=message_dict)


@app.exception_handler(404)
def not_found(request: Request, exc: HTTPException) -> JSONResponse:
    return error_page("Resource not found.", 404)


@app.exception_handler(500)
def internal_error(request: Request, exc: HTTPException) -> JSONResponse:
    return error_page("Internal server error.", 500)


@app.exception_handler(400)
def bad_request(request: Request, exc: HTTPException) -> JSONResponse:
    return error_page("Bad request.", 400)


@app.exception_handler(401)
def unauthorized(request: Request, exc: HTTPException) -> JSONResponse:
    return error_page("Unauthorized", 401)


@app.exception_handler(403)
def forbidden(request: Request, exc: HTTPException) -> JSONResponse:
    return error_page("Forbidden", 403)


@app.exception_handler(405)
def method_not_allowed(request: Request, exc: HTTPException) -> JSONResponse:
    return error_page("Method not allowed", 405)


def check_auth(request: Request) -> bool:
    """Check authentication if set"""
    if not config.get("token"):
        return True
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return False
    try:
        auth_type, auth_token = auth_header.split(" ", 1)
        if auth_type.lower() == "bearer" and auth_token == config["token"]:
            return True
    except ValueError:
        return False
    return False


@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    """Middleware to handle authentication for all requests."""
    if not check_auth(request):
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})
    response = await call_next(request)
    return response
