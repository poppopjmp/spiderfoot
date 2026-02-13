# -*- coding: utf-8 -*-
# =============================================================================
# SpiderFoot — Celery Report Tasks
# =============================================================================
# Async report generation: PDF (branded), HTML, and LLM-enhanced reports.
# Reports are stored in MinIO and linked to the scan in PostgreSQL.
# =============================================================================

from __future__ import annotations

import logging
import os
import time
import traceback
from typing import Any

from spiderfoot.celery_app import celery_app

logger = logging.getLogger("sf.tasks.report")


@celery_app.task(
    name="spiderfoot.tasks.report.generate_pdf_report",
    bind=True,
    queue="report",
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=600,   # 10 min
    time_limit=900,        # 15 min
)
def generate_pdf_report(
    self,
    scan_id: str,
    global_opts: dict[str, Any],
    *,
    template: str = "default",
    branding: dict[str, Any] | None = None,
    include_executive_summary: bool = True,
    include_charts: bool = True,
    include_raw_data: bool = False,
    llm_enhanced: bool = False,
) -> dict[str, Any]:
    """Generate a branded PDF scan report.

    Args:
        scan_id:     Scan instance ID.
        global_opts: SpiderFoot configuration dict.
        template:    Report template name (maps to Jinja2 template).
        branding:    Custom branding dict (company_name, logo_url, colors).
        include_executive_summary: Include AI-generated executive summary.
        include_charts: Include visual charts (severity breakdown, timeline).
        include_raw_data: Include raw event data tables.
        llm_enhanced: Use LLM to enhance finding descriptions.

    Returns:
        dict with report_id, storage_url, file_size, page_count.
    """
    start = time.time()

    self.update_state(
        state="GENERATING",
        meta={
            "scan_id": scan_id,
            "template": template,
            "progress": 0,
        },
    )

    try:
        from spiderfoot.db import SpiderFootDb
        from spiderfoot.reporting.report_generator import ReportGenerator
        from spiderfoot.reporting.pdf_renderer import PDFRenderer

        dbh = SpiderFootDb(global_opts)

        # Gather scan data
        scan_info = dbh.scanInstanceGet(scan_id)
        if not scan_info:
            raise ValueError(f"Scan {scan_id} not found")

        events = dbh.scanResultEvent(scan_id)
        summary = dbh.scanResultSummary(scan_id)

        self.update_state(state="GENERATING", meta={"progress": 20})

        # Build report context
        report_context = {
            "scan_id": scan_id,
            "scan_name": scan_info[1] if len(scan_info) > 1 else scan_id,
            "target": scan_info[2] if len(scan_info) > 2 else "",
            "events": events,
            "summary": summary,
            "branding": branding or _default_branding(),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "include_executive_summary": include_executive_summary,
            "include_charts": include_charts,
            "include_raw_data": include_raw_data,
        }

        self.update_state(state="GENERATING", meta={"progress": 40})

        # LLM-enhanced descriptions (optional)
        if llm_enhanced:
            try:
                report_gen = ReportGenerator(global_opts)
                ai_report = report_gen.generate(scan_id)
                report_context["ai_sections"] = ai_report
                report_context["executive_summary"] = getattr(
                    ai_report, "executive_summary", ""
                )
            except Exception as e:
                logger.warning(f"LLM enhancement failed, continuing without: {e}")
                report_context["ai_sections"] = None

        self.update_state(state="GENERATING", meta={"progress": 60})

        # Render PDF
        renderer = PDFRenderer(template_name=template)
        pdf_bytes, page_count = renderer.render(report_context)

        self.update_state(state="GENERATING", meta={"progress": 80})

        # Store in MinIO
        report_key = f"reports/{scan_id}/{scan_id}_report.pdf"
        storage_url = _store_report(pdf_bytes, report_key, global_opts)

        duration = time.time() - start

        result = {
            "scan_id": scan_id,
            "report_id": f"rpt_{scan_id}",
            "status": "completed",
            "storage_url": storage_url,
            "storage_key": report_key,
            "file_size_bytes": len(pdf_bytes),
            "page_count": page_count,
            "template": template,
            "llm_enhanced": llm_enhanced,
            "duration_seconds": round(duration, 2),
        }

        logger.info(
            "report.pdf.completed",
            extra={"scan_id": scan_id, "pages": page_count, "size": len(pdf_bytes)},
        )

        return result

    except Exception as exc:
        logger.error(
            "report.pdf.failed",
            extra={"scan_id": scan_id, "error": str(exc)},
        )
        raise self.retry(exc=exc)


