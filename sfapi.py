"""
FastAPI implementation for SpiderFoot API
This runs alongside the existing CherryPy web application
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, status, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, validator
import uvicorn

# SpiderFoot imports
from spiderfoot import SpiderFoot
from sflib import SpiderFootDb, SpiderFootHelpers, SpiderFootPlugin
from sfwebui import SpiderFootWebUi

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()

class Config:
    """Configuration management"""
    def __init__(self):
        self.sf = SpiderFoot({})
        self.config = self.sf.configUnserialize(self.sf.configSerialize())
        self.db = SpiderFootDb(self.config)
        
    def get_config(self):
        return self.config
    
    def update_config(self, updates: dict):
        for key, value in updates.items():
            self.config[key] = value
        return self.config

# Global config instance
app_config = Config()

# Pydantic models
class ScanRequest(BaseModel):
    name: str = Field(..., description="Scan name")
    target: str = Field(..., description="Target to scan")
    modules: Optional[List[str]] = Field(default=None, description="List of modules to use")
    type_filter: Optional[List[str]] = Field(default=None, description="Event types to collect")
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Scan name cannot be empty')
        return v
    
    @validator('target')
    def target_must_be_valid(cls, v):
        if not v.strip():
            raise ValueError('Target cannot be empty')
        return v

class ScanResponse(BaseModel):
    scan_id: str
    name: str
    target: str
    status: str
    created: datetime
    started: Optional[datetime] = None
    ended: Optional[datetime] = None

class EventResponse(BaseModel):
    event_id: str
    scan_id: str
    event_type: str
    data: str
    module: str
    confidence: int
    visibility: int
    risk: int
    created: datetime
    updated: datetime

class ModuleInfo(BaseModel):
    name: str
    category: str
    description: str
    flags: List[str]
    dependencies: List[str]
    documentation_url: Optional[str] = None

class ApiKeyModel(BaseModel):
    key: str = Field(..., description="API key")

class ConfigUpdate(BaseModel):
    config: Dict[str, Any] = Field(..., description="Configuration updates")

# Authentication
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API token"""
    token = credentials.credentials
    expected_token = app_config.get_config().get('__webaddr_apikey', '')
    
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key not configured"
        )
    
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return token

# FastAPI app
app = FastAPI(
    title="SpiderFoot API",
    description="Comprehensive OSINT automation platform API",
    version="4.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error",
            "status_code": 500
        }
    )

# API Routes
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "4.0.0"
    }

@app.get("/api/config", dependencies=[Depends(verify_token)])
async def get_config():
    """Get current configuration"""
    try:
        config = app_config.get_config()
        # Remove sensitive information
        safe_config = {k: v for k, v in config.items() if not k.startswith('__')}
        return {"config": safe_config}
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get configuration")

@app.post("/api/config", dependencies=[Depends(verify_token)])
async def update_config(config_update: ConfigUpdate):
    """Update configuration"""
    try:
        updated_config = app_config.update_config(config_update.config)
        return {"message": "Configuration updated", "config": updated_config}
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")

@app.get("/api/modules", dependencies=[Depends(verify_token)])
async def get_modules():
    """Get available modules"""
    try:
        sf = SpiderFoot(app_config.get_config())
        modules = sf.modulesProducing(['*'])
        
        module_list = []
        for module_name in modules:
            try:
                module = __import__(f'modules.{module_name}', fromlist=[module_name])
                module_class = getattr(module, f'sfp_{module_name}')
                instance = module_class()
                
                module_info = ModuleInfo(
                    name=module_name,
                    category=getattr(instance, 'meta', {}).get('category', 'Unknown'),
                    description=getattr(instance, 'meta', {}).get('summary', 'No description'),
                    flags=getattr(instance, 'meta', {}).get('flags', []),
                    dependencies=getattr(instance, 'meta', {}).get('dependencies', []),
                    documentation_url=getattr(instance, 'meta', {}).get('documentation_url')
                )
                module_list.append(module_info.dict())
            except Exception as e:
                logger.warning(f"Could not load module {module_name}: {e}")
                continue
        
        return {"modules": module_list}
    except Exception as e:
        logger.error(f"Error getting modules: {e}")
        raise HTTPException(status_code=500, detail="Failed to get modules")

