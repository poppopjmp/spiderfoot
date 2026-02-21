# -*- coding: utf-8 -*-
"""
Scan Engine router — CRUD for scan engine YAML profiles.

Provides REST endpoints for managing reusable scan engine configurations:
  - List available engines
  - Get engine details
  - Create/update custom engines
  - Delete engines
  - Validate engine YAML
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from spiderfoot.scan_engine import (
    ScanEngine,
    ScanEngineError,
    ScanEngineLoader,
    ScanIntensity,
    ScanScope,
)

from ..dependencies import get_api_key

log = logging.getLogger("spiderfoot.api.engines")

router = APIRouter(prefix="/api/engines", tags=["engines"])

# Dependency
api_key_dep = Depends(get_api_key)
optional_auth_dep = Depends(get_api_key)

# Singleton loader
_loader: ScanEngineLoader | None = None


def get_engine_loader() -> ScanEngineLoader:
    global _loader
    if _loader is None:
        _loader = ScanEngineLoader()
    return _loader


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class EngineListItem(BaseModel):
    name: str
    description: str = ""
    file: str = ""
    intensity: str = "normal"
    tags: list[str] = []


class EngineListResponse(BaseModel):
    engines: list[EngineListItem]
    total: int


class ScopeSchema(BaseModel):
    scope: str = "subdomains"
    include_patterns: list[str] = []
    exclude_patterns: list[str] = []
    max_depth: int = 3
    follow_redirects: bool = True
    include_ipv6: bool = False


class RateLimitSchema(BaseModel):
    max_threads: int = 10
    request_delay_ms: int = 0
    max_requests_per_second: float = 0
    scan_timeout_minutes: int = 0
    module_timeout_seconds: int = 300
    dns_timeout_seconds: int = 10
    http_timeout_seconds: int = 15


class ModuleSchema(BaseModel):
    enabled: bool = True
    options: dict[str, Any] = {}
    priority: int = 5


class ReportSchema(BaseModel):
    formats: list[str] = ["html"]
    auto_generate: bool = False
    include_raw_data: bool = False
    include_executive_summary: bool = True
    include_charts: bool = True
    llm_enhanced: bool = False
    template: str = "default"


class NotificationSchema(BaseModel):
    enabled: bool = False
    on_complete: bool = True
    on_high_severity: bool = True
    channels: list[str] = []


class EngineCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    version: str = "1.0"
    author: str = ""
    tags: list[str] = []
    intensity: str = "normal"
    scope: ScopeSchema = ScopeSchema()
    rate_limit: RateLimitSchema = RateLimitSchema()
    modules: dict[str, ModuleSchema | bool] = {}
    module_groups: list[str] = []
    exclude_modules: list[str] = []
    report: ReportSchema = ReportSchema()
    notification: NotificationSchema = NotificationSchema()
    metadata: dict[str, Any] = {}


class EngineDetailResponse(BaseModel):
    name: str
    description: str
    version: str
    author: str
    tags: list[str]
    intensity: str
    scope: dict[str, Any]
    rate_limit: dict[str, Any]
    modules: dict[str, Any]
    module_groups: list[str]
    exclude_modules: list[str]
    report: dict[str, Any]
    notification: dict[str, Any]
    metadata: dict[str, Any]
    enabled_modules: list[str]


class EngineValidateRequest(BaseModel):
    engine: dict[str, Any]


class EngineValidateResponse(BaseModel):
    valid: bool
    name: str = ""
    errors: list[str] = []
    module_count: int = 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=EngineListResponse)
async def list_engines(
    api_key: str = optional_auth_dep,
) -> EngineListResponse:
    """List all available scan engine profiles."""
    loader = get_engine_loader()
    engines = loader.list_engines()
    return EngineListResponse(
        engines=[EngineListItem(**e) for e in engines],
        total=len(engines),
    )


@router.get("/{engine_name}", response_model=EngineDetailResponse)
async def get_engine(
    engine_name: str,
    api_key: str = optional_auth_dep,
) -> EngineDetailResponse:
    """Get a scan engine profile by name."""
    loader = get_engine_loader()
    try:
        engine = loader.load(engine_name)
    except ScanEngineError as e:
        log.warning("Engine not found: %s", e)
        raise HTTPException(status_code=404, detail="Engine not found")

    data = engine.to_dict()
    data["enabled_modules"] = engine.get_enabled_modules()
    return EngineDetailResponse(**data)


@router.post("", status_code=201, response_model=EngineDetailResponse)
async def create_engine(
    request: EngineCreateRequest,
    api_key: str = api_key_dep,
) -> EngineDetailResponse:
    """Create a new scan engine profile."""
    loader = get_engine_loader()

    # Check if engine already exists
    existing = loader.list_engines()
    for e in existing:
        if e["name"].lower() == request.name.lower():
            raise HTTPException(
                status_code=409,
                detail=f"Engine '{request.name}' already exists. Use PUT to update.",
            )

    try:
        engine = loader.load_from_dict(request.model_dump())
        loader.save(engine)
    except ScanEngineError as e:
        log.warning("Invalid engine configuration: %s", e)
        raise HTTPException(status_code=422, detail="Invalid engine configuration")

    data = engine.to_dict()
    data["enabled_modules"] = engine.get_enabled_modules()
    return EngineDetailResponse(**data)


@router.put("/{engine_name}", response_model=EngineDetailResponse)
async def update_engine(
    engine_name: str,
    request: EngineCreateRequest,
    api_key: str = api_key_dep,
) -> EngineDetailResponse:
    """Update an existing scan engine profile."""
    loader = get_engine_loader()

    try:
        engine = loader.load_from_dict(request.model_dump())
        loader.save(engine, name=engine_name)
    except ScanEngineError as e:
        log.warning("Invalid engine configuration: %s", e)
        raise HTTPException(status_code=422, detail="Invalid engine configuration")

    data = engine.to_dict()
    data["enabled_modules"] = engine.get_enabled_modules()
    return EngineDetailResponse(**data)


@router.delete("/{engine_name}", status_code=204)
async def delete_engine(
    engine_name: str,
    api_key: str = api_key_dep,
) -> None:
    """Delete a scan engine profile."""
    import os
    from pathlib import Path

    loader = get_engine_loader()
    path = loader.engines_dir / f"{engine_name}.yaml"
    if not path.exists():
        path = loader.engines_dir / f"{engine_name}.yml"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Engine '{engine_name}' not found")

    os.remove(path)
    # Clear from cache
    if engine_name in loader._cache:
        del loader._cache[engine_name]

    log.info("Deleted scan engine: %s", engine_name)


@router.post("/validate", response_model=EngineValidateResponse)
async def validate_engine(
    request: EngineValidateRequest,
    api_key: str = optional_auth_dep,
) -> EngineValidateResponse:
    """Validate a scan engine configuration without saving it."""
    loader = get_engine_loader()
    errors = []

    try:
        engine = loader.load_from_dict(request.engine)

        # Additional validations
        if not engine.name:
            errors.append("Engine name is required")
        if not engine.modules and not engine.module_groups:
            errors.append("At least one module or module_group must be specified")

        return EngineValidateResponse(
            valid=len(errors) == 0,
            name=engine.name,
            errors=errors,
            module_count=len(engine.get_enabled_modules()),
        )
    except ScanEngineError as e:
        return EngineValidateResponse(
            valid=False,
            errors=[str(e)],
        )
    except Exception as e:
        return EngineValidateResponse(
            valid=False,
            errors=[f"Unexpected error: {str(e)}"],
        )
