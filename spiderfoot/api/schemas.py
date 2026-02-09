"""
Pydantic schemas for SpiderFoot domain objects.

These schemas define the **service-boundary contract** for data
exchanged between microservices (API ↔ Scanner ↔ WebUI) via
HTTP/gRPC.  They replace the ad-hoc dicts and positional tuples
previously used for serialisation.

Schemas are grouped by domain:
  - Event schemas: scan event data
  - Scan schemas: scan instance metadata
  - Config schemas: configuration key-value pairs
  - Log schemas: scan log entries
  - Correlation schemas: correlation result data

Usage:
    from spiderfoot.api.schemas import (
        EventCreate, EventResponse, ScanCreate, ScanResponse,
    )
"""
from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────

class ScanStatus(str, Enum):
    """Canonical scan lifecycle states."""
    CREATED = "CREATED"
    STARTING = "STARTING"
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    ABORT_REQUESTED = "ABORT-REQUESTED"
    ABORTED = "ABORTED"
    FINISHED = "FINISHED"
    ERROR_FAILED = "ERROR-FAILED"


# ── Event Schemas ────────────────────────────────────────────────────

class EventCreate(BaseModel):
    """Inbound event payload — written by scanner, stored by API."""
    event_hash: str = Field(..., min_length=1, description="SHA-256 hash identifying this event")
    event_type: str = Field(..., min_length=1, description="SpiderFoot event type (e.g. INTERNET_NAME)")
    module: str = Field(..., min_length=1, description="Module that produced the event")
    data: str = Field(..., min_length=1, description="Event payload data")
    source_event_hash: str = Field("ROOT", description="Hash of the parent event")
    confidence: int = Field(100, ge=0, le=100, description="Data confidence 0-100")
    visibility: int = Field(100, ge=0, le=100, description="Data visibility 0-100")
    risk: int = Field(0, ge=0, le=100, description="Risk score 0-100")
    false_positive: bool = Field(False, description="Marked as false positive")

    model_config = {"from_attributes": True}


class EventResponse(BaseModel):
    """Outbound event payload — returned by API to clients."""
    event_hash: str
    event_type: str
    module: str
    data: str
    source_event_hash: str = "ROOT"
    confidence: int = 100
    visibility: int = 100
    risk: int = 0
    false_positive: bool = False
    generated: float = Field(default_factory=time.time, description="Epoch timestamp")
    source_data: Optional[str] = None
    scan_id: Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_db_row(cls, row: tuple, *, scan_id: Optional[str] = None) -> "EventResponse":
        """Create from a legacy positional DB row tuple.

        Standard row layout (from SpiderFootDb):
            0: generated  1: data  2: source  3: module
            4: type  5: hash  6: confidence  7: visibility
            8: risk  9: sourceEventHash  ...  13: false_positive
        """
        try:
            return cls(
                generated=float(row[0]) if row[0] else time.time(),
                data=str(row[1]) if row[1] else "",
                source_data=str(row[2]) if len(row) > 2 and row[2] else None,
                module=str(row[3]) if len(row) > 3 and row[3] else "unknown",
                event_type=str(row[4]) if len(row) > 4 and row[4] else "UNKNOWN",
                event_hash=str(row[5]) if len(row) > 5 and row[5] else "",
                confidence=int(row[6]) if len(row) > 6 and row[6] is not None else 100,
                visibility=int(row[7]) if len(row) > 7 and row[7] is not None else 100,
                risk=int(row[8]) if len(row) > 8 and row[8] is not None else 0,
                source_event_hash=str(row[9]) if len(row) > 9 and row[9] else "ROOT",
                false_positive=bool(row[13]) if len(row) > 13 and row[13] else False,
                scan_id=scan_id,
            )
        except (IndexError, TypeError, ValueError):
            # Fallback for short rows
            return cls(
                data=str(row[1]) if len(row) > 1 else "",
                event_type=str(row[4]) if len(row) > 4 else "UNKNOWN",
                module=str(row[3]) if len(row) > 3 else "unknown",
                event_hash=str(row[5]) if len(row) > 5 else "",
                scan_id=scan_id,
            )


class EventSummary(BaseModel):
    """Aggregated event type summary for a scan."""
    event_type: str
    count: int = 0
    last_seen: Optional[float] = None

    model_config = {"from_attributes": True}


# ── Scan Schemas ─────────────────────────────────────────────────────

class ScanCreate(BaseModel):
    """Request payload for creating a new scan."""
    name: str = Field(..., min_length=1, max_length=512, description="Human-readable scan name")
    target: str = Field(..., min_length=1, description="Scan target (domain, IP, etc.)")
    modules: Optional[List[str]] = Field(None, description="Module list (None = all)")
    type_filter: Optional[List[str]] = Field(None, description="Event type filter")
    options: Optional[Dict[str, Any]] = Field(None, description="Scan-specific config overrides")

    @field_validator("target")
    @classmethod
    def target_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Target must not be blank")
        return v.strip()


