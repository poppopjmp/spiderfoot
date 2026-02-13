"""
Custom Report Templates API router — template CRUD, rendering, export/import.

v5.7.2
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from spiderfoot.report_templates import ReportTemplateManager, TemplateCategory, TemplateFormat

router = APIRouter()

_manager = ReportTemplateManager()


# -------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------

class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    category: str = Field("custom")
    output_format: str = Field("html", description="html | markdown | json | text")
    author: str = ""
    header_template: str = ""
    body_template: str = Field(..., min_length=1)
    footer_template: str = ""
    css_styles: str = ""
    sections: list[dict] = Field(default_factory=list)
    variables: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    output_format: str | None = None
    header_template: str | None = None
    body_template: str | None = None
    footer_template: str | None = None
    css_styles: str | None = None
    tags: list[str] | None = None
    version: str | None = None


class RenderRequest(BaseModel):
    template_id: str = Field(...)
    scan_data: dict = Field(default_factory=dict)
    variables: dict = Field(default_factory=dict)


class CloneRequest(BaseModel):
    new_name: str = ""


# -------------------------------------------------------------------
# Template CRUD
# -------------------------------------------------------------------

@router.get("/report-templates", tags=["report-templates"])
async def list_templates(
    category: str | None = Query(None),
    output_format: str | None = Query(None),
    builtin_only: bool = Query(False),
):
    """List report templates."""
    templates = _manager.list_templates(
        category=category, output_format=output_format,
        builtin_only=builtin_only,
    )
    return {"templates": [t.to_dict() for t in templates]}


@router.post("/report-templates", tags=["report-templates"], status_code=201)
async def create_template(body: TemplateCreate):
    """Create a new report template."""
    t = _manager.create_template(body.model_dump())
    return {"template": t.to_dict()}


@router.get("/report-templates/{template_id}", tags=["report-templates"])
async def get_template(template_id: str):
    """Get a template by ID."""
    t = _manager.get_template(template_id)
    if not t:
        raise HTTPException(404, "Template not found")
    return t.to_dict()


@router.patch("/report-templates/{template_id}", tags=["report-templates"])
async def update_template(template_id: str, body: TemplateUpdate):
    """Update a report template."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    t = _manager.update_template(template_id, updates)
    if not t:
        raise HTTPException(404, "Template not found")
    return {"updated": t.to_dict()}


@router.delete("/report-templates/{template_id}", tags=["report-templates"])
async def delete_template(template_id: str):
    """Delete a custom template (built-in templates cannot be deleted)."""
    if not _manager.delete_template(template_id):
        raise HTTPException(400, "Cannot delete template (not found or built-in)")
    return {"deleted": template_id}


@router.post("/report-templates/{template_id}/clone", tags=["report-templates"])
async def clone_template(template_id: str, body: CloneRequest):
    """Clone a template for customization."""
    clone = _manager.clone_template(template_id, body.new_name)
    if not clone:
        raise HTTPException(404, "Template not found")
    return {"cloned": clone.to_dict()}


# -------------------------------------------------------------------
# Rendering
# -------------------------------------------------------------------

@router.post("/report-templates/render", tags=["report-templates"])
async def render_report(body: RenderRequest):
    """Render a report from a template with scan data."""
    report = _manager.render(
        template_id=body.template_id,
        scan_data=body.scan_data,
        variables=body.variables,
    )
    return report.to_dict()


@router.get("/report-templates/history", tags=["report-templates"])
async def render_history(limit: int = Query(20, ge=1, le=200)):
    """Get recent render history."""
    history = _manager.get_render_history(limit=limit)
    return {"history": [r.to_dict() for r in history]}


# -------------------------------------------------------------------
# Export / Import
# -------------------------------------------------------------------

@router.get("/report-templates/{template_id}/export", tags=["report-templates"])
async def export_template(template_id: str):
    """Export a template for sharing."""
    data = _manager.export_template(template_id)
    if not data:
        raise HTTPException(404, "Template not found")
    return data


@router.post("/report-templates/import", tags=["report-templates"], status_code=201)
async def import_template(body: dict):
    """Import a template from exported data."""
    t = _manager.import_template(body)
    return {"imported": t.to_dict()}


# -------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------

@router.get("/report-templates/variables", tags=["report-templates"])
async def list_variables():
    """List variables available in template context."""
    return {"variables": _manager.get_available_variables()}


@router.get("/report-templates/categories", tags=["report-templates"])
async def list_categories():
    """List template categories."""
    return {"categories": _manager.get_categories()}


@router.get("/report-templates/formats", tags=["report-templates"])
async def list_formats():
    """List supported output formats."""
    return {
        "formats": [
            {"id": f.value, "description": {
                "html": "HTML document with styling",
                "markdown": "Markdown document",
                "json": "Structured JSON data",
                "text": "Plain text output",
            }.get(f.value, f.value)}
            for f in TemplateFormat
        ]
    }
