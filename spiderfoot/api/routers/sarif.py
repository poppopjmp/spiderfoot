"""SARIF export API router for SpiderFoot.

Provides SARIF v2.1.0 export for integration with GitHub Code Scanning,
Azure DevOps, and other SARIF consumers.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from spiderfoot.sarif_export import SARIFExporter, _SARIF_RULE_MAP

logger = logging.getLogger("spiderfoot.api.sarif")

router = APIRouter()


class SARIFExportRequest(BaseModel):
    scan_id: str
    scan_name: str = "SpiderFoot Scan"
    scan_target: str = ""
    events: list[dict[str, Any]] = []


class SARIFExportResponse(BaseModel):
    sarif: dict[str, Any]
    result_count: int
    rule_count: int
    summary: dict[str, int]


@router.post("/sarif/export", response_model=SARIFExportResponse, tags=["sarif"])
async def export_sarif(request: SARIFExportRequest):
    """Export scan events as a SARIF v2.1.0 document.

    The output is compatible with:
    - GitHub Code Scanning (upload via REST API)
    - Azure DevOps SARIF viewer
    - VS Code SARIF Viewer extension
    - Any SARIF 2.1.0 compliant tool
    """
    exporter = SARIFExporter(
        scan_id=request.scan_id,
        scan_name=request.scan_name,
        scan_target=request.scan_target,
    )

    converted = 0
    for event in request.events:
        ok = exporter.add_event(
            event_type=event.get("type", ""),
            data=event.get("data", ""),
            module=event.get("module", ""),
            source_event=event.get("source", ""),
            timestamp=event.get("timestamp", ""),
        )
        if ok:
            converted += 1

    sarif_doc = exporter.export()

    logger.info(
        "SARIF export: scan=%s results=%d rules=%d",
        request.scan_id, exporter.result_count, exporter.rule_count,
    )

    return SARIFExportResponse(
        sarif=sarif_doc,
        result_count=exporter.result_count,
        rule_count=exporter.rule_count,
        summary=exporter.summary(),
    )


@router.get("/sarif/rules", tags=["sarif"])
async def list_sarif_rules():
    """List all SARIF rules that SpiderFoot can produce."""
    rules = []
    for event_type, info in sorted(_SARIF_RULE_MAP.items()):
        rules.append({
            "ruleId": info["id"],
            "name": info["name"],
            "description": info["shortDescription"],
            "level": info["level"],
            "tags": info.get("tags", []),
            "eventType": event_type,
        })
    return {
        "rules": rules,
        "total": len(rules),
    }


@router.get("/sarif/schema", tags=["sarif"])
async def sarif_schema_info():
    """Return SARIF schema version and reference information."""
    return {
        "version": "2.1.0",
        "schema": "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json",
        "tool": "SpiderFoot",
        "supported_uploads": [
            "GitHub Code Scanning API",
            "Azure DevOps",
            "VS Code SARIF Viewer",
        ],
    }
