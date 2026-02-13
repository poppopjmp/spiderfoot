# -*- coding: utf-8 -*-
# =============================================================================
# SpiderFoot — Celery Export Tasks
# =============================================================================
# Async data export in multiple formats: JSON, CSV, STIX 2.1, SARIF.
# =============================================================================

from __future__ import annotations

import logging
import time
from typing import Any

from spiderfoot.celery_app import celery_app

logger = logging.getLogger("sf.tasks.export")


@celery_app.task(
    name="spiderfoot.tasks.export.export_scan_data",
    bind=True,
    queue="export",
    max_retries=2,
    default_retry_delay=15,
    soft_time_limit=300,
    time_limit=600,
)
def export_scan_data(
    self,
    scan_id: str,
    format: str,
    global_opts: dict[str, Any],
    *,
    event_types: list[str] | None = None,
    include_raw: bool = False,
) -> dict[str, Any]:
    """Export scan results to a file in the specified format.

    Args:
        scan_id:     Scan instance ID.
        format:      Export format: json, csv, stix, sarif, excel.
        global_opts: SpiderFoot configuration dict.
        event_types: Optional filter for specific event types.
        include_raw: Include raw data fields.

    Returns:
        dict with storage_url, file_size, format.
    """
    start = time.time()

    self.update_state(
        state="EXPORTING",
        meta={"scan_id": scan_id, "format": format, "progress": 0},
    )

    try:
        from spiderfoot.reporting.export_service import ExportService

        svc = ExportService(global_opts)
        export_bytes, filename = svc.export_scan(
            scan_id,
            format=format,
            event_types=event_types,
            include_raw=include_raw,
        )

        # Store in MinIO
        from spiderfoot.tasks.report import _store_report

        content_types = {
            "json": "application/json",
            "csv": "text/csv",
            "stix": "application/json",
            "sarif": "application/json",
            "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

        report_key = f"exports/{scan_id}/{filename}"
        storage_url = _store_report(
            export_bytes,
            report_key,
            global_opts,
            content_type=content_types.get(format, "application/octet-stream"),
        )

        return {
            "scan_id": scan_id,
            "status": "completed",
            "format": format,
            "filename": filename,
            "storage_url": storage_url,
            "file_size_bytes": len(export_bytes),
            "duration_seconds": round(time.time() - start, 2),
        }

    except Exception as exc:
        logger.error(
            "export.failed",
            extra={"scan_id": scan_id, "format": format, "error": str(exc)},
        )
        raise self.retry(exc=exc)
