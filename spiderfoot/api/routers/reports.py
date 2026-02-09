"""
Report API Endpoints for SpiderFoot.

FastAPI router providing endpoints for LLM-powered report generation,
retrieval, and export. Supports both synchronous and background generation.

Endpoints:
  POST /api/reports/generate       - Start async report generation
  GET  /api/reports/{report_id}    - Retrieve generated report
  POST /api/reports/preview        - Quick executive summary (sync)
  GET  /api/reports/{report_id}/export - Export report in various formats
  GET  /api/reports                - List generated reports
  DELETE /api/reports/{report_id}  - Delete a report
"""

from __future__ import annotations

import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

log = logging.getLogger("spiderfoot.api.reports")

# Store generated reports in-memory (replaced by persistence in Cycle 9)
_report_store: Dict[str, Dict[str, Any]] = {}

try:
    from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
    from fastapi.responses import StreamingResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class ReportTypeEnum(str, Enum):
    """Report type selection."""
    FULL = "full"
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    RISK_ASSESSMENT = "risk_assessment"
    RECOMMENDATIONS = "recommendations"


class ReportFormatEnum(str, Enum):
    """Output format for export."""
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    PLAIN_TEXT = "plain_text"
    CSV = "csv"


class ReportGenerateRequest(BaseModel):
    """Request body for report generation."""
    scan_id: str = Field(..., description="ID of the scan to generate a report for")
    report_type: ReportTypeEnum = Field(
        ReportTypeEnum.FULL,
        description="Type of report to generate",
    )
    title: Optional[str] = Field(None, description="Custom report title")
    language: str = Field("English", description="Report language")
    custom_instructions: Optional[str] = Field(
        None, description="Additional instructions for the LLM"
    )


class ReportPreviewRequest(BaseModel):
    """Request body for quick executive summary preview."""
    scan_id: str = Field(..., description="ID of the scan")
    custom_instructions: Optional[str] = Field(None)


class ReportStatusResponse(BaseModel):
    """Response showing report generation status."""
    report_id: str
    scan_id: str
    status: str  # "pending", "generating", "completed", "failed"
    progress_pct: float = 0.0
    message: str = ""


class ReportResponse(BaseModel):
    """Full report response."""
    report_id: str
    scan_id: str
    title: str
    status: str
    report_type: str
    executive_summary: Optional[str] = None
    recommendations: Optional[str] = None
    sections: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    generation_time_ms: float = 0.0
    total_tokens_used: int = 0


class ReportListItem(BaseModel):
    """Summary item for report listing."""
    report_id: str
    scan_id: str
    title: str
    status: str
    report_type: str
    generation_time_ms: float = 0.0
    created_at: float = 0.0


# ---------------------------------------------------------------------------
# Report store helpers (in-memory, replaced by DB in Cycle 9)
# ---------------------------------------------------------------------------

def store_report(report_id: str, data: Dict[str, Any]) -> None:
    """Save report data to the in-memory store."""
    _report_store[report_id] = data


