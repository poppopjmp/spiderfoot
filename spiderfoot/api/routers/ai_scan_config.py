"""
AI Scan Configuration API router.

Endpoints for intelligent scan parameter recommendation.

v5.6.3
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from ..dependencies import get_api_key
from pydantic import BaseModel, Field

from spiderfoot.ai_scan_config import (
    AIScanConfigurator,
    ScanObjective,
    TargetType,
    StealthLevel,
)

_log = logging.getLogger("spiderfoot.api.ai_scan_config")

router = APIRouter(dependencies=[Depends(get_api_key)])

# Singleton configurator (Redis injected at startup if available)
_configurator = AIScanConfigurator()


def _get_configurator() -> AIScanConfigurator:
    return _configurator


# ── Request / Response models ─────────────────────────────────────────

class RecommendRequest(BaseModel):
    """Request body for scan recommendation."""
    target: str = Field(..., description="Scan target (domain, IP, email, etc.)")
    target_type: str = Field(..., description="Type of target (domain, ip_address, etc.)")
    objective: str = Field("recon", description="Scan objective")
    stealth: str = Field("low", description="Stealth level")
    include_api_key_modules: bool = Field(True, description="Include modules requiring API keys")
    max_modules: Optional[int] = Field(None, description="Max number of modules", ge=1, le=100)
    exclude_modules: list[str] = Field(default_factory=list, description="Modules to exclude")
    prefer_modules: list[str] = Field(default_factory=list, description="Modules to prefer")
    scope_limit: Optional[str] = Field(None, description="Scope constraint (e.g. target_only)")


class FeedbackRequest(BaseModel):
    """Feedback on a recommendation."""
    recommendation_id: str = Field(..., description="Recommendation ID")
    rating: int = Field(..., ge=1, le=5, description="1-5 star rating")
    actual_duration_minutes: Optional[int] = Field(None, description="Actual scan duration")
    actual_events: Optional[int] = Field(None, description="Actual event count")
    notes: str = Field("", description="Free-form feedback")


class CompareRequest(BaseModel):
    """Request to compare multiple configurations."""
    target: str
    target_type: str
    objectives: list[str] = Field(..., min_length=2, max_length=5,
                                  description="Objectives to compare")
    stealth: str = Field("low")


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/ai-config/recommend")
async def recommend_scan_config(req: RecommendRequest):
    """Generate an AI-powered scan configuration recommendation.

    Analyses the target type, scan objective, and stealth requirements to
    produce an optimal module selection, timing configuration, and scope.
    """
    cfg = _get_configurator()

    try:
        target_type = TargetType(req.target_type)
    except ValueError:
        valid = [t.value for t in TargetType]
        raise HTTPException(400, f"Invalid target_type. Valid: {valid}")

    try:
        objective = ScanObjective(req.objective)
    except ValueError:
        valid = [o.value for o in ScanObjective]
        raise HTTPException(400, f"Invalid objective. Valid: {valid}")

    try:
        stealth = StealthLevel(req.stealth)
    except ValueError:
        valid = [s.value for s in StealthLevel]
        raise HTTPException(400, f"Invalid stealth level. Valid: {valid}")

    rec = cfg.recommend(
        target=req.target,
        target_type=target_type,
        objective=objective,
        stealth=stealth,
        include_api_key_modules=req.include_api_key_modules,
        max_modules=req.max_modules,
        exclude_modules=req.exclude_modules,
        prefer_modules=req.prefer_modules,
        scope_limit=req.scope_limit,
    )

    return {
        "recommendation": {
            "id": rec.recommendation_id,
            "target": rec.target,
            "target_type": rec.target_type,
            "objective": rec.objective,
            "stealth_level": rec.stealth_level,
            "confidence": rec.confidence,
            "modules": rec.modules,
            "module_count": rec.module_count,
            "timing": rec.timing,
            "scope": {
                "max_depth": rec.max_depth,
                "follow_redirects": rec.follow_redirects,
                "include_subdomains": rec.include_subdomains,
                "include_affiliates": rec.include_affiliates,
            },
            "estimates": {
                "duration_minutes": rec.estimated_duration_minutes,
                "events": rec.estimated_events,
                "api_calls": rec.estimated_api_calls,
            },
            "warnings": rec.warnings,
            "notes": rec.notes,
            "created_at": rec.created_at,
            "engine_version": rec.engine_version,
        }
    }


@router.get("/ai-config/recommend/{recommendation_id}")
async def get_recommendation(recommendation_id: str):
    """Retrieve a previously generated recommendation by ID."""
    cfg = _get_configurator()
    rec = cfg.get_recommendation(recommendation_id)
    if not rec:
        raise HTTPException(404, "Recommendation not found or expired")
    return {"recommendation": rec.__dict__}


@router.post("/ai-config/compare")
async def compare_objectives(req: CompareRequest):
    """Compare scan configurations across multiple objectives.

    Useful for understanding trade-offs between different scan approaches.
    """
    cfg = _get_configurator()

    try:
        target_type = TargetType(req.target_type)
    except ValueError:
        raise HTTPException(400, f"Invalid target_type: {req.target_type}")

    try:
        stealth = StealthLevel(req.stealth)
    except ValueError:
        raise HTTPException(400, f"Invalid stealth: {req.stealth}")

    comparisons = []
    for obj_str in req.objectives:
        try:
            objective = ScanObjective(obj_str)
        except ValueError:
            raise HTTPException(400, f"Invalid objective: {obj_str}")

        rec = cfg.recommend(
            target=req.target,
            target_type=target_type,
            objective=objective,
            stealth=stealth,
        )
        comparisons.append({
            "objective": obj_str,
            "module_count": rec.module_count,
            "confidence": rec.confidence,
            "estimated_duration_minutes": rec.estimated_duration_minutes,
            "estimated_events": rec.estimated_events,
            "stealth_level": rec.stealth_level,
            "active_modules": sum(
                1 for m in rec.modules
                if not m.get("category") in ("search_engine", "whois", "certificate")
            ),
            "passive_modules": sum(
                1 for m in rec.modules
                if m.get("category") in ("search_engine", "whois", "certificate")
            ),
        })

    return {
        "target": req.target,
        "target_type": req.target_type,
        "comparisons": comparisons,
    }


@router.post("/ai-config/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Submit feedback on a scan recommendation to improve future suggestions."""
    cfg = _get_configurator()
    result = cfg.submit_feedback(
        recommendation_id=req.recommendation_id,
        rating=req.rating,
        actual_duration_minutes=req.actual_duration_minutes,
        actual_events=req.actual_events,
        notes=req.notes,
    )
    return result


@router.get("/ai-config/presets")
async def list_presets():
    """List available scan objective presets with descriptions."""
    cfg = _get_configurator()
    return {"presets": cfg.get_presets()}


@router.get("/ai-config/target-types")
async def list_target_types():
    """List supported target types."""
    cfg = _get_configurator()
    return {"target_types": cfg.get_target_types()}


@router.get("/ai-config/stealth-levels")
async def list_stealth_levels():
    """List available stealth levels with timing profiles."""
    cfg = _get_configurator()
    return {"stealth_levels": cfg.get_stealth_levels()}


@router.get("/ai-config/modules")
async def list_module_catalog(
    category: Optional[str] = Query(None, description="Filter by category"),
    passive_only: bool = Query(False, description="Only passive modules"),
    target_type: Optional[str] = Query(None, description="Filter by compatible target type"),
):
    """List the module catalog used by the AI configurator."""
    cfg = _get_configurator()
    modules = cfg.get_module_catalog()

    if category:
        modules = [m for m in modules if m["category"] == category]
    if passive_only:
        modules = [m for m in modules if m["passive"]]
    if target_type:
        modules = [m for m in modules if target_type in m["targets"]]

    return {"modules": modules, "total": len(modules)}
