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
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from spiderfoot.scan.scan_service_facade import ScanService

from pydantic import BaseModel, Field

log = logging.getLogger("spiderfoot.api.reports")

# ---------------------------------------------------------------------------
# Persistent store (Cycle 12 — replaces in-memory dict)
# ---------------------------------------------------------------------------

try:
    from spiderfoot.reporting.report_storage import ReportStore, StoreConfig
    _persistent_store: ReportStore | None = None
except ImportError:
    _persistent_store = None

# Legacy fallback dict — only used when ReportStore is unavailable
_report_store: dict[str, dict[str, Any]] = {}


def _get_store() -> ReportStore | None:
    """Lazily initialise the persistent ReportStore singleton."""
    global _persistent_store
    if _persistent_store is not None:
        return _persistent_store
    try:
        from spiderfoot.reporting.report_storage import ReportStore, StoreConfig
        store = ReportStore(StoreConfig())
        log.info("Persistent ReportStore initialised (backend=%s)",
                 store.config.backend.value)
        _persistent_store = store
        return _persistent_store
    except Exception as exc:
        log.debug("ReportStore unavailable, using in-memory fallback: %s", exc)
        return None

try:
    from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
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
    title: str | None = Field(None, description="Custom report title")
    language: str = Field("English", description="Report language")
    custom_instructions: str | None = Field(
        None, description="Additional instructions for the LLM"
    )


class ReportPreviewRequest(BaseModel):
    """Request body for quick executive summary preview."""
    scan_id: str = Field(..., description="ID of the scan")
    custom_instructions: str | None = Field(None)


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
    executive_summary: str | None = None
    recommendations: str | None = None
    sections: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
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


class PDFReportRequest(BaseModel):
    """Request body for PDF report generation (v5.4.3+)."""
    scan_id: str = Field(..., description="ID of the scan to generate a PDF for")
    title: str | None = Field(None, description="Custom report title")
    template: str = Field("default", description="Report template name")
    include_executive_summary: bool = Field(True, description="Include AI executive summary")
    include_charts: bool = Field(True, description="Include data visualizations")
    include_raw_data: bool = Field(False, description="Append raw event data")
    llm_enhanced: bool = Field(False, description="Use LLM for narrative enrichment")
    branding: dict[str, str] | None = Field(None, description="Custom branding overrides")


class ExportFormatRequest(BaseModel):
    """Request body for async export via Celery (v5.4.3+)."""
    scan_id: str = Field(..., description="ID of the scan to export")
    format: str = Field("json", description="Export format: json, csv, stix, sarif, excel")
    filename: str | None = Field(None, description="Custom output filename")


# ---------------------------------------------------------------------------
# Report store helpers (in-memory, replaced by DB in Cycle 9)
# ---------------------------------------------------------------------------

def store_report(report_id: str, data: dict[str, Any]) -> None:
    """Save report data — persistent store with in-memory fallback."""
    store = _get_store()
    if store is not None:
        try:
            store.save(data)
            return
        except Exception as exc:
            log.warning("Persistent save failed, using in-memory: %s", exc)
    _report_store[report_id] = data


def get_stored_report(report_id: str) -> dict[str, Any] | None:
    """Retrieve report data — persistent store with in-memory fallback."""
    store = _get_store()
    if store is not None:
        try:
            result = store.get(report_id)
            if result is not None:
                return result
        except Exception as exc:
            log.debug("Persistent get failed: %s", exc)
    return _report_store.get(report_id)


def delete_stored_report(report_id: str) -> bool:
    """Delete report — persistent store with in-memory fallback."""
    store = _get_store()
    deleted = False
    if store is not None:
        try:
            deleted = store.delete(report_id)
        except Exception as exc:
            log.debug("Persistent delete failed: %s", exc)
    if not deleted:
        deleted = _report_store.pop(report_id, None) is not None
    return deleted


