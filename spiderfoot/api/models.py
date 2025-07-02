"""
Pydantic models for SpiderFoot API
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
from datetime import datetime

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
