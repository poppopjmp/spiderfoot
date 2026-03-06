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

import json
import logging
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from ..dependencies import get_api_key, safe_filename, SafeId
from fastapi.responses import Response, StreamingResponse

log = logging.getLogger("spiderfoot.api.export")

router = APIRouter(dependencies=[Depends(get_api_key)])


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
        from spiderfoot.reporting.export_service import ExportService, ExportFormat
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
    scan_id: SafeId,
    format: ExportFormatParam = Query(
        ExportFormatParam.json,
        description="Output format: json, csv, stix, sarif",
    ),
    include_raw: bool = Query(True, description="Include raw data fields"),
    max_events: int = Query(0, ge=0, description="Max events (0 = unlimited)"),
) -> Response:
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
    from spiderfoot.reporting.export_service import ExportConfig
    svc.config = ExportConfig(
        include_raw_data=include_raw,
        max_events=max_events,
    )

    dbh = _get_dbh()

    try:
        content = svc.export_scan(scan_id, fmt, dbh=dbh)
    except ValueError as exc:
        log.warning("Export failed for scan %s: %s", scan_id, exc)
        raise HTTPException(status_code=400, detail="Export failed")
    except Exception as exc:
        log.error("Export failed for scan %s: %s", scan_id, exc)
        raise HTTPException(status_code=500, detail="Export failed")

    content_type = _CONTENT_TYPES.get(format.value, "application/octet-stream")
    ext = _FILE_EXTENSIONS.get(format.value, "txt")
    filename = safe_filename(f"spiderfoot-{scan_id}") + f".{ext}"

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
async def export_scan_stix(scan_id: SafeId) -> Response:
    """Convenience endpoint for STIX export."""
    return await export_scan(scan_id, format=ExportFormatParam.stix)


@router.get(
    "/scans/{scan_id}/export/sarif",
    tags=["scans"],
    summary="Export scan as SARIF report",
    description="Download scan results as a SARIF 2.1.0 report for security tooling integration.",
)
async def export_scan_sarif(scan_id: SafeId) -> Response:
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
    scan_id: SafeId,
    event_type: str | None = Query(None, description="Filter by event type"),
    chunk_size: int = Query(500, ge=100, le=5000, description="Events per chunk"),
) -> StreamingResponse:
    """Stream scan events as newline-delimited JSON (JSONL).

    Unlike the buffered /export endpoint, this streams events incrementally
    so the server never needs to hold the full export in memory.
    """

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
                        "visibility": event_row[6] if len(event_row) > 6 else None,
                        "risk": event_row[7] if len(event_row) > 7 else None,
                        "hash": str(event_row[8]) if len(event_row) > 8 else None,
                        "source_event_hash": str(event_row[9]) if len(event_row) > 9 else None,
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
            log.error("Streaming export error for %s: %s", scan_id, exc, exc_info=True)
            yield json.dumps({"error": "Internal export error"}) + "\n"

    return StreamingResponse(
        _event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename(f"spiderfoot-{scan_id}")}.jsonl"',
            "X-Content-Type-Options": "nosniff",
        },
    )


# ── Live event SSE stream (active scans) ──────────────────────────────

@router.get(
    "/scans/{scan_id}/events/stream",
    tags=["scans"],
    summary="Live scan events (SSE)",
    description=(
        "Server-Sent Events stream of individual scan events as they are "
        "produced.  Uses the EventRelay push system when available, with "
        "database-polling fallback for completed scans.  Each SSE data "
        "payload is a JSON object identical to the JSONL export schema."
    ),
    responses={
        200: {"description": "SSE event stream", "content": {"text/event-stream": {}}},
        404: {"description": "Scan not found"},
    },
)
async def stream_scan_events_sse(
    scan_id: SafeId,
    request: Request,
    event_type: str | None = Query(None, description="Filter by event type"),
) -> StreamingResponse:
    """Stream scan events live via Server-Sent Events."""
    import asyncio

    async def _sse_generator():
        """Yield SSE-formatted scan events."""
        # Try relay mode (push) for active scans
        use_relay = False
        relay = None
        queue = None
        try:
            from spiderfoot.events.event_relay import get_event_relay
            relay = get_event_relay()
            if relay._eventbus is not None or relay.has_consumers(scan_id):
                use_relay = True
                queue = relay.register_consumer(scan_id)
                try:
                    await relay.subscribe_scan(scan_id)
                except Exception:
                    pass
        except (ImportError, Exception):
            pass

        event_id = 0

        if use_relay and queue is not None:
            # ── Push mode: stream from EventRelay ──────────────
            try:
                while True:
                    if await request.is_disconnected():
                        return
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)

                        # Apply event_type filter
                        et = event.get("type", event.get("event_type", ""))
                        if event_type and et != event_type:
                            continue

                        event_id += 1
                        data = json.dumps(event, default=str)
                        yield f"id: {event_id}\nevent: scan_event\ndata: {data}\n\n"

                        # Check for completion signals
                        if et in ("scan_completed", "scan_error", "stream_end"):
                            yield f"id: {event_id + 1}\nevent: complete\ndata: {json.dumps({'scan_id': scan_id, 'reason': et})}\n\n"
                            return

                    except asyncio.TimeoutError:
                        yield f": heartbeat\n\n"
            finally:
                if relay:
                    relay.unregister_consumer(scan_id, queue)
        else:
            # ── Poll mode: stream from DB (completed scan) ────
            dbh = _get_dbh()
            if dbh is None:
                yield f"event: error\ndata: {json.dumps({'error': 'Database unavailable'})}\n\n"
                return

            all_events = dbh.scanResultEvent(scan_id) or []
            for event_row in all_events:
                if await request.is_disconnected():
                    return

                if isinstance(event_row, (list, tuple)):
                    record = {
                        "generated": event_row[0] if len(event_row) > 0 else None,
                        "data": str(event_row[1]) if len(event_row) > 1 else "",
                        "source_data": str(event_row[2]) if len(event_row) > 2 else "",
                        "module": str(event_row[3]) if len(event_row) > 3 else "",
                        "event_type": str(event_row[4]) if len(event_row) > 4 else "",
                        "confidence": event_row[5] if len(event_row) > 5 else None,
                        "visibility": event_row[6] if len(event_row) > 6 else None,
                        "risk": event_row[7] if len(event_row) > 7 else None,
                    }
                elif isinstance(event_row, dict):
                    record = event_row
                else:
                    continue

                et = record.get("event_type", "")
                if event_type and et != event_type:
                    continue
                if et == "ROOT":
                    continue

                event_id += 1
                data = json.dumps(record, default=str)
                yield f"id: {event_id}\nevent: scan_event\ndata: {data}\n\n"

            yield f"id: {event_id + 1}\nevent: complete\ndata: {json.dumps({'scan_id': scan_id, 'total_events': event_id})}\n\n"

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
