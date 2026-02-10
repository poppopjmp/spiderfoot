"""
Pydantic models for SpiderFoot API
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Any
from datetime import datetime

class ScanRequest(BaseModel):
    """Data model for a scan creation request."""
    name: str = Field(..., description="Scan name")
    target: str = Field(..., description="Target to scan")
    modules: list[str] | None = Field(default=None, description="List of modules to use")
    type_filter: list[str] | None = Field(default=None, description="Event types to collect")
    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Scan name cannot be empty')
        return v
    @field_validator('target')
    @classmethod
    def target_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Target cannot be empty')
        return v

class ScanResponse(BaseModel):
    """Data model for a scan status response."""
    scan_id: str
    name: str
    target: str
    status: str
    created: datetime
    started: datetime | None = None
    ended: datetime | None = None

class WorkspaceRequest(BaseModel):
    """Data model for a workspace creation request."""
    name: str = Field(..., description="Workspace name")
    description: str | None = Field(default="", description="Workspace description")

class WorkspaceResponse(BaseModel):
    """Data model for a workspace details response."""
    workspace_id: str
    name: str
    description: str
    created_time: str
    modified_time: str
    targets: list[dict[str, Any]]
    scans: list[dict[str, Any]]

class TargetRequest(BaseModel):
    """Data model for a scan target specification."""
    target: str = Field(..., description="Target value")
    target_type: str = Field(..., description="Target type")
    metadata: dict[str, Any] | None = Field(default_factory=dict)

class MultiScanRequest(BaseModel):
    """Data model for a multi-target scan request."""
    targets: list[str] | None = Field(default=None)
    modules: list[str] = Field(..., description="Modules to use")
    scan_options: dict[str, Any] | None = Field(default_factory=dict)

class CTIReportRequest(BaseModel):
    """Data model for a CTI report generation request."""
    report_type: str = Field(default="threat_assessment")
    custom_prompt: str | None = None
    output_format: str = Field(default="json")

class EventResponse(BaseModel):
    """Data model for a scan event response."""
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
    hash: str | None = None

class ModuleInfo(BaseModel):
    """Data model for module metadata."""
    name: str
    category: str
    description: str
    flags: list[str]
    dependencies: list[str]
    documentation_url: str | None = None

class ApiKeyModel(BaseModel):
    """Data model for API key authentication."""
    key: str = Field(..., description="API key")

class ConfigUpdate(BaseModel):
    """Data model for a configuration update request."""
    config: dict[str, Any] = Field(..., description="Configuration updates")