@celery_app.task(
    name="spiderfoot.tasks.report.generate_html_report",
    bind=True,
    queue="report",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def generate_html_report(
    self,
    scan_id: str,
    global_opts: dict[str, Any],
    *,
    template: str = "default",
) -> dict[str, Any]:
    """Generate an HTML scan report (lighter-weight than PDF)."""
    start = time.time()

    try:
        from spiderfoot.db import SpiderFootDb
        from spiderfoot.reporting.pdf_renderer import PDFRenderer

        dbh = SpiderFootDb(global_opts)
        scan_info = dbh.scanInstanceGet(scan_id)
        events = dbh.scanResultEvent(scan_id)
        summary = dbh.scanResultSummary(scan_id)

        report_context = {
            "scan_id": scan_id,
            "scan_name": scan_info[1] if len(scan_info) > 1 else scan_id,
            "target": scan_info[2] if len(scan_info) > 2 else "",
            "events": events,
            "summary": summary,
            "branding": _default_branding(),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        }

        renderer = PDFRenderer(template_name=template)
        html_str = renderer.render_html(report_context)

        report_key = f"reports/{scan_id}/{scan_id}_report.html"
        storage_url = _store_report(
            html_str.encode("utf-8"), report_key, global_opts,
            content_type="text/html",
        )

        return {
            "scan_id": scan_id,
            "status": "completed",
            "storage_url": storage_url,
            "file_size_bytes": len(html_str.encode("utf-8")),
            "duration_seconds": round(time.time() - start, 2),
        }

    except Exception as exc:
        logger.error("report.html.failed", extra={"scan_id": scan_id, "error": str(exc)})
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_branding() -> dict[str, Any]:
    return {
        "company_name": os.environ.get("SF_REPORT_COMPANY", "SpiderFoot"),
        "logo_url": os.environ.get("SF_REPORT_LOGO", ""),
        "primary_color": os.environ.get("SF_REPORT_COLOR_PRIMARY", "#1a73e8"),
        "secondary_color": os.environ.get("SF_REPORT_COLOR_SECONDARY", "#34a853"),
        "footer_text": os.environ.get(
            "SF_REPORT_FOOTER",
            "Generated by SpiderFoot — Open Source Intelligence Automation",
        ),
    }


def _store_report(
    data: bytes,
    key: str,
    opts: dict,
    content_type: str = "application/pdf",
) -> str:
    """Upload report bytes to MinIO and return the URL."""
    try:
        from minio import Minio
        import io

        endpoint = os.environ.get("SF_MINIO_ENDPOINT", "minio:9000")
        access_key = os.environ.get("SF_MINIO_ACCESS_KEY", opts.get("MINIO_ROOT_USER", "spiderfoot"))
        secret_key = os.environ.get("SF_MINIO_SECRET_KEY", opts.get("MINIO_ROOT_PASSWORD", "changeme123"))
        bucket = os.environ.get("SF_MINIO_REPORTS_BUCKET", "sf-reports")
        secure = os.environ.get("SF_MINIO_SECURE", "false").lower() == "true"

        client = Minio(endpoint, access_key, secret_key, secure=secure)

        client.put_object(
            bucket,
            key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

        return f"{'https' if secure else 'http'}://{endpoint}/{bucket}/{key}"

    except Exception as e:
        logger.error(f"MinIO upload failed: {e}")
        # Fall back to returning the key (can be resolved later)
        return f"minio://{key}"