def get_stored_report(report_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve report data from store."""
    return _report_store.get(report_id)


def delete_stored_report(report_id: str) -> bool:
    """Delete report from store. Returns True if found."""
    return _report_store.pop(report_id, None) is not None


def list_stored_reports() -> List[Dict[str, Any]]:
    """List all stored reports."""
    return list(_report_store.values())


def clear_store() -> None:
    """Clear all stored reports (for testing)."""
    _report_store.clear()


# ---------------------------------------------------------------------------
# Background task: generate report
# ---------------------------------------------------------------------------

def _generate_report_background(
    report_id: str,
    scan_id: str,
    report_type: str,
    title: Optional[str],
    language: str,
    custom_instructions: Optional[str],
    events: List[Dict[str, Any]],
    scan_metadata: Dict[str, Any],
) -> None:
    """Run report generation as a background task.

    Updates the report store with progress and final result.
    """
    from spiderfoot.report_generator import (
        GeneratedReport,
        ReportGenerator,
        ReportGeneratorConfig,
        ReportType,
    )

    stored = get_stored_report(report_id)
    if stored is None:
        return

    stored["status"] = "generating"
    stored["progress_pct"] = 10.0

    try:
        # Map string to enum
        type_map = {
            "full": ReportType.FULL,
            "executive": ReportType.EXECUTIVE,
            "technical": ReportType.TECHNICAL,
            "risk_assessment": ReportType.RISK_ASSESSMENT,
            "recommendations": ReportType.RECOMMENDATIONS,
        }

        config = ReportGeneratorConfig(
            report_type=type_map.get(report_type, ReportType.FULL),
            report_title=title or "",
            language=language,
            custom_instructions=custom_instructions or "",
        )

        # Section completion callback for progress tracking
        sections_done = [0]
        total_sections = [3]  # estimate

        def on_section(section_title: str, _content: str) -> None:
            sections_done[0] += 1
            pct = min(10 + (sections_done[0] / max(total_sections[0], 1)) * 80, 90)
            stored["progress_pct"] = pct
            stored["message"] = f"Generated: {section_title}"

        config.on_section_complete = on_section

        generator = ReportGenerator(config)
        report = generator.generate(events, scan_metadata)

        # Store completed report
        stored["status"] = "completed"
        stored["progress_pct"] = 100.0
        stored["title"] = report.title
        stored["report_type"] = report.report_type.value
        stored["executive_summary"] = report.executive_summary
        stored["recommendations"] = report.recommendations
        stored["sections"] = [
            {
                "title": s.title,
                "content": s.content,
                "section_type": s.section_type,
                "source_event_count": s.source_event_count,
                "token_count": s.token_count,
            }
            for s in report.sections
        ]
        stored["metadata"] = report.metadata
        stored["generation_time_ms"] = report.generation_time_ms
        stored["total_tokens_used"] = report.total_tokens_used
        stored["message"] = "Report generation completed"

        log.info("Report %s generated in %.0fms", report_id, report.generation_time_ms)

    except Exception as e:
        stored["status"] = "failed"
        stored["message"] = f"Generation failed: {str(e)}"
        log.error("Report %s generation failed: %s", report_id, e, exc_info=True)


# ---------------------------------------------------------------------------
# Scan event retrieval helper
# ---------------------------------------------------------------------------

def _get_scan_events(scan_id: str) -> tuple:
    """Retrieve scan events and metadata.

    Returns (events_list, metadata_dict).
    Falls back to empty if DB unavailable.
    """
    events = []
    metadata = {"scan_id": scan_id, "target": "Unknown"}

    try:
        from spiderfoot import SpiderFootDb
        from spiderfoot.config import get_app_config

        config = get_app_config()
        dbh = SpiderFootDb(config.get_config())

        # Get scan info
        scan_info = dbh.scanInstanceGet(scan_id)
        if scan_info:
            metadata["target"] = scan_info[1] if len(scan_info) > 1 else "Unknown"
            metadata["started"] = scan_info[3] if len(scan_info) > 3 else ""
            metadata["ended"] = scan_info[4] if len(scan_info) > 4 else ""

        # Get events
        raw_events = dbh.scanResultEvent(scan_id)
        for row in raw_events:
            events.append({
                "type": row[4] if len(row) > 4 else "UNKNOWN",
                "data": row[1] if len(row) > 1 else "",
                "module": row[3] if len(row) > 3 else "",
                "source_event": row[2] if len(row) > 2 else "",
                "timestamp": row[0] if len(row) > 0 else 0,
            })
    except Exception as e:
        log.warning("Could not retrieve scan events: %s", e)

    return events, metadata


# ---------------------------------------------------------------------------
# Router and endpoint definitions
# ---------------------------------------------------------------------------

if not HAS_FASTAPI:
    # Provide a stub router so imports don't fail
    class _StubRouter:
        pass
    router = _StubRouter()
else:
    router = APIRouter()

    @router.post(
        "/reports/generate",
        response_model=ReportStatusResponse,
        status_code=202,
        summary="Start report generation",
        description="Initiates async report generation for a scan. Returns a report ID for polling.",
    )
    async def generate_report(
        request: ReportGenerateRequest,
        background_tasks: BackgroundTasks,
    ) -> ReportStatusResponse:
        report_id = str(uuid.uuid4())

        # Retrieve scan events
        events, scan_metadata = _get_scan_events(request.scan_id)

        # Initialize report in store
        store_report(report_id, {
            "report_id": report_id,
            "scan_id": request.scan_id,
            "title": request.title or f"Report: {scan_metadata.get('target', 'Unknown')}",
            "status": "pending",
            "report_type": request.report_type.value,
            "progress_pct": 0.0,
            "message": "Queued for generation",
            "executive_summary": None,
            "recommendations": None,
            "sections": [],
            "metadata": {},
            "generation_time_ms": 0.0,
            "total_tokens_used": 0,
            "created_at": time.time(),
        })

        # Start background generation
        background_tasks.add_task(
            _generate_report_background,
            report_id=report_id,
            scan_id=request.scan_id,
            report_type=request.report_type.value,
            title=request.title,
            language=request.language,
            custom_instructions=request.custom_instructions,
            events=events,
            scan_metadata=scan_metadata,
        )

        return ReportStatusResponse(
            report_id=report_id,
            scan_id=request.scan_id,
            status="pending",
            progress_pct=0.0,
            message="Report generation queued",
        )

    @router.get(
        "/reports/{report_id}",
        response_model=ReportResponse,
        summary="Get generated report",
        description="Retrieve a generated report by ID. Check status to see if generation is complete.",
    )
    async def get_report(report_id: str) -> ReportResponse:
        stored = get_stored_report(report_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="Report not found")

        return ReportResponse(
            report_id=stored["report_id"],
            scan_id=stored["scan_id"],
            title=stored.get("title", ""),
            status=stored["status"],
            report_type=stored.get("report_type", "full"),
            executive_summary=stored.get("executive_summary"),
            recommendations=stored.get("recommendations"),
            sections=stored.get("sections", []),
            metadata=stored.get("metadata", {}),
            generation_time_ms=stored.get("generation_time_ms", 0.0),
            total_tokens_used=stored.get("total_tokens_used", 0),
        )

    @router.get(
        "/reports/{report_id}/status",
        response_model=ReportStatusResponse,
        summary="Check report generation status",
    )
    async def get_report_status(report_id: str) -> ReportStatusResponse:
        stored = get_stored_report(report_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="Report not found")

        return ReportStatusResponse(
            report_id=report_id,
            scan_id=stored["scan_id"],
            status=stored["status"],
            progress_pct=stored.get("progress_pct", 0.0),
            message=stored.get("message", ""),
        )

    @router.post(
        "/reports/preview",
        summary="Generate executive summary preview",
        description="Synchronously generates a quick executive summary for immediate display.",
    )
    async def preview_report(request: ReportPreviewRequest) -> Dict[str, Any]:
        from spiderfoot.report_generator import ReportGenerator, ReportGeneratorConfig

        events, scan_metadata = _get_scan_events(request.scan_id)

        config = ReportGeneratorConfig(
            custom_instructions=request.custom_instructions or "",
        )
        generator = ReportGenerator(config)
        summary = generator.generate_executive_only(events, scan_metadata)

        return {
            "scan_id": request.scan_id,
            "executive_summary": summary,
            "target": scan_metadata.get("target", "Unknown"),
        }

    @router.get(
        "/reports/{report_id}/export",
        summary="Export report in specified format",
        description="Export a completed report as Markdown, HTML, JSON, plain text, or CSV.",
    )
    async def export_report(
        report_id: str,
        fmt: ReportFormatEnum = Query(
            ReportFormatEnum.MARKDOWN, alias="format",
            description="Output format"
        ),
    ):
        from spiderfoot.report_formatter import ReportFormatter
        from spiderfoot.report_generator import (
            GeneratedReport,
            GeneratedSection,
            ReportFormat,
            ReportType,
        )

        stored = get_stored_report(report_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="Report not found")
        if stored["status"] != "completed":
            raise HTTPException(
                status_code=409,
                detail=f"Report is not ready (status: {stored['status']})"
            )

        # Reconstruct GeneratedReport from stored data
        report = GeneratedReport(
            title=stored.get("title", "Report"),
            scan_id=stored.get("scan_id", ""),
            scan_target=stored.get("metadata", {}).get("target", ""),
            executive_summary=stored.get("executive_summary", ""),
            recommendations=stored.get("recommendations", ""),
            report_type=ReportType(stored.get("report_type", "full")),
            sections=[
                GeneratedSection(
                    title=s.get("title", ""),
                    content=s.get("content", ""),
                    section_type=s.get("section_type", ""),
                    source_event_count=s.get("source_event_count", 0),
                    token_count=s.get("token_count", 0),
                )
                for s in stored.get("sections", [])
            ],
            metadata=stored.get("metadata", {}),
            generation_time_ms=stored.get("generation_time_ms", 0.0),
            total_tokens_used=stored.get("total_tokens_used", 0),
        )

        formatter = ReportFormatter()
        content = formatter.render(report, fmt.value)

        media_types = {
            "markdown": "text/markdown",
            "html": "text/html",
            "json": "application/json",
            "plain_text": "text/plain",
            "csv": "text/csv",
        }
        extensions = {
            "markdown": "md",
            "html": "html",
            "json": "json",
            "plain_text": "txt",
            "csv": "csv",
        }

        media_type = media_types.get(fmt.value, "text/plain")
        ext = extensions.get(fmt.value, "txt")
        filename = f"report-{report_id[:8]}.{ext}"

        return StreamingResponse(
            iter([content]),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Pragma": "no-cache",
            },
        )

    @router.get(
        "/reports",
        response_model=List[ReportListItem],
        summary="List generated reports",
    )
    async def list_reports(
        scan_id: Optional[str] = Query(None, description="Filter by scan ID"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> List[ReportListItem]:
        reports = list_stored_reports()

        if scan_id:
            reports = [r for r in reports if r.get("scan_id") == scan_id]

        # Sort by creation time (newest first)
        reports.sort(key=lambda r: r.get("created_at", 0), reverse=True)

        # Paginate
        paginated = reports[offset: offset + limit]

        return [
            ReportListItem(
                report_id=r["report_id"],
                scan_id=r["scan_id"],
                title=r.get("title", ""),
                status=r["status"],
                report_type=r.get("report_type", "full"),
                generation_time_ms=r.get("generation_time_ms", 0.0),
                created_at=r.get("created_at", 0.0),
            )
            for r in paginated
        ]

    @router.delete(
        "/reports/{report_id}",
        summary="Delete a report",
        status_code=204,
    )
    async def delete_report(report_id: str):
        if not delete_stored_report(report_id):
            raise HTTPException(status_code=404, detail="Report not found")
        return None
