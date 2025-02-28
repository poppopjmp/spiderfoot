from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from spiderfoot import SpiderFootTarget
from sflib import SpiderFoot

app = FastAPI()

class ScanRequest(BaseModel):
    target: str
    modules: List[str]

class APIKeyRequest(BaseModel):
    module: str
    key: str

@app.get("/")
async def read_root():
    return {"message": "Welcome to SpiderFoot API"}

@app.post("/start_scan")
async def start_scan(scan_request: ScanRequest):
    try:
        sf = SpiderFoot()
        target = SpiderFootTarget(scan_request.target)
        sf.setTarget(target)
        sf.setModules(scan_request.modules)
        scan_id = sf.startScan()
        return {"scan_id": scan_id}
    except ValueError as e:
        print(f"ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.post("/stop_scan/{scan_id}")
async def stop_scan(scan_id: str):
    try:
        sf = SpiderFoot()
        sf.stopScan(scan_id)
        return {"message": "Scan stopped successfully"}
    except ValueError as e:
        print(f"ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_results/{scan_id}")
async def get_scan_results(scan_id: str):
    try:
        sf = SpiderFoot()
        results = sf.getScanResults(scan_id)
        return {"results": results}
    except ValueError as e:
        print(f"ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/modules")
async def list_modules():
    try:
        sf = SpiderFoot()
        modules = sf.listModules()
        return {"modules": modules}
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/active_scans")
async def list_active_scans():
    try:
        sf = SpiderFoot()
        active_scans = sf.listActiveScans()
        return {"active_scans": active_scans}
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_status/{scan_id}")
async def get_scan_status(scan_id: str):
    try:
        sf = SpiderFoot()
        status = sf.getScanStatus(scan_id)
        return {"status": status}
    except ValueError as e:
        print(f"ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/scan_history")
async def list_scan_history():
    try:
        sf = SpiderFoot()
        history = sf.listScanHistory()
        return {"history": history}
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/export_scan_results/{scan_id}")
async def export_scan_results(scan_id: str, export_format: str):
    try:
        sf = SpiderFoot()
        exported_results = sf.exportScanResults(scan_id, export_format)
        return {"exported_results": exported_results}
    except ValueError as e:
        print(f"ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.post("/import_api_key")
async def import_api_key(api_key_request: APIKeyRequest):
    try:
        sf = SpiderFoot()
        sf.importApiKey(api_key_request.module, api_key_request.key)
        return {"message": "API key imported successfully"}
    except ValueError as e:
        print(f"ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TypeError as e:
        print(f"TypeError: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/export_api_keys")
async def export_api_keys():
    try:
        sf = SpiderFoot()
        api_keys = sf.exportApiKeys()
        return {"api_keys": api_keys}
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/docs")
async def get_docs():
    return {"message": "Swagger-like documentation page"}
