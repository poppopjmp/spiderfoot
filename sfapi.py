"""
FastAPI implementation for SpiderFoot API
This runs alongside the existing CherryPy web application
"""

import asyncio
import json
import logging
import multiprocessing as mp
import os
import time
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

# SpiderFoot imports - corrected based on codebase structure
from sflib import SpiderFoot
from spiderfoot.db import SpiderFootDb
from spiderfoot import SpiderFootHelpers
from sfscan import startSpiderFootScanner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()

class Config:
    """Configuration management"""
    def __init__(self):
        # Initialize with default config like sf.py does
        default_config = {
            '__modules__': {},
            '__correlationrules__': [],
            '_debug': False,
            'webaddr': '127.0.0.1',
            'webport': '5001',
            '__webaddr_apikey': None,  # Will be set later
            '__database': 'spiderfoot.db'  # Add default database path
        }
        self.sf = SpiderFoot(default_config)
        # Load the actual config from database
        dbh = SpiderFootDb(default_config, init=True)
        loaded_config = self.sf.configUnserialize(dbh.configGet(), default_config)
        
        # Handle both real dictionaries and mock objects during testing
        if hasattr(loaded_config, 'copy') and callable(loaded_config.copy):
            try:
                self.config = loaded_config.copy()
            except:
                # If copy fails (mock object), convert to dict
                self.config = dict(loaded_config) if loaded_config else default_config.copy()
        elif isinstance(loaded_config, dict):
            self.config = loaded_config.copy()
        else:
            # For mock objects or other types, try to convert to dict or use default
            try:
                self.config = dict(loaded_config) if loaded_config else default_config.copy()
            except:
                self.config = default_config.copy()
        
        # Ensure __database is always set
        if not self.config.get('__database'):
            self.config['__database'] = 'spiderfoot.db'
            
        self.db = SpiderFootDb(self.config)
        
    def get_config(self):
        return self.config
    
    def update_config(self, updates: dict):
        for key, value in updates.items():
            self.config[key] = value
        return self.config

# Global config instance - make it conditional for testing
app_config = None

def get_app_config():
    """Get or create the global app config instance"""
    global app_config
    if app_config is None:
        app_config = Config()
    return app_config

# Initialize config if not in test environment
if not os.getenv('TESTING_MODE'):
    app_config = Config()

# Set up logging queue for scans
import multiprocessing as mp
from spiderfoot.logger import logListenerSetup, logWorkerSetup

# Create global logging queue for scan processes
api_logging_queue = mp.Queue()
if app_config:
    logListenerSetup(api_logging_queue, app_config.get_config())

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
    source_event: str
    confidence: int
    visibility: int
    risk: int
    created: datetime
    hash: Optional[str] = None

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
    config = get_app_config().get_config()
    expected_token = config.get('__webaddr_apikey', '')
    
    if not expected_token:
        # For development/testing, you might want to allow access without API key
        # In production, this should always require a key
        logger.warning("No API key configured - allowing access")
        return token
    
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
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
        config = get_app_config().get_config()
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
        updated_config = get_app_config().update_config(config_update.config)
        return {"message": "Configuration updated", "config": updated_config}
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")

@app.get("/api/modules", dependencies=[Depends(verify_token)])
async def get_modules():
    """Get available modules"""
    try:
        config = get_app_config().get_config()
        modules = config.get('__modules__', {})
        
        module_list = []
        for module_name, module_info in modules.items():
            try:
                module_data = ModuleInfo(
                    name=module_info.get('name', module_name),
                    category=module_info.get('cats', ['Unknown'])[0] if module_info.get('cats') else 'Unknown',
                    description=module_info.get('descr', 'No description'),
                    flags=module_info.get('labels', []),
                    dependencies=[]  # Not stored in module info
                )
                module_list.append(module_data.dict())
            except Exception as e:
                logger.warning(f"Could not process module {module_name}: {e}")
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
        scans = get_app_config().db.scanInstanceList()
        
        # Apply pagination
        total = len(scans)
        paginated_scans = scans[offset:offset + limit]
        
        scan_list = []
        for scan_data in paginated_scans:
            # Handle the scan data format properly
            scan_response = ScanResponse(
                scan_id=scan_data[0],
                name=scan_data[1],
                target=scan_data[2],
                status=scan_data[5] if len(scan_data) > 5 else 'UNKNOWN',
                created=datetime.fromtimestamp(scan_data[3]) if scan_data[3] else datetime.now(),
                started=datetime.fromtimestamp(scan_data[4]) if scan_data[4] and scan_data[4] != 0 else None,
                ended=datetime.fromtimestamp(scan_data[4]) if len(scan_data) > 6 and scan_data[6] and scan_data[6] != 0 else None
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
        config = get_app_config().get_config()
        available_modules = config.get('__modules__', {})
        
        if scan_request.modules:
            # Validate requested modules exist
            invalid_modules = [m for m in scan_request.modules if m not in available_modules]
            if invalid_modules:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid modules: {', '.join(invalid_modules)}"
                )
            modules = scan_request.modules
        else:
            # Use all available modules
            modules = list(available_modules.keys())
          # Create scan in database
        app_config.db.scanInstanceCreate(scan_id, scan_request.name, scan_request.target)
        
        # Start scan using the same method as web UI
        scan_config = config.copy()
        scan_config['_modulesenabled'] = ','.join(modules)
          # Start scan process with correct signature: (loggingQueue, scanName, scanId, targetValue, targetType, moduleList, globalOpts)
        
        p = mp.Process(target=startSpiderFootScanner, args=(
            api_logging_queue, scan_request.name, scan_id, scan_request.target, target_type, modules, scan_config
        ))
        p.daemon = True
        p.start()
        
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
            status=scan_info[5] if len(scan_info) > 5 else 'UNKNOWN',
            created=datetime.fromtimestamp(scan_info[3]) if scan_info[3] else datetime.now(),
            started=datetime.fromtimestamp(scan_info[4]) if scan_info[4] and scan_info[4] != 0 else None,
            ended=datetime.fromtimestamp(scan_info[6]) if len(scan_info) > 6 and scan_info[6] and scan_info[6] != 0 else None
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