@app.get("/api/scans", dependencies=[Depends(verify_token)])
async def get_scans(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get list of scans"""
    try:
        scans = app_config.db.scanInstanceList()
        
        # Apply pagination
        total = len(scans)
        paginated_scans = scans[offset:offset + limit]
        
        scan_list = []
        for scan_data in paginated_scans:
            scan_response = ScanResponse(
                scan_id=scan_data[0],
                name=scan_data[1],
                target=scan_data[2],
                status=scan_data[4],
                created=datetime.fromisoformat(scan_data[3]),
                started=datetime.fromisoformat(scan_data[5]) if scan_data[5] else None,
                ended=datetime.fromisoformat(scan_data[6]) if scan_data[6] else None
            )
            scan_list.append(scan_response.dict())
        
        return {
            "scans": scan_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error getting scans: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scans")

@app.post("/api/scans", dependencies=[Depends(verify_token)])
async def create_scan(scan_request: ScanRequest):
    """Create a new scan"""
    try:
        scan_id = SpiderFootHelpers.genScanInstanceId()
        
        # Validate target
        target_type = SpiderFootHelpers.targetTypeFromString(scan_request.target)
        if not target_type:
            raise HTTPException(status_code=400, detail="Invalid target format")
        
        # Set up modules
        if scan_request.modules:
            modules = scan_request.modules
        else:
            sf = SpiderFoot(app_config.get_config())
            modules = list(sf.modulesProducing(['*']).keys())
        
        # Create scan in database
        app_config.db.scanInstanceCreate(scan_id, scan_request.name, scan_request.target)
        
        # Start scan asynchronously
        asyncio.create_task(run_scan(scan_id, scan_request.target, modules, scan_request.type_filter))
        
        return {
            "scan_id": scan_id,
            "message": "Scan created and started",
            "name": scan_request.name,
            "target": scan_request.target
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating scan: {e}")
        raise HTTPException(status_code=500, detail="Failed to create scan")

@app.get("/api/scans/{scan_id}", dependencies=[Depends(verify_token)])
async def get_scan(scan_id: str):
    """Get scan details"""
    try:
        scan_info = app_config.db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        scan_response = ScanResponse(
            scan_id=scan_info[0],
            name=scan_info[1],
            target=scan_info[2],
            status=scan_info[4],
            created=datetime.fromisoformat(scan_info[3]),
            started=datetime.fromisoformat(scan_info[5]) if scan_info[5] else None,
            ended=datetime.fromisoformat(scan_info[6]) if scan_info[6] else None
        )
        
        return scan_response.dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scan")

@app.delete("/api/scans/{scan_id}", dependencies=[Depends(verify_token)])
async def delete_scan(scan_id: str):
    """Delete a scan"""
    try:
        scan_info = app_config.db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Stop scan if running
        if scan_info[4] == 'RUNNING':
            app_config.db.scanInstanceSet(scan_id, None, None, 'ABORTED')
        
        # Delete scan data
        app_config.db.scanInstanceDelete(scan_id)
        
        return {"message": "Scan deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete scan")

@app.get("/api/scans/{scan_id}/events", dependencies=[Depends(verify_token)])
async def get_scan_events(
    scan_id: str,
    event_types: Optional[List[str]] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0)
):
    """Get events for a scan"""
    try:
        scan_info = app_config.db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        events = app_config.db.scanEventsList(scan_id, limit, event_types)
        
        event_list = []
        for event_data in events[offset:offset + limit]:
            event_response = EventResponse(
                event_id=str(event_data[0]),
                scan_id=event_data[1],
                event_type=event_data[2],
                data=event_data[3],
                module=event_data[4],
                confidence=event_data[5],
                visibility=event_data[6],
                risk=event_data[7],
                created=datetime.fromisoformat(event_data[8]),
                updated=datetime.fromisoformat(event_data[9])
            )
            event_list.append(event_response.dict())
        
        return {
            "events": event_list,
            "total": len(events),
            "scan_id": scan_id,
            "limit": limit,
            "offset": offset
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting events for scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scan events")

@app.get("/api/scans/{scan_id}/export", dependencies=[Depends(verify_token)])
async def export_scan(
    scan_id: str,
    format: str = Query("json", regex="^(json|csv|xml)$")
):
    """Export scan results"""
    try:
        scan_info = app_config.db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        events = app_config.db.scanEventsList(scan_id)
        
        if format == "json":
            def generate_json():
                yield '{"scan_id": "' + scan_id + '", "events": ['
                for i, event in enumerate(events):
                    if i > 0:
                        yield ","
                    event_dict = {
                        "event_type": event[2],
                        "data": event[3],
                        "module": event[4],
                        "confidence": event[5],
                        "created": event[8]
                    }
                    yield json.dumps(event_dict)
                yield "]}"
            
            return StreamingResponse(
                generate_json(),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=scan_{scan_id}.json"}
            )
        
        elif format == "csv":
            def generate_csv():
                yield "event_type,data,module,confidence,created\n"
                for event in events:
                    yield f'"{event[2]}","{event[3]}","{event[4]}",{event[5]},"{event[8]}"\n'
            
            return StreamingResponse(
                generate_csv(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=scan_{scan_id}.csv"}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to export scan")

# Utility functions
async def run_scan(scan_id: str, target: str, modules: List[str], type_filter: Optional[List[str]]):
    """Run a scan asynchronously"""
    try:
        config = app_config.get_config()
        sf = SpiderFoot(config)
        
        # Update scan status
        app_config.db.scanInstanceSet(scan_id, datetime.utcnow().isoformat(), None, 'RUNNING')
        
        # Configure modules
        modlist = []
        if modules:
            for module in modules:
                if module in sf.modulesProducing(['*']):
                    modlist.append(module)
        else:
            modlist = list(sf.modulesProducing(['*']).keys())
        
        # Start scan
        sf.startScan(scan_id, target, modlist, type_filter or [])
        
        # Update scan status on completion
        app_config.db.scanInstanceSet(scan_id, None, datetime.utcnow().isoformat(), 'FINISHED')
        
    except Exception as e:
        logger.error(f"Error running scan {scan_id}: {e}")
        app_config.db.scanInstanceSet(scan_id, None, datetime.utcnow().isoformat(), 'ERROR-FAILED')

# WebSocket support for real-time updates
@app.websocket("/api/scans/{scan_id}/stream")
async def websocket_scan_stream(websocket, scan_id: str):
    """WebSocket endpoint for real-time scan updates"""
    await websocket.accept()
    
    try:
        while True:
            # Get latest events
            events = app_config.db.scanEventsList(scan_id, 10)
            
            if events:
                await websocket.send_json({
                    "type": "events",
                    "scan_id": scan_id,
                    "events": [
                        {
                            "event_type": event[2],
                            "data": event[3],
                            "module": event[4],
                            "created": event[8]
                        } for event in events
                    ]
                })
            
            await asyncio.sleep(2)
            
    except Exception as e:
        logger.error(f"WebSocket error for scan {scan_id}: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    # Configuration
    host = os.getenv("FASTAPI_HOST", "127.0.0.1")
    port = int(os.getenv("FASTAPI_PORT", "8001"))
    
    # Run the application
    uvicorn.run(
        "sfapi:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )
