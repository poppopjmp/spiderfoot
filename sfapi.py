#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot REST API
Complete FastAPI implementation with workspace and workflow support
Based on sfwebui.py functionality with full feature parity
"""

import argparse
import asyncio
import base64
import csv
import html
import json
import logging
import multiprocessing as mp
import openpyxl
import os
import random
import re
import sqlite3
import string
import sys
import time
from copy import deepcopy
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable
from urllib.parse import quote, unquote

from fastapi import FastAPI, HTTPException, Depends, status, Request, Query, BackgroundTasks, UploadFile, File, Form, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, PlainTextResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator
import uvicorn

# SpiderFoot imports
from sflib import SpiderFoot
from spiderfoot import SpiderFootDb
from spiderfoot import SpiderFootHelpers
from spiderfoot import __version__
from spiderfoot.workspace import SpiderFootWorkspace
from spiderfoot.workflow import SpiderFootWorkflow
from sfscan import startSpiderFootScanner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer(auto_error=False)

mp.set_start_method("spawn", force=True)

class Config:
    """Configuration management - mirrors sfwebui.py config handling"""
    def __init__(self):
        # Initialize with default config like sfwebui.py does
        default_config = {
            '__modules__': {},
            '__correlationrules__': [],
            '_debug': False,
            '__webaddr': '127.0.0.1',
            '__webport': '5001',
            '__webaddr_apikey': None,
            '__database': 'spiderfoot.db',
            '__loglevel': 'INFO',
            '__logfile': '',
            '__version__': __version__
        }
        
        # Load saved configuration from database
        self.defaultConfig = deepcopy(default_config)
        dbh = SpiderFootDb(self.defaultConfig, init=True)
        sf = SpiderFoot(self.defaultConfig)
        self.config = sf.configUnserialize(dbh.configGet(), self.defaultConfig)
        
        # Set up logging
        self.loggingQueue = mp.Queue()
        self.log = logging.getLogger("spiderfoot.api")

    def get_config(self):
        return self.config
    
    def update_config(self, updates: dict):
        for key, value in updates.items():
            self.config[key] = value
        return self.config

# Global config instance
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
from spiderfoot.logger import logListenerSetup, logWorkerSetup

# Create global logging queue for scan processes
api_logging_queue = mp.Queue()
if app_config:
    logListenerSetup(api_logging_queue, app_config.get_config())

# Pydantic models for API requests/responses
class ScanRequest(BaseModel):
    name: str = Field(..., description="Scan name")
    target: str = Field(..., description="Target to scan")
    modules: Optional[List[str]] = Field(default=None, description="List of modules to use")
    type_filter: Optional[List[str]] = Field(default=None, description="Event types to collect")
    
    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Scan name cannot be empty')
        return v
    
    @field_validator('target')
    @classmethod
    def target_must_not_be_empty(cls, v):
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

class WorkspaceRequest(BaseModel):
    name: str = Field(..., description="Workspace name")
    description: Optional[str] = Field(default="", description="Workspace description")

class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    description: str
    created_time: str
    modified_time: str
    targets: List[Dict[str, Any]]
    scans: List[Dict[str, Any]]

class TargetRequest(BaseModel):
    target: str = Field(..., description="Target value")
    target_type: str = Field(..., description="Target type")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class MultiScanRequest(BaseModel):
    targets: Optional[List[str]] = Field(default=None)
    modules: List[str] = Field(..., description="Modules to use")
    scan_options: Optional[Dict[str, Any]] = Field(default_factory=dict)

class CTIReportRequest(BaseModel):
    report_type: str = Field(default="threat_assessment")
    custom_prompt: Optional[str] = None
    output_format: str = Field(default="json")

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

# WebSocket manager for real-time updates
class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

# Authentication dependency
async def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate API key"""
    if not credentials:
        return None
    
    config = get_app_config()
    api_key = config.get_config().get('__webaddr_apikey')
    
    if api_key and credentials.credentials != api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return credentials.credentials

