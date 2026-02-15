"""
Plugin Marketplace API router.

Endpoints for browsing, installing, and managing SpiderFoot plugins.

v5.6.4
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from spiderfoot.plugin_marketplace import PluginMarketplace

_log = logging.getLogger("spiderfoot.api.marketplace")

router = APIRouter()

_marketplace = PluginMarketplace()


def _get_marketplace() -> PluginMarketplace:
    return _marketplace


# ── Request models ────────────────────────────────────────────────────

class RegisterPluginRequest(BaseModel):
    """Request to register a new plugin."""
    name: str = Field(..., min_length=3, max_length=100)
    module_name: str = Field(..., pattern=r"^sfp_[a-z0-9_]+$")
    description: str = Field(..., min_length=10, max_length=500)
    long_description: str = Field("", max_length=5000)
    category: str = Field("utility")
    latest_version: str = Field("1.0.0")
    produces: list[str] = Field(default_factory=list)
    consumes: list[str] = Field(default_factory=list)
    requires_api_key: bool = False
    target_types: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    homepage: str = Field("")
    repository: str = Field("")
    license: str = Field("MIT")
    author: dict = Field(default_factory=dict)


class InstallPluginRequest(BaseModel):
    """Request to install a plugin."""
    version: Optional[str] = Field(None, description="Specific version, or latest")


class ReviewRequest(BaseModel):
    """Request to submit a review."""
    user_id: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
    title: str = Field("", max_length=200)
    body: str = Field("", max_length=2000)


class UpdatePluginRequest(BaseModel):
    """Request to update plugin metadata."""
    name: Optional[str] = None
    description: Optional[str] = None
    long_description: Optional[str] = None
    category: Optional[str] = None
    latest_version: Optional[str] = None
    tags: Optional[list[str]] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None


# ── Browse / Search ───────────────────────────────────────────────────

@router.get("/marketplace/plugins")
async def search_plugins(
    q: str = Query("", description="Search query"),
    category: Optional[str] = Query(None),
    trust_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort_by: str = Query("downloads", description="Sort field"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Search and browse the plugin marketplace."""
    mp = _get_marketplace()
    return mp.search_plugins(
        query=q, category=category, trust_level=trust_level,
        status=status, sort_by=sort_by, page=page, page_size=page_size,
    )


@router.get("/marketplace/plugins/{plugin_id}")
async def get_plugin(plugin_id: str):
    """Get detailed information about a specific plugin."""
    mp = _get_marketplace()
    plugin = mp.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(404, "Plugin not found")
    return {"plugin": plugin}


@router.get("/marketplace/featured")
async def get_featured(limit: int = Query(10, ge=1, le=50)):
    """Get featured/popular plugins."""
    mp = _get_marketplace()
    return {"plugins": mp.get_featured(limit)}


@router.get("/marketplace/categories")
async def get_categories():
    """List plugin categories with counts."""
    mp = _get_marketplace()
    return {"categories": mp.get_categories()}


@router.get("/marketplace/stats")
async def get_stats():
    """Get marketplace statistics."""
    mp = _get_marketplace()
    return {"stats": mp.get_stats()}


# ── Installation ──────────────────────────────────────────────────────

@router.post("/marketplace/plugins/{plugin_id}/install")
async def install_plugin(plugin_id: str, req: InstallPluginRequest | None = None):
    """Install a plugin from the marketplace."""
    mp = _get_marketplace()
    version = req.version if req else None
    result = mp.install_plugin(plugin_id, version)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/marketplace/plugins/{plugin_id}/uninstall")
async def uninstall_plugin(plugin_id: str):
    """Uninstall a plugin."""
    mp = _get_marketplace()
    result = mp.uninstall_plugin(plugin_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/marketplace/installed")
async def get_installed():
    """List all installed plugins."""
    mp = _get_marketplace()
    return {"plugins": mp.get_installed()}


@router.get("/marketplace/updates")
async def check_updates():
    """Check for available plugin updates."""
    mp = _get_marketplace()
    return {"updates": mp.check_updates()}


# ── Reviews ───────────────────────────────────────────────────────────

@router.post("/marketplace/plugins/{plugin_id}/reviews")
async def add_review(plugin_id: str, req: ReviewRequest):
    """Submit a review for a plugin."""
    mp = _get_marketplace()
    result = mp.add_review(
        plugin_id=plugin_id,
        user_id=req.user_id,
        rating=req.rating,
        title=req.title,
        body=req.body,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return {"review": result}


@router.get("/marketplace/plugins/{plugin_id}/reviews")
async def get_reviews(
    plugin_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Get reviews for a plugin."""
    mp = _get_marketplace()
    return {"reviews": mp.get_reviews(plugin_id, limit)}


# ── Registration ──────────────────────────────────────────────────────

@router.post("/marketplace/register")
async def register_plugin(req: RegisterPluginRequest):
    """Register a new plugin in the marketplace."""
    mp = _get_marketplace()
    entry = req.model_dump()
    result = mp.register_plugin(entry)
    return {"plugin": result}


@router.put("/marketplace/plugins/{plugin_id}")
async def update_plugin(plugin_id: str, req: UpdatePluginRequest):
    """Update plugin metadata."""
    mp = _get_marketplace()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    result = mp.update_plugin(plugin_id, updates)
    if not result:
        raise HTTPException(404, "Plugin not found")
    return {"plugin": result}
