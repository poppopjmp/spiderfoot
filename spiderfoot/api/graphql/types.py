"""
GraphQL type definitions for SpiderFoot domain objects.

Each Strawberry type mirrors an existing Pydantic schema or database
entity, providing a graph-friendly view of scan data that's ideal
for visualization dashboards.
"""
from __future__ import annotations

import strawberry
from typing import Optional


# ── Core Types ──────────────────────────────────────────────────────


@strawberry.type
class ScanType:
    """A SpiderFoot scan instance."""
    scan_id: str
    name: str
    target: str
    status: str
    created: float
    started: float
    ended: float

    @strawberry.field
    def duration_seconds(self) -> float:
        """Wall-clock scan duration in seconds (0 if not finished)."""
        if self.ended and self.started:
            return self.ended - self.started
        return 0.0

    @strawberry.field
    def is_running(self) -> bool:
        """Whether the scan is currently running."""
        return self.status in ("RUNNING", "STARTING", "STARTED")


@strawberry.type
class EventType:
    """A single scan result / event."""
    event_hash: str
    event_type: str
    module: str
    data: str
    source_event_hash: str
    confidence: int
    visibility: int
    risk: int
    false_positive: bool
    generated: float
    scan_id: Optional[str] = None


@strawberry.type
class EventTypeSummary:
    """Aggregated count of events per type for a scan."""
    event_type: str
    count: int
    last_seen: Optional[float] = None


@strawberry.type
class CorrelationType:
    """A correlation finding from rule evaluation."""
    correlation_id: str
    rule_id: str
    rule_name: str
    title: str
    severity: str
    description: str
    matched_event_count: int


@strawberry.type
class ScanLogType:
    """A log entry from scan execution."""
    timestamp: float
    component: str
    log_type: str
    message: str


@strawberry.type
class ModuleType:
    """A SpiderFoot module / plugin."""
    name: str
    description: str
    provides: list[str]
    consumes: list[str]
    category: Optional[str] = None
    is_deprecated: bool = False


@strawberry.type
class EventTypeInfo:
    """Reference data about an event type."""
    event: str
    description: str
    raw: bool
    category: str


@strawberry.type
class WorkspaceType:
    """A SpiderFoot workspace containing related scans."""
    workspace_id: str
    name: str
    description: str
    created_time: float
    modified_time: float
    scan_count: int
    target_count: int


@strawberry.type
class GraphNode:
    """A node in the scan result relationship graph."""
    id: str
    label: str
    event_type: str
    module: str
    risk: int


@strawberry.type
class GraphEdge:
    """An edge connecting two events in the relationship graph."""
    source: str
    target: str
    label: str


@strawberry.type
class ScanGraph:
    """Complete graph of scan results for visualization."""
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    node_count: int
    edge_count: int


@strawberry.type
class TimelineEntry:
    """A point in the scan timeline for time-series visualization."""
    timestamp: float
    event_type: str
    count: int


@strawberry.type
class RiskDistribution:
    """Risk distribution across scan events."""
    level: str
    count: int
    percentage: float


@strawberry.type
class ModuleEventCount:
    """Number of events produced by a module."""
    module: str
    count: int


@strawberry.type
class ScanStatistics:
    """Aggregate statistics for a scan — ideal for dashboard cards."""
    total_events: int
    unique_event_types: int
    total_correlations: int
    risk_distribution: list[RiskDistribution]
    top_modules: list[ModuleEventCount]
    timeline: list[TimelineEntry]
    duration_seconds: float


# ── Input Types ─────────────────────────────────────────────────────


@strawberry.input
class EventFilter:
    """Filter criteria for querying events."""
    event_types: Optional[list[str]] = None
    modules: Optional[list[str]] = None
    min_risk: Optional[int] = None
    max_risk: Optional[int] = None
    min_confidence: Optional[int] = None
    exclude_false_positives: bool = True
    search_text: Optional[str] = None


@strawberry.input
class PaginationInput:
    """Pagination parameters."""
    page: int = 1
    page_size: int = 50


# ── Paginated Wrappers ──────────────────────────────────────────────


@strawberry.type
class PaginatedEvents:
    """Paginated list of events with metadata."""
    events: list[EventType]
    total: int
    page: int
    page_size: int
    total_pages: int


@strawberry.type
class PaginatedScans:
    """Paginated list of scans."""
    scans: list[ScanType]
    total: int
    page: int
    page_size: int


# ── Mutation Types ──────────────────────────────────────────────────


@strawberry.input
class ScanCreateInput:
    """Input for creating and starting a new scan."""
    name: str
    target: str
    modules: Optional[list[str]] = None
    use_case: Optional[str] = None


@strawberry.input
class FalsePositiveInput:
    """Input for marking results as false positive."""
    scan_id: str
    result_ids: list[str]
    false_positive: bool = True


@strawberry.type
class MutationResult:
    """Generic mutation result with success flag and message."""
    success: bool
    message: str


@strawberry.type
class ScanCreateResult:
    """Result of creating/starting a new scan."""
    success: bool
    message: str
    scan_id: Optional[str] = None
    scan: Optional[ScanType] = None


@strawberry.type
class FalsePositiveResult:
    """Result of false positive operation."""
    success: bool
    message: str
    updated: int = 0


# ── Vector Search Types ─────────────────────────────────────────────


@strawberry.type
class VectorSearchHit:
    """A single result from semantic vector search."""
    id: str
    score: float
    event_type: Optional[str] = None
    module: Optional[str] = None
    data: Optional[str] = None
    scan_id: Optional[str] = None
    risk: Optional[int] = None
    payload: Optional[str] = None  # JSON-encoded raw payload


@strawberry.type
class VectorSearchResult:
    """Paginated vector similarity search result."""
    hits: list[VectorSearchHit]
    total_found: int
    query_time_ms: float
    collection: str


@strawberry.type
class VectorCollectionInfo:
    """Info about a vector collection."""
    name: str
    point_count: int
    vector_dimensions: int
    distance_metric: str