# Authentication dependency for optional auth
async def optional_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Optional authentication for endpoints that can work without auth"""
    if not credentials:
        return None
    return await get_api_key(credentials)

# Helper functions (mirroring sfwebui.py functionality)
def clean_user_input(input_list: list) -> list:
    """Convert data to HTML entities; except quotes and ampersands."""
    ret = []
    for item in input_list:
        if isinstance(item, str):
            c = html.escape(item, quote=False)
            ret.append(c)
        else:
            ret.append(item)
    return ret

def search_base(config: dict, scan_id: str = None, event_type: str = None, value: str = None) -> list:
    """Search functionality mirroring sfwebui.py"""
    retdata = []
    
    if not scan_id and not event_type and not value:
        return retdata
    
    if not value:
        return retdata
    
    regex = ""
    if value.startswith("/") and value.endswith("/"):
        regex = value[1:-1]
        value = ""
    
    value = value.replace('*', '%')
    if value in [None, ""] and regex in [None, ""]:
        return retdata
    
    dbh = SpiderFootDb(config)
    criteria = {
        'scan_id': scan_id or '',
        'type': event_type or '',
        'value': value or '',
        'regex': regex or '',
    }
    
    try:
        data = dbh.search(criteria, filterFp=True)
    except Exception:
        return retdata
    
    for row in data:
        lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
        escaped = html.escape(row[1])
        retdata.append([lastseen, escaped, row[2], row[3], row[4], row[5], row[10], row[11]])
    
    return retdata

def build_excel(data: list, column_names: list, sheet_name_index: int = 0) -> str:
    """Convert supplied raw data into Excel format"""
    row_nums = dict()
    workbook = openpyxl.Workbook()
    default_sheet = workbook.active
    column_names.pop(sheet_name_index)
    allowed_sheet_chars = string.ascii_uppercase + string.digits + '_'
    
    for row in data:
        if len(row) < len(column_names):
            continue
            
        sheet_name = row[sheet_name_index]
        sheet_name = ''.join(c for c in sheet_name if c in allowed_sheet_chars)[:31]
        
        if sheet_name not in workbook.sheetnames:
            if len(workbook.sheetnames) == 1 and workbook.sheetnames[0] == 'Sheet':
                sheet = default_sheet
                sheet.title = sheet_name
            else:
                sheet = workbook.create_sheet(sheet_name)
            
            row_nums[sheet_name] = 1
            for col_num, column_title in enumerate(column_names, 1):
                sheet.cell(row=1, column=col_num, value=column_title)
            row_nums[sheet_name] += 1
        else:
            sheet = workbook[sheet_name]
        
        for col_num, cell_value in enumerate([v for i, v in enumerate(row) if i != sheet_name_index], 1):
            sheet.cell(row=row_nums[sheet_name], column=col_num, value=cell_value)
        row_nums[sheet_name] += 1
    
    if row_nums:
        workbook._sheets.sort(key=lambda ws: ws.title)
    
    with BytesIO() as f:
        workbook.save(f)
        f.seek(0)
        return base64.b64encode(f.read()).decode()

# Router definitions

scan_router = APIRouter()
workspace_router = APIRouter()
data_router = APIRouter()
config_router = APIRouter()
websocket_router = APIRouter()

# Initialize websocket manager
websocket_manager = WebSocketManager()

# Create FastAPI app
app = FastAPI(
    title="SpiderFoot API",
    description="Complete REST API for SpiderFoot OSINT automation platform",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately in production
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
        content={"error": {"message": exc.detail, "status_code": exc.status_code}}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": {"message": "Internal server error", "status_code": 500}}
    )

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "version": __version__, "timestamp": time.time()}

# Scan management endpoints
@scan_router.get("/scans")
async def list_scans(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    api_key: str = Depends(optional_auth)
):
    """List all scans"""
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        scans = db.scanInstanceList()
          # Apply pagination
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
        raise HTTPException(status_code=500, detail="Failed to list scans")

@scan_router.post("/scans", status_code=201)
async def create_scan(scan_request: ScanRequest, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """Create and start a new scan"""
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        scan_id = SpiderFootHelpers.genScanInstanceId()
        target_type = SpiderFootHelpers.targetTypeFromString(scan_request.target)
        if not target_type:
            raise HTTPException(status_code=422, detail="Invalid target")
        sf = SpiderFoot(config.get_config())
        all_modules = sf.modulesProducing(['*'])
        # Use all modules if modules is None or empty
        if not scan_request.modules:
            modules = all_modules
        else:
            modules = scan_request.modules
        # Ensure at least one module (storage) is present
        if not modules:
            modules = ['sfp__stor_db']
        # Create scan instance in DB here, not in background
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

async def start_scan_background(scan_id: str, scan_name: str, target: str, 
                              target_type: str, modules: list, 
                              type_filter: list, config: dict):
    try:
        # Only start the scan, do not create scan instance here
        startSpiderFootScanner(
            api_logging_queue,
            scan_name,
            scan_id,
            target,
            target_type,
            modules,
            config
        )
    except Exception as e:
        logger.error("Failed to start scan %s: %s", scan_id, e)

@scan_router.get("/scans/{scan_id}")
async def get_scan(scan_id: str, api_key: str = Depends(optional_auth)):
    """Get scan details"""
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
        raise HTTPException(status_code=500, detail="Failed to get scan")

@scan_router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str, api_key: str = Depends(get_api_key)):
    """Delete a scan"""
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        
        # Check if scan exists
        scan_info = db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Delete scan
        db.scanInstanceDelete(scan_id)
        
        return {"message": "Scan deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete scan")

@scan_router.post("/scans/{scan_id}/stop")
async def stop_scan(scan_id: str, api_key: str = Depends(get_api_key)):
    """Stop a running scan"""
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        
        # Check if scan exists
        scan_info = db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Set scan status to aborted
        db.scanInstanceSet(scan_id, None, None, "ABORTED")
        
        return {"message": "Scan stopped successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop scan")

@scan_router.get("/scans/{scan_id}/events")
async def get_scan_events(
    scan_id: str,
    event_types: Optional[List[str]] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    api_key: str = Depends(optional_auth)
):
    """Get scan events/results"""
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        
        # Check if scan exists
        scan_info = db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get scan events
        events = db.scanResultEvent(scan_id, event_types or ['ALL'])
        
        # Apply pagination
        paginated_events = events[offset:offset + limit]
        
        events_list = []
        for event in paginated_events:
            events_list.append({
                "time": event[0],
                "data": event[1], 
                "source_data": event[2],
                "module": event[3],
                "event_type": event[4],
                "confidence": event[6],
                "visibility": event[7],
                "risk": event[8],
                "hash": event[9] if len(event) > 9 else None
            })
        
        return {
            "events": events_list,
            "total": len(events),
            "offset": offset,
            "limit": limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scan events for {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scan events")

@scan_router.get("/scans/{scan_id}/export")
async def export_scan(
    scan_id: str,
    format: str = Query("json", pattern="^(json|csv|xml)$"),
    api_key: str = Depends(optional_auth)
):
    """Export scan results"""
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        
        # Check if scan exists
        scan_info = db.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get all events
        events = db.scanResultEvent(scan_id, ['ALL'])
        
        if format == "csv":
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(['Time', 'Event Type', 'Module', 'Data', 'Source', 'Confidence', 'Visibility', 'Risk'])
            
            for event in events:
                writer.writerow([
                    event[0], event[4], event[3], event[1], 
                    event[2], event[6], event[7], event[8]
                ])
            
            csv_content = output.getvalue()
            output.close()
            
            return StreamingResponse(
                BytesIO(csv_content.encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=scan_{scan_id}.csv"}
            )
        elif format == "xml":
            # Basic XML export
            xml_content = f"<?xml version='1.0' encoding='UTF-8'?>\n<scan id='{scan_id}'>\n"
            for event in events:
                xml_content += f"  <event type='{event[4]}' module='{event[3]}' time='{event[0]}'>\n"
                xml_content += f"    <data>{html.escape(str(event[1]))}</data>\n"
                xml_content += f"    <confidence>{event[6]}</confidence>\n"
                xml_content += f"  </event>\n"
            xml_content += "</scan>"
            
            return PlainTextResponse(
                xml_content,
                media_type="application/xml",
                headers={"Content-Disposition": f"attachment; filename=scan_{scan_id}.xml"}
            )
        else:
            # JSON format
            events_list = []
            for event in events:
                events_list.append({
                    "time": event[0],
                    "data": event[1],
                    "source": event[2],
                    "module": event[3],
                    "type": event[4],
                    "confidence": event[6],
                    "visibility": event[7],
                    "risk": event[8]
                })
            
            return {"scan_id": scan_id, "events": events_list}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to export scan")

# Workspace management endpoints  
@workspace_router.get("/workspaces")
async def list_workspaces(api_key: str = Depends(optional_auth)):
    """List all workspaces"""
    try:
        config = get_app_config()
        workspaces = SpiderFootWorkspace.list_workspaces(config.get_config())
        return {"workspaces": workspaces}
    except Exception as e:
        logger.error(f"Failed to list workspaces: {e}")
        raise HTTPException(status_code=500, detail="Failed to list workspaces")

@workspace_router.post("/workspaces", status_code=201)
async def create_workspace(workspace_request: WorkspaceRequest, api_key: str = Depends(get_api_key)):
    """Create a new workspace"""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), name=workspace_request.name)
        workspace.description = workspace_request.description
        workspace.save_workspace()
        
        return {
            "workspace_id": workspace.workspace_id,
            "name": workspace.name,
            "description": workspace.description,
            "created_time": workspace.created_time,
            "message": "Workspace created successfully"
        }
    except Exception as e:
        logger.error(f"Failed to create workspace: {e}")
        raise HTTPException(status_code=500, detail="Failed to create workspace")

@workspace_router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str, api_key: str = Depends(optional_auth)):
    """Get workspace details"""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        
        return {
            "workspace_id": workspace.workspace_id,
            "name": workspace.name,
            "description": workspace.description,
            "created_time": workspace.created_time,
            "modified_time": workspace.modified_time,
            "targets": workspace.get_targets(),
            "scans": workspace.get_scans(),
            "metadata": workspace.metadata
        }
    except ValueError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except Exception as e:
        logger.error(f"Failed to get workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get workspace")

@workspace_router.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str, api_key: str = Depends(get_api_key)):
    """Delete a workspace"""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        workspace.delete_workspace()
        
        return {"message": "Workspace deleted successfully"}
    except ValueError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except Exception as e:
        logger.error(f"Failed to delete workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete workspace")

@workspace_router.post("/workspaces/{workspace_id}/targets", status_code=201)
async def add_target(workspace_id: str, target_request: TargetRequest, api_key: str = Depends(get_api_key)):
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        # Validate target_type
        valid_type = SpiderFootHelpers.targetTypeFromString(target_request.target)
        if not valid_type or valid_type != target_request.target_type:
            raise HTTPException(status_code=422, detail="Invalid target type")
        target_id = workspace.add_target(
            target_request.target,
            target_request.target_type,
            target_request.metadata
        )
        return {
            "target_id": target_id,
            "message": "Target added successfully"
        }
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except Exception as e:
        logger.error(f"Failed to add target to workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to add target")

@workspace_router.get("/workspaces/{workspace_id}/targets")
async def list_targets(workspace_id: str, api_key: str = Depends(optional_auth)):
    """List workspace targets"""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        
        targets = workspace.get_targets()
        return {"targets": targets}
    except ValueError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except Exception as e:
        logger.error(f"Failed to list targets for workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list targets")

@workspace_router.delete("/workspaces/{workspace_id}/targets/{target_id}")
async def remove_target(workspace_id: str, target_id: str, api_key: str = Depends(get_api_key)):
    """Remove target from workspace"""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        
        success = workspace.remove_target(target_id)
        if not success:
            raise HTTPException(status_code=404, detail="Target not found")
        
        return {"message": "Target removed successfully"}
    except ValueError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove target {target_id} from workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove target")

@workspace_router.post("/workspaces/{workspace_id}/multi-scan")
async def start_multi_scan(workspace_id: str, multi_scan_request: MultiScanRequest,
                          background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """Start multi-target scan"""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        
        # Get targets from workspace if not provided
        targets = multi_scan_request.targets
        if not targets:
            workspace_targets = workspace.get_targets()
            targets = [t['value'] for t in workspace_targets]
        
        if not targets:
            raise HTTPException(status_code=400, detail="No targets available for scanning")
        
        # Create workflow for multi-target scan
        from spiderfoot.workflow import SpiderFootWorkflow
        workflow = SpiderFootWorkflow(config.get_config(), workspace)
        
        # Start multi-target scan in background
        background_tasks.add_task(
            start_multi_scan_background,
            workflow,
            targets,
            multi_scan_request.modules,
            multi_scan_request.scan_options
        )
        
        return {
            "workflow_id": workflow.workflow_id,
            "targets": targets,
            "modules": multi_scan_request.modules,
            "message": f"Multi-target scan started for {len(targets)} targets"
        }
    except ValueError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except Exception as e:
        logger.error(f"Failed to start multi-scan: {e}")
        raise HTTPException(status_code=500, detail="Failed to start multi-scan")

async def start_multi_scan_background(workflow, targets: List[str], 
                                    modules: List[str], scan_options: Dict[str, Any]):
    """Start multi-target scan in background"""
    try:
        # Convert targets to proper format
        target_objects = []
        for target in targets:
            target_type = SpiderFootHelpers.targetTypeFromString(target)
            target_objects.append({
                'value': target,
                'type': target_type
            })
        
        workflow.start_multi_target_scan(target_objects, modules, scan_options)
    except Exception as e:
        logger.error(f"Failed to start multi-target scan: {e}")

# Configuration endpoints
@config_router.get("/config")
async def get_config_endpoint(api_key: str = Depends(optional_auth)):
    """Get current configuration"""
    try:
        config = get_app_config()
        # Return only safe configuration items
        safe_config = {
            k: v for k, v in config.get_config().items() 
            if not k.startswith('__') or k in ['__version__', '__database']
        }
        return {"config": safe_config}
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get configuration")

@config_router.get("/modules")
async def get_modules(api_key: str = Depends(optional_auth)):
    """Get available modules"""
    try:
        config = get_app_config()
        
        # Use the same approach as sfwebui.py
        modules_list = []
        for mod in config.get_config()['__modules__']:
            if "__" in mod:
                continue
            
            module_config = config.get_config()['__modules__'][mod]
            module_info = {
                "name": mod,
                "category": module_config.get('cats', ['Unknown'])[0] if module_config.get('cats') else 'Unknown',
                "description": module_config.get('descr', 'No description'),
                "flags": module_config.get('labels', []),
                "dependencies": module_config.get('deps', []),
                "provides": module_config.get('provides', []),
                "consumes": module_config.get('consumes', []),
                "group": module_config.get('group', [])
            }
            modules_list.append(module_info)
        
        return {"modules": sorted(modules_list, key=lambda x: x['name'])}
    except Exception as e:
        logger.error(f"Failed to get modules: {e}")
        raise HTTPException(status_code=500, detail="Failed to get modules")

@config_router.get("/event-types")
async def get_event_types(api_key: str = Depends(optional_auth)):
    """Get available event types"""
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        
        event_types = db.eventTypes()
        return {"event_types": event_types}
    except Exception as e:
        logger.error(f"Failed to get event types: {e}")
        raise HTTPException(status_code=500, detail="Failed to get event types")

# WebSocket support for real-time updates
@websocket_router.websocket("/scans/{scan_id}")
async def websocket_scan_stream(websocket: WebSocket, scan_id: str):
    """WebSocket endpoint for real-time scan updates"""
    await websocket_manager.connect(websocket)
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        
        # Check if scan exists
        scan_info = db.scanInstanceGet(scan_id)
        if not scan_info:
            await websocket.send_text(json.dumps({"error": "Scan not found"}))
            return
        
        last_event_count = 0
        
        while True:
            # Get current scan status and events
            current_scan_info = db.scanInstanceGet(scan_id)
            events = db.scanResultEvent(scan_id, ['ALL'])
            
            # Send status update
            if current_scan_info:
                await websocket.send_text(json.dumps({
                    "type": "status_update",
                    "scan_id": scan_id,
                    "status": current_scan_info[6],
                    "event_count": len(events),
                    "timestamp": time.time()
                }))
            
            # Send new events if any
            if len(events) > last_event_count:
                new_events = events[last_event_count:]
                await websocket.send_text(json.dumps({
                    "type": "new_events",
                    "scan_id": scan_id,
                    "events": [
                        {
                            "event_type": event[4],
                            "data": event[1],
                            "module": event[3],
                            "created": datetime.fromtimestamp(event[0]).isoformat() if event[0] else None
                        } for event in new_events
                    ]
                }))
                last_event_count = len(events)
            
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error for scan {scan_id}: {e}")

# Include routers
app.include_router(scan_router, prefix="/api", tags=["scans"])
app.include_router(workspace_router, prefix="/api", tags=["workspaces"])
app.include_router(data_router, prefix="/api", tags=["data"])
app.include_router(config_router, prefix="/api", tags=["configuration"])
app.include_router(websocket_router, prefix="/ws", tags=["websockets"])

# Main function to run the API
def main():
    """Main function to run the FastAPI application"""
    
    parser = argparse.ArgumentParser(description='SpiderFoot REST API Server')
    parser.add_argument('-H', '--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('-p', '--port', type=int, default=8001, help='Port to bind to')
    parser.add_argument('-c', '--config', help='Configuration file path')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    
    args = parser.parse_args()
      # Load custom config if provided
    if args.config:
        global app_config
        app_config = Config()
    
    uvicorn.run(
        "sfapi:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