def list_stored_reports(
    scan_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List stored reports — persistent store with in-memory fallback."""
    store = _get_store()
    if store is not None:
        try:
            return store.list_reports(
                scan_id=scan_id, limit=limit, offset=offset,
            )
        except Exception as exc:
            log.debug("Persistent list failed: %s", exc)
    # Fallback
    reports = list(_report_store.values())
    if scan_id:
        reports = [r for r in reports if r.get("scan_id") == scan_id]
    reports.sort(key=lambda r: r.get("created_at", 0), reverse=True)
    return reports[offset: offset + limit]


def update_stored_report(report_id: str, updates: dict[str, Any]) -> None:
    """Partially update a stored report."""
    store = _get_store()
    if store is not None:
        try:
            store.update(report_id, updates)
            return
        except Exception as exc:
            log.debug("Persistent update failed: %s", exc)
    # Fallback
    if report_id in _report_store:
        _report_store[report_id].update(updates)


def clear_store() -> None:
    """Clear all stored reports (for testing).

    Resets both the persistent store and the in-memory fallback so
    each test starts with an empty slate.
    """
    global _persistent_store
    if _persistent_store is not None:
        try:
            # Bulk-delete all data via SQL for robustness
            backend = _persistent_store._backend
            if hasattr(backend, "_get_conn"):
                conn = backend._get_conn()
                conn.execute("DELETE FROM reports")
                conn.commit()
            else:
                # MemoryBackend
                backend._store.clear()
            _persistent_store._cache.clear()
        except (OSError, AttributeError):
            pass
        _persistent_store = None
    _report_store.clear()


# ---------------------------------------------------------------------------
# Background task: generate report
# ---------------------------------------------------------------------------

def _generate_report_background(
    report_id: str,
    scan_id: str,
    report_type: str,
    title: str | None,
    language: str,
    custom_instructions: str | None,
    events: list[dict[str, Any]],
    scan_metadata: dict[str, Any],
) -> None:
    """Run report generation as a background task.

    Updates the report store with progress and final result.
    """
    from spiderfoot.reporting.report_generator import (
        GeneratedReport,
        ReportGenerator,
        ReportGeneratorConfig,
        ReportType,
    )

    stored = get_stored_report(report_id)
    if stored is None:
        return

    update_stored_report(report_id, {"status": "generating", "progress_pct": 10.0})

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
            """Track report section completion progress."""
            sections_done[0] += 1
            pct = min(10 + (sections_done[0] / max(total_sections[0], 1)) * 80, 90)
            update_stored_report(report_id, {
                "progress_pct": pct,
                "message": f"Generated: {section_title}",
            })

        config.on_section_complete = on_section

        generator = ReportGenerator(config)
        report = generator.generate(events, scan_metadata)

        # Store completed report
        update_stored_report(report_id, {
            "status": "completed",
            "progress_pct": 100.0,
            "title": report.title,
            "report_type": report.report_type.value,
            "executive_summary": report.executive_summary,
            "recommendations": report.recommendations,
            "sections": [
                {
                    "title": s.title,
                    "content": s.content,
                    "section_type": s.section_type,
                    "source_event_count": s.source_event_count,
                    "token_count": s.token_count,
                }
                for s in report.sections
            ],
            "metadata": report.metadata,
            "generation_time_ms": report.generation_time_ms,
            "total_tokens_used": report.total_tokens_used,
            "message": "Report generation completed",
        })

        log.info("Report %s generated in %.0fms", report_id, report.generation_time_ms)

    except Exception as e:
        update_stored_report(report_id, {
            "status": "failed",
            "message": f"Generation failed: {str(e)}",
        })
        log.error("Report %s generation failed: %s", report_id, e, exc_info=True)


# ---------------------------------------------------------------------------
# Scan event retrieval helper
# ---------------------------------------------------------------------------

def _get_scan_events(scan_id: str, scan_service=None) -> tuple:
    """Retrieve scan events and metadata.

    Uses ``ScanService`` when provided (injected from endpoints).
    Falls back to empty if unavailable.

    Returns (events_list, metadata_dict).
    """
    events = []
    metadata = {"scan_id": scan_id, "target": "Unknown"}

    try:
        if scan_service is None:
            # Fallback: build a service from config (non‑endpoint callers)
            from spiderfoot.db.repositories import (
                get_repository_factory,
                RepositoryFactory,
            )
            from spiderfoot.scan.scan_service_facade import ScanService
            from spiderfoot.config import get_app_config

            config = get_app_config()
            factory = get_repository_factory()
            if factory is None:
                factory = RepositoryFactory(config.get_config())
            repo = factory.scan_repo()
            scan_service = ScanService(repo, dbh=repo._dbh)

        # Get scan info
        scan_info = scan_service.get_scan(scan_id)
        if scan_info:
            metadata["target"] = getattr(scan_info, "target", "Unknown") or "Unknown"
            metadata["started"] = getattr(scan_info, "started", "") or ""
            metadata["ended"] = getattr(scan_info, "ended", "") or ""

        # Get events
        raw_events = scan_service.get_events(scan_id)
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
        """Stub router for when dependencies are unavailable."""
        pass
    router = _StubRouter()
else:
    from ..dependencies import get_scan_service

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
        scan_service: ScanService = Depends(get_scan_service),
    ) -> ReportStatusResponse:
        """Start asynchronous report generation for a scan."""
        report_id = str(uuid.uuid4())

        # Retrieve scan events
        events, scan_metadata = _get_scan_events(request.scan_id, scan_service=scan_service)

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
        """Retrieve a generated report by its ID."""
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
        """Check the generation status of a report."""
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
    async def preview_report(request: ReportPreviewRequest,
                            scan_service: ScanService = Depends(get_scan_service)) -> dict[str, Any]:
        """Generate a quick executive summary preview synchronously."""
        from spiderfoot.reporting.report_generator import ReportGenerator, ReportGeneratorConfig

        events, scan_metadata = _get_scan_events(request.scan_id, scan_service=scan_service)

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
    ) -> StreamingResponse:
        """Export a completed report in the specified format."""
        from spiderfoot.reporting.report_formatter import ReportFormatter
        from spiderfoot.reporting.report_generator import (
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
        response_model=list[ReportListItem],
        summary="List generated reports",
    )
    async def list_reports(
        scan_id: str | None = Query(None, description="Filter by scan ID"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> list[ReportListItem]:
        """List all generated reports with optional filtering."""
        reports = list_stored_reports(scan_id=scan_id, limit=limit, offset=offset)

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
            for r in reports
        ]

    @router.delete(
        "/reports/{report_id}",
        summary="Delete a report",
        status_code=204,
    )
    async def delete_report(report_id: str) -> None:
        """Delete a report by its ID."""
        if not delete_stored_report(report_id):
            raise HTTPException(status_code=404, detail="Report not found")
        return None

    # -------------------------------------------------------------------
    # PDF / Export endpoints (v5.4.3 — Celery-powered)
    # -------------------------------------------------------------------

    @router.post(
        "/reports/pdf",
        response_model=ReportStatusResponse,
        status_code=202,
        summary="Generate PDF report (async)",
        description="Dispatches PDF generation to a Celery worker. Returns report ID for polling.",
    )
    async def generate_pdf_report(
        request: PDFReportRequest,
        scan_service: ScanService = Depends(get_scan_service),
    ) -> ReportStatusResponse:
        """Generate a branded PDF report asynchronously via Celery."""
        report_id = str(uuid.uuid4())

        # Initialize report record
        store_report(report_id, {
            "report_id": report_id,
            "scan_id": request.scan_id,
            "title": request.title or f"PDF Report",
            "status": "pending",
            "report_type": "pdf",
            "progress_pct": 0.0,
            "message": "Queued for PDF generation",
            "created_at": time.time(),
        })

        # Dispatch to Celery if available, else generate inline
        try:
            from spiderfoot.celery_app import is_celery_available
            if is_celery_available():
                from spiderfoot.tasks.report import generate_pdf_report as pdf_task
                pdf_task.apply_async(
                    kwargs={
                        "scan_id": request.scan_id,
                        "report_id": report_id,
                        "template": request.template,
                        "branding": request.branding,
                        "include_executive_summary": request.include_executive_summary,
                        "include_charts": request.include_charts,
                        "include_raw_data": request.include_raw_data,
                        "llm_enhanced": request.llm_enhanced,
                    },
                    queue="report",
                )
                return ReportStatusResponse(
                    report_id=report_id,
                    scan_id=request.scan_id,
                    status="pending",
                    message="PDF generation dispatched to worker",
                )
        except Exception as e:
            log.warning("Celery unavailable for PDF generation: %s", e)

        # Fallback: generate inline (blocking)
        try:
            events, scan_meta = _get_scan_events(request.scan_id, scan_service=scan_service)
            from spiderfoot.reporting.report_formatter import ReportFormatter
            from spiderfoot.reporting.pdf_renderer import PDFRenderer

            formatter = ReportFormatter()
            # Build a minimal GeneratedReport for HTML rendering
            from spiderfoot.reporting.report_generator import GeneratedReport
            report = GeneratedReport(
                title=request.title or f"Scan Report: {scan_meta.get('target', 'Unknown')}",
                scan_id=request.scan_id,
                sections=[],
            )
            html_content = formatter.to_html(report)
            renderer = PDFRenderer()
            pdf_bytes = renderer.render(html_content, title=report.title)

            store_report(report_id, {
                "report_id": report_id,
                "scan_id": request.scan_id,
                "status": "completed",
                "title": report.title,
                "report_type": "pdf",
                "progress_pct": 100.0,
                "message": "PDF generated (inline)",
                "pdf_size_bytes": len(pdf_bytes),
                "created_at": time.time(),
            })
        except Exception as e:
            store_report(report_id, {
                "report_id": report_id,
                "scan_id": request.scan_id,
                "status": "failed",
                "report_type": "pdf",
                "message": str(e),
                "created_at": time.time(),
            })

        return ReportStatusResponse(
            report_id=report_id,
            scan_id=request.scan_id,
            status="pending",
            message="PDF generation started",
        )

    @router.post(
        "/reports/export",
        response_model=ReportStatusResponse,
        status_code=202,
        summary="Export scan data (async)",
        description="Dispatches data export to a Celery worker. Supports JSON, CSV, STIX, SARIF, Excel.",
    )
    async def export_scan_data(
        request: ExportFormatRequest,
    ) -> ReportStatusResponse:
        """Export scan data in the specified format via Celery."""
        export_id = str(uuid.uuid4())

        store_report(export_id, {
            "report_id": export_id,
            "scan_id": request.scan_id,
            "title": f"Export ({request.format.upper()})",
            "status": "pending",
            "report_type": f"export_{request.format}",
            "message": "Queued for export",
            "created_at": time.time(),
        })

        try:
            from spiderfoot.celery_app import is_celery_available
            if is_celery_available():
                from spiderfoot.tasks.export import export_scan_data as export_task
                export_task.apply_async(
                    kwargs={
                        "scan_id": request.scan_id,
                        "export_format": request.format,
                        "filename": request.filename,
                    },
                    task_id=export_id,
                    queue="export",
                )
                return ReportStatusResponse(
                    report_id=export_id,
                    scan_id=request.scan_id,
                    status="pending",
                    message=f"Export ({request.format}) dispatched to worker",
                )
        except Exception as e:
            log.warning("Celery unavailable for export: %s", e)

        return ReportStatusResponse(
            report_id=export_id,
            scan_id=request.scan_id,
            status="failed",
            message="Celery workers required for async export",
        )