@app.post("/api/scans/{scan_id}/stop", dependencies=[Depends(verify_token)])
async def stop_scan(scan_id: str):
    """Stop a running scan"""
    try:
        scan_info = app_config.db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        if scan_info[5] != 'RUNNING':
            raise HTTPException(status_code=400, detail="Scan is not running")
        
        # Set scan status to stopping
        app_config.db.scanInstanceSet(scan_id, None, None, 'ABORT-REQUESTED')
        
        return {"message": "Scan stop requested", "scan_id": scan_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop scan")

@app.get("/api/scans/{scan_id}/status", dependencies=[Depends(verify_token)])
async def get_scan_status(scan_id: str):
    """Get scan status and progress"""
    try:
        scan_info = app_config.db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get event counts for progress
        events = app_config.db.scanResultEvent(scan_id, 'ALL')
        event_count = len(events)
        
        # Get unique event types
        event_types = set()
        for event in events:
            event_types.add(event[4])
        
        return {
            "scan_id": scan_id,
            "status": scan_info[5] if len(scan_info) > 5 else 'UNKNOWN',
            "event_count": event_count,
            "event_types": list(event_types),
            "started": datetime.fromtimestamp(scan_info[4]).isoformat() if scan_info[4] and scan_info[4] != 0 else None,
            "ended": datetime.fromtimestamp(scan_info[6]).isoformat() if len(scan_info) > 6 and scan_info[6] and scan_info[6] != 0 else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scan status {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scan status")

@app.get("/api/event-types", dependencies=[Depends(verify_token)])
async def get_event_types():
    """Get available event types"""
    try:
        dbh = app_config.db
        event_types = dbh.eventTypes()
        return {"event_types": event_types}
    except Exception as e:
        logger.error(f"Error getting event types: {e}")
        raise HTTPException(status_code=500, detail="Failed to get event types")

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
        
        # Use the same method as web UI
        events = app_config.db.scanResultEvent(scan_id, event_types[0] if event_types else 'ALL')
        
        # Apply pagination
        total = len(events)
        paginated_events = events[offset:offset + limit]
        
        event_list = []
        for event_data in paginated_events:
            event_response = EventResponse(
                event_id=str(event_data[11]),  # rowid
                scan_id=event_data[12],       # scan_instance_id
                event_type=event_data[4],     # event_type
                data=event_data[1],           # event_data
                module=event_data[3],         # module
                source_event=event_data[10] if event_data[10] else '',  # source_event_id
                confidence=event_data[6],     # confidence
                visibility=event_data[7],     # visibility
                risk=event_data[8],           # risk
                created=datetime.fromtimestamp(event_data[0]) if event_data[0] else datetime.now(),
                hash=event_data[9] if len(event_data) > 9 else None
            )
            event_list.append(event_response.dict())
        
        return {
            "events": event_list,
            "total": total,
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
        
        events = app_config.db.scanResultEvent(scan_id, 'ALL')
        
        if format == "json":
            def generate_json():
                yield '{"scan_id": "' + scan_id + '", "events": ['
                for i, event in enumerate(events):
                    if i > 0:
                        yield ","
                    event_dict = {
                        "event_type": event[4],
                        "data": event[1],
                        "module": event[3],
                        "confidence": event[6],
                        "created": datetime.fromtimestamp(event[0]).isoformat() if event[0] else None
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
                    created_str = datetime.fromtimestamp(event[0]).isoformat() if event[0] else ''
                    yield f'"{event[4]}","{event[1]}","{event[3]}",{event[6]},"{created_str}"\n'
            
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

# WebSocket support for real-time updates
@app.websocket("/api/scans/{scan_id}/stream")
async def websocket_scan_stream(websocket, scan_id: str):
    """WebSocket endpoint for real-time scan updates"""
    await websocket.accept()
    
    try:
        last_event_count = 0
        
        while True:
            # Get latest events
            events = app_config.db.scanResultEvent(scan_id, 'ALL')
            
            if len(events) > last_event_count:
                # Send only new events
                new_events = events[last_event_count:]
                await websocket.send_json({
                    "type": "events",
                    "scan_id": scan_id,
                    "events": [
                        {
                            "event_type": event[4],
                            "data": event[1],
                            "module": event[3],
                            "created": datetime.fromtimestamp(event[0]).isoformat() if event[0] else None
                        } for event in new_events
                    ]
                })
                last_event_count = len(events)
            
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