class ScanResponse(BaseModel):
    """Scan instance metadata returned by the API."""
    scan_id: str
    name: str
    target: str
    status: str
    created: float = 0.0
    started: float = 0.0
    ended: float = 0.0

    model_config = {"from_attributes": True}

    @classmethod
    def from_db_row(cls, row: tuple) -> "ScanResponse":
        """Create from a ScanRecord-style tuple/row."""
        return cls(
            scan_id=str(row[0]),
            name=str(row[1]),
            target=str(row[2]),
            created=float(row[3]) if len(row) > 3 and row[3] else 0.0,
            started=float(row[4]) if len(row) > 4 and row[4] else 0.0,
            ended=float(row[5]) if len(row) > 5 and row[5] else 0.0,
            status=str(row[6]) if len(row) > 6 and row[6] else "UNKNOWN",
        )


class ScanListResponse(BaseModel):
    """Paginated list of scans."""
    scans: List[ScanResponse]
    total: int
    page: int = 1
    page_size: int = 50


# ── Log Schemas ──────────────────────────────────────────────────────

class ScanLogEntry(BaseModel):
    """Single scan log entry."""
    scan_id: str
    component: str = ""
    log_type: str = "INFO"
    message: str = ""
    timestamp: float = Field(default_factory=time.time)

    model_config = {"from_attributes": True}


class ScanLogCreate(BaseModel):
    """Payload for writing a scan log entry."""
    component: str = ""
    log_type: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    message: str = Field(..., min_length=1)


# ── Config Schemas ───────────────────────────────────────────────────

class ConfigEntry(BaseModel):
    """Single configuration key-value pair."""
    key: str = Field(..., min_length=1)
    value: Any = None
    section: Optional[str] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class ConfigUpdate(BaseModel):
    """Batch configuration update payload."""
    entries: List[ConfigEntry]
    merge: bool = Field(True, description="Merge with existing (True) or replace (False)")


# ── Correlation Schemas ──────────────────────────────────────────────

class CorrelationResult(BaseModel):
    """Single correlation finding."""
    rule_id: str
    rule_name: str
    severity: str = "info"
    description: str = ""
    matched_events: List[str] = Field(default_factory=list, description="Event hashes")
    metadata: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class CorrelationSummary(BaseModel):
    """Aggregated correlation summary for a scan."""
    scan_id: str
    total_rules_evaluated: int = 0
    total_matches: int = 0
    results: List[CorrelationResult] = Field(default_factory=list)


# ── Pagination ───────────────────────────────────────────────────────

class PaginationMeta(BaseModel):
    """Standardised pagination metadata."""
    page: int = 1
    page_size: int = 50
    total: int = 0
    total_pages: int = 0

    @classmethod
    def compute(cls, total: int, page: int = 1, page_size: int = 50) -> "PaginationMeta":
        return cls(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0,
        )


class PaginatedResponse(BaseModel):
    """Generic paginated wrapper."""
    data: List[Any]
    pagination: PaginationMeta


# ── API Response Envelopes ───────────────────────────────────────────

class MessageResponse(BaseModel):
    """Simple success/message response."""
    message: str
    success: bool = True


class ScanCreateResponse(BaseModel):
    """Response returned when a scan is created."""
    id: str
    name: str
    target: str
    status: str = "STARTING"
    message: str = "Scan created and starting"


class ScanDeleteResponse(BaseModel):
    """Response returned when a scan is deleted."""
    message: str = "Scan deleted successfully"


class ScanStopResponse(BaseModel):
    """Response returned when a scan is stopped."""
    message: str
    status: str


class ScanMetadataResponse(BaseModel):
    """Scan metadata wrapper."""
    metadata: Dict[str, Any] = {}


class ScanNotesResponse(BaseModel):
    """Scan notes wrapper."""
    notes: str = ""


class ScanRerunResponse(BaseModel):
    """Response returned when a scan is rerun."""
    new_scan_id: str
    message: str = "Scan rerun started"


class ScanCloneResponse(BaseModel):
    """Response returned when a scan is cloned."""
    new_scan_id: str
    message: str = "Scan cloned successfully"


class FalsePositiveResponse(BaseModel):
    """Response after setting false positive flags."""
    success: bool = True
    updated: int = 0


# ── Workspace response schemas ──────────────────────────────────────

class WorkspaceCreateResponse(BaseModel):
    """Response after creating a workspace."""
    workspace_id: str
    name: str
    description: str = ""
    created_time: Optional[str] = None
    message: str = "Workspace created successfully"


class WorkspaceDetailResponse(BaseModel):
    """Detailed workspace information."""
    workspace_id: str
    name: str
    description: str = ""
    created_time: Optional[str] = None
    modified_time: Optional[str] = None
    targets: list = []
    scans: list = []
    metadata: dict = {}


class WorkspaceUpdateResponse(BaseModel):
    """Response after updating a workspace."""
    workspace_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    message: str = "Workspace updated"


class WorkspaceDeleteResponse(BaseModel):
    """Response after deleting a workspace."""
    message: str
    workspace_id: str


class WorkspaceCloneResponse(BaseModel):
    """Response after cloning a workspace."""
    workspace_id: str
    name: str
    message: str = "Workspace cloned successfully"


class TargetAddResponse(BaseModel):
    """Response after adding a target."""
    target_id: str = ""
    workspace_id: str
    value: str
    target_type: str = ""
    message: str = "Target added successfully"


class TargetDeleteResponse(BaseModel):
    """Response after deleting a target."""
    message: str
    target_id: str
    workspace_id: str
