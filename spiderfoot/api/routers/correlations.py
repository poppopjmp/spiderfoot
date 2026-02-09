"""
Correlation management endpoints for SpiderFoot API.

Cycle 26 rewrite — delegates to ``CorrelationService`` instead of
raw ``SpiderFootDb`` / config manipulation.  Uses ``PaginationParams``
and ``PaginatedResponse`` from Cycle 25.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from ..dependencies import get_app_config, optional_auth, get_correlation_svc
from ..pagination import PaginationParams, PaginatedResponse, paginate
from spiderfoot.correlation_service import CorrelationService, CorrelationResult
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)
optional_auth_dep = Depends(optional_auth)


# -----------------------------------------------------------------------
# Request / response models
# -----------------------------------------------------------------------

class CorrelationRuleRequest(BaseModel):
    """Request model for creating a correlation rule."""
    name: str = Field(..., description="Rule name")
    description: str = Field(..., description="Rule description")
    risk: str = Field(..., description="Risk level: HIGH, MEDIUM, LOW, INFO")
    logic: str = Field(..., description="Rule logic/query")
    enabled: bool = Field(True, description="Whether rule is enabled")
    tags: Optional[List[str]] = Field(None, description="Rule tags")


class CorrelationRuleUpdate(BaseModel):
    """Partial-update model for a correlation rule."""
    name: Optional[str] = Field(None, description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    risk: Optional[str] = Field(None, description="Risk level")
    logic: Optional[str] = Field(None, description="Rule logic/query")
    enabled: Optional[bool] = Field(None, description="Whether rule is enabled")
    tags: Optional[List[str]] = Field(None, description="Rule tags")


# -----------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------

def _result_to_dict(r: CorrelationResult) -> dict:
    """Serialise a ``CorrelationResult`` to a JSON-safe dict."""
    return {
        "rule_id": r.rule_id,
        "rule_name": r.rule_name,
        "headline": r.headline,
        "risk": r.risk,
        "scan_id": r.scan_id,
        "event_count": r.event_count,
        "events": r.events,
        "timestamp": r.timestamp,
    }


# -----------------------------------------------------------------------
# CRUD — correlation rules
# -----------------------------------------------------------------------

@router.get("/correlation-rules")
async def list_correlation_rules(
    api_key: str = optional_auth_dep,
    risk: Optional[str] = Query(None, description="Filter by risk level"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    params: PaginationParams = Depends(),
    svc: CorrelationService = Depends(get_correlation_svc),
):
    """List correlation rules with optional filtering and pagination."""
    try:
        rules = svc.filter_rules(risk=risk, enabled=enabled, tag=tag)
        return paginate(rules, params)
    except Exception as e:
        logger.error("Failed to list correlation rules: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/correlation-rules", status_code=201)
async def create_correlation_rule(
    rule_data: CorrelationRuleRequest,
    api_key: str = optional_auth_dep,
    svc: CorrelationService = Depends(get_correlation_svc),
):
    """Create a new correlation rule."""
    try:
        now = datetime.now().isoformat()
        new_rule = {
            "name": rule_data.name,
            "description": rule_data.description,
            "risk": rule_data.risk.upper(),
            "logic": rule_data.logic,
            "enabled": rule_data.enabled,
            "tags": rule_data.tags or [],
            "created": now,
            "modified": now,
        }
        created = svc.add_rule(new_rule)
        logger.info("Created correlation rule: %s", created.get("id"))
        return {"rule": created, "message": "Correlation rule created successfully"}
    except Exception as e:
        logger.error("Failed to create correlation rule: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/correlation-rules/{rule_id}")
async def get_correlation_rule(
    rule_id: str,
    api_key: str = optional_auth_dep,
    svc: CorrelationService = Depends(get_correlation_svc),
):
    """Get a specific correlation rule by ID."""
    rule = svc.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Correlation rule not found")
    return {"rule": rule}


@router.put("/correlation-rules/{rule_id}")
async def update_correlation_rule(
    rule_id: str,
    rule_data: CorrelationRuleUpdate,
    api_key: str = optional_auth_dep,
    svc: CorrelationService = Depends(get_correlation_svc),
):
    """Update a correlation rule (partial)."""
    updates = {k: v for k, v in rule_data.dict().items() if v is not None}
    if "risk" in updates:
        updates["risk"] = updates["risk"].upper()
    updates["modified"] = datetime.now().isoformat()

    updated = svc.update_rule(rule_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Correlation rule not found")

    logger.info("Updated correlation rule: %s", rule_id)
    return {"rule": updated, "message": "Correlation rule updated successfully"}


@router.delete("/correlation-rules/{rule_id}")
async def delete_correlation_rule(
    rule_id: str,
    api_key: str = optional_auth_dep,
    svc: CorrelationService = Depends(get_correlation_svc),
):
    """Delete a correlation rule."""
    removed = svc.delete_rule(rule_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Correlation rule not found")

    logger.info("Deleted correlation rule: %s", rule_id)
    return {"message": "Correlation rule deleted successfully"}


# -----------------------------------------------------------------------
# Execution / analysis
# -----------------------------------------------------------------------

@router.post("/correlation-rules/{rule_id}/test")
async def test_correlation_rule(
    rule_id: str,
    test_data: Dict[str, Any] = Body(
        ..., description="Test data (must include scan_id)"
    ),
    api_key: str = optional_auth_dep,
    svc: CorrelationService = Depends(get_correlation_svc),
):
    """Run a single correlation rule against a scan and return results."""
    rule = svc.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Correlation rule not found")

    scan_id = test_data.get("scan_id")
    if not scan_id:
        raise HTTPException(
            status_code=400, detail="scan_id is required in test_data"
        )

    try:
        import time as _time

        t0 = _time.monotonic()
        results = svc.run_for_scan(scan_id, rule_ids=[rule_id])
        elapsed_ms = round((_time.monotonic() - t0) * 1000, 1)

        return {
            "test_result": {
                "rule_id": rule_id,
                "rule_name": rule.get("name"),
                "test_passed": len(results) == 0,
                "matches": [_result_to_dict(r) for r in results],
                "risk_level": rule.get("risk"),
                "match_count": len(results),
                "execution_time_ms": elapsed_ms,
            },
            "message": "Rule test completed successfully",
        }
    except Exception as e:
        logger.error("Failed to test correlation rule %s: %s", rule_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/scans/{scan_id}/correlations/detailed")
async def get_detailed_scan_correlations(
    scan_id: str,
    api_key: str = optional_auth_dep,
    risk: Optional[str] = Query(None, description="Filter by risk level"),
    rule_id: Optional[str] = Query(None, description="Filter by specific rule"),
    params: PaginationParams = Depends(),
    svc: CorrelationService = Depends(get_correlation_svc),
):
    """Get detailed correlation results for a scan via CorrelationService."""
    try:
        # Attempt to get cached results first; fall back to live run
        results = svc.get_results(scan_id)
        if not results:
            rule_ids = [rule_id] if rule_id else None
            results = svc.run_for_scan(scan_id, rule_ids=rule_ids)

        # Apply risk filter
        if risk:
            results = [r for r in results if r.risk.upper() == risk.upper()]
        if rule_id and not risk:
            results = [r for r in results if r.rule_id == rule_id]

        dicts = [_result_to_dict(r) for r in results]
        resp = paginate(dicts, params)

        # Build risk summary from full (pre-paginated) list
        risk_summary: Dict[str, int] = {}
        for r in results:
            risk_summary[r.risk] = risk_summary.get(r.risk, 0) + 1

        resp["scan_id"] = scan_id
        resp["summary"] = {
            "total_correlations": len(results),
            "risk_breakdown": risk_summary,
            "high_risk_count": risk_summary.get("HIGH", 0),
            "medium_risk_count": risk_summary.get("MEDIUM", 0),
            "low_risk_count": risk_summary.get("LOW", 0),
        }
        return resp

    except Exception as e:
        logger.error(
            "Failed to get correlations for scan %s: %s", scan_id, e
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/correlations/analyze")
async def analyze_correlation_patterns(
    analysis_request: Dict[str, Any] = Body(
        ..., description="Analysis configuration"
    ),
    api_key: str = optional_auth_dep,
    svc: CorrelationService = Depends(get_correlation_svc),
):
    """Run correlation analysis across multiple scans."""
    scan_ids: List[str] = analysis_request.get("scan_ids", [])
    rule_ids: Optional[List[str]] = analysis_request.get("rule_ids") or None

    if not scan_ids:
        raise HTTPException(
            status_code=400, detail="No scan_ids provided for analysis"
        )

    try:
        import time as _time

        t0 = _time.monotonic()
        all_results: List[CorrelationResult] = []
        for sid in scan_ids:
            all_results.extend(svc.run_for_scan(sid, rule_ids=rule_ids))
        elapsed_ms = round((_time.monotonic() - t0) * 1000, 1)

        # Aggregate — rule frequency
        rule_freq: Dict[str, int] = {}
        for r in all_results:
            rule_freq[r.rule_name] = rule_freq.get(r.rule_name, 0) + 1

        common = [
            {"rule_name": name, "frequency": freq}
            for name, freq in sorted(
                rule_freq.items(), key=lambda x: x[1], reverse=True
            )[:10]
        ]

        # Risk breakdown
        risk_summary: Dict[str, int] = {}
        for r in all_results:
            risk_summary[r.risk] = risk_summary.get(r.risk, 0) + 1

        return {
            "analysis_id": f"analysis_{int(datetime.now().timestamp())}",
            "scan_count": len(scan_ids),
            "total_correlations_analyzed": len(all_results),
            "patterns": {
                "common_correlations": common,
                "risk_breakdown": risk_summary,
            },
            "results": [_result_to_dict(r) for r in all_results],
            "analysis_timestamp": datetime.now().isoformat(),
            "analysis_duration_ms": elapsed_ms,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to analyze correlation patterns: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
