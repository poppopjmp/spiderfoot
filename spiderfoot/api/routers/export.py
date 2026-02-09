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
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

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
    except Exception:
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
