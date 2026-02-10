"""
Scan export API router.

Exposes ExportService capabilities through the REST API with support
for JSON, CSV, STIX 2.1, and SARIF download formats.

Endpoints:
    GET /scans/{scan_id}/export     — unified export (format query param)
    GET /scans/{scan_id}/export/stix  — STIX 2.1 bundle download
    GET /scans/{scan_id}/export/sarif — SARIF report download
"""
from __future__ import annotations

import logging
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

log = logging.getLogger("spiderfoot.api.export")

router = APIRouter()


class ExportFormatParam(str, Enum):
    """Query parameter values for export format."""
    json = "json"
    csv = "csv"
    stix = "stix"
    sarif = "sarif"


# MIME types for each format
_CONTENT_TYPES = {
    "json": "application/json",
    "csv": "text/csv",
    "stix": "application/stix+json",
    "sarif": "application/sarif+json",
}

_FILE_EXTENSIONS = {
    "json": "json",
    "csv": "csv",
    "stix": "stix.json",
    "sarif": "sarif.json",
}


def _get_export_service():
    """Lazy-import ExportService to avoid circular imports."""
    try:
        from spiderfoot.export_service import ExportService, ExportFormat
        return ExportService(), ExportFormat
    except ImportError:
        return None, None


def _get_dbh():
    """Try to obtain a database handle from ServiceRegistry."""
    try:
        from spiderfoot.service_registry import ServiceRegistry
        registry = ServiceRegistry.instance()
        return registry.get("db") or registry.get("dbh")
    except (ImportError, AttributeError):
        pass
    return None


@router.get(
    "/scans/{scan_id}/export",
    tags=["scans"],
    summary="Export scan results",
    description=(
        "Download scan results in JSON, CSV, STIX 2.1, or SARIF format. "
        "Use the `format` query parameter to select the output format."
    ),
    responses={
        200: {"description": "Scan data in requested format"},
        404: {"description": "Scan not found"},
        501: {"description": "Export service not available"},
    },
)
async def export_scan(
    scan_id: str,
    format: ExportFormatParam = Query(
        ExportFormatParam.json,
        description="Output format: json, csv, stix, sarif",
    ),
    include_raw: bool = Query(True, description="Include raw data fields"),
    max_events: int = Query(0, ge=0, description="Max events (0 = unlimited)"),
):
    """Export scan results in the specified format."""
    svc, ExportFormat = _get_export_service()
    if svc is None:
        raise HTTPException(status_code=501, detail="ExportService not available")

    # Map query param to enum
    fmt_map = {
        "json": ExportFormat.JSON,
        "csv": ExportFormat.CSV,
        "stix": ExportFormat.STIX,
        "sarif": ExportFormat.SARIF,
    }
    fmt = fmt_map.get(format.value)
    if fmt is None:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format.value}")

    # Apply config overrides
    from spiderfoot.export_service import ExportConfig
    svc.config = ExportConfig(
        include_raw_data=include_raw,
        max_events=max_events,
    )

    dbh = _get_dbh()

    try:
        content = svc.export_scan(scan_id, fmt, dbh=dbh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        log.error("Export failed for scan %s: %s", scan_id, exc)
        raise HTTPException(status_code=500, detail="Export failed")

    content_type = _CONTENT_TYPES.get(format.value, "application/octet-stream")
    ext = _FILE_EXTENSIONS.get(format.value, "txt")
    filename = f"spiderfoot-{scan_id}.{ext}"

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/scans/{scan_id}/export/stix",
    tags=["scans"],
    summary="Export scan as STIX 2.1 bundle",
    description="Download scan results as a STIX 2.1 JSON bundle for threat intelligence sharing.",
)
async def export_scan_stix(scan_id: str):
    """Convenience endpoint for STIX export."""
    return await export_scan(scan_id, format=ExportFormatParam.stix)


@router.get(
    "/scans/{scan_id}/export/sarif",
    tags=["scans"],
    summary="Export scan as SARIF report",
    description="Download scan results as a SARIF 2.1.0 report for security tooling integration.",
)
async def export_scan_sarif(scan_id: str):
    """Convenience endpoint for SARIF export."""
    return await export_scan(scan_id, format=ExportFormatParam.sarif)


@router.get(
    "/scans/{scan_id}/export/stream",
    tags=["scans"],
    summary="Streaming export (JSON Lines)",
    description=(
        "Stream scan events as newline-delimited JSON (JSONL / NDJSON). "
        "Ideal for large scans where buffering the full response in memory "
        "would be impractical.  Each line is a self-contained JSON object."
    ),
    responses={
        200: {"description": "JSONL stream", "content": {"application/x-ndjson": {}}},
        404: {"description": "Scan not found"},
    },
)
async def export_scan_stream(
    scan_id: str,
    event_type: str | None = Query(None, description="Filter by event type"),
    chunk_size: int = Query(500, ge=100, le=5000, description="Events per chunk"),
):
    """Stream scan events as newline-delimited JSON (JSONL).

    Unlike the buffered /export endpoint, this streams events incrementally
    so the server never needs to hold the full export in memory.
    """
    import json

    # Verify scan exists
    try:
        from spiderfoot.api.dependencies import get_app_config
        from spiderfoot.sflib.core import SpiderFoot

        config = get_app_config()
        sf = SpiderFoot(config.get_config())
        dbh = _get_dbh()

        if dbh:
            scan_info = dbh.scanInstanceGet(scan_id)
        else:
            scan_info = None

        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to verify scan %s for streaming: %s", scan_id, exc)
        raise HTTPException(status_code=500, detail="Failed to access scan data")

    async def _event_generator():
        """Yield scan events as JSONL."""
        try:
            if dbh is None:
                return

            # Get events in chunks to limit memory
            all_events = dbh.scanResultEvent(scan_id) or []

            yielded = 0
            for event_row in all_events:
                if isinstance(event_row, (list, tuple)):
                    record = {
                        "generated": event_row[0] if len(event_row) > 0 else None,
                        "data": str(event_row[1]) if len(event_row) > 1 else "",
                        "source_data": str(event_row[2]) if len(event_row) > 2 else "",
                        "module": str(event_row[3]) if len(event_row) > 3 else "",
                        "event_type": str(event_row[4]) if len(event_row) > 4 else "",
                        "confidence": event_row[5] if len(event_row) > 5 else None,
                    }
                elif isinstance(event_row, dict):
                    record = event_row
                else:
                    continue

                # Apply event_type filter
                et = record.get("event_type", "")
                if event_type and et != event_type:
                    continue
                if et == "ROOT":
                    continue

                yield json.dumps(record, default=str) + "\n"
                yielded += 1

            log.info("Streamed %d events for scan %s", yielded, scan_id)
        except Exception as exc:
            log.error("Streaming export error for %s: %s", scan_id, exc)
            yield json.dumps({"error": str(exc)}) + "\n"

    return StreamingResponse(
        _event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="spiderfoot-{scan_id}.jsonl"',
            "X-Content-Type-Options": "nosniff",
        },
    )
