# -*- coding: utf-8 -*-
"""
API Key management router — CRUD operations for API keys.

Endpoints:
  GET    /api/keys          - List all API keys
  POST   /api/keys          - Create a new API key
  GET    /api/keys/{id}     - Get key details
  PUT    /api/keys/{id}     - Update key metadata
  DELETE /api/keys/{id}     - Delete a key
  POST   /api/keys/{id}/revoke - Revoke (disable) a key
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..dependencies import get_api_key

log = logging.getLogger("spiderfoot.api.keys")

router = APIRouter(prefix="/api/keys", tags=["api-keys"])

api_key_dep = Depends(get_api_key)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class KeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    role: str = Field("viewer", description="RBAC role (viewer/analyst/operator/admin)")
    scopes: list[str] = Field(default_factory=list, description="Optional permission overrides")
    expires_in_days: int = Field(0, ge=0, le=3650, description="Days until expiry (0 = never)")
    description: str = ""


class KeyCreateResponse(BaseModel):
    key_id: str
    full_key: str
    name: str
    role: str
    message: str = "Store the full_key securely — it cannot be retrieved again."


class KeyDetailResponse(BaseModel):
    key_id: str
    name: str
    role: str
    scopes: list[str]
    created_at: float
    expires_at: float
    last_used_at: float
    enabled: bool
    created_by: str
    description: str


class KeyUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    scopes: list[str] | None = None
    enabled: bool | None = None
    description: str | None = None


class KeyListResponse(BaseModel):
    keys: list[KeyDetailResponse]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=KeyListResponse)
async def list_keys(
    api_key: str = api_key_dep,
) -> KeyListResponse:
    """List all API keys (hashes are never exposed)."""
    from spiderfoot.api_keys import get_api_key_manager
    mgr = get_api_key_manager()
    records = mgr.list_keys()
    return KeyListResponse(
        keys=[KeyDetailResponse(**r.to_dict()) for r in records],
        total=len(records),
    )


@router.post("", status_code=201, response_model=KeyCreateResponse)
async def create_key(
    request: KeyCreateRequest,
    api_key: str = api_key_dep,
) -> KeyCreateResponse:
    """Create a new API key.

    The full key is returned ONLY in this response.
    Store it securely — it cannot be retrieved again.
    """
    from spiderfoot.api_keys import get_api_key_manager
    mgr = get_api_key_manager()
    try:
        key_id, full_key = mgr.create_key(
            name=request.name,
            role=request.role,
            scopes=request.scopes,
            expires_in_days=request.expires_in_days,
            description=request.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return KeyCreateResponse(
        key_id=key_id,
        full_key=full_key,
        name=request.name,
        role=request.role,
    )


@router.get("/{key_id}", response_model=KeyDetailResponse)
async def get_key(
    key_id: str,
    api_key: str = api_key_dep,
) -> KeyDetailResponse:
    """Get API key details (hash is never exposed)."""
    from spiderfoot.api_keys import get_api_key_manager
    mgr = get_api_key_manager()
    record = mgr.get_key(key_id)
    if not record:
        raise HTTPException(status_code=404, detail="API key not found")
    return KeyDetailResponse(**record.to_dict())


@router.put("/{key_id}", response_model=KeyDetailResponse)
async def update_key(
    key_id: str,
    request: KeyUpdateRequest,
    api_key: str = api_key_dep,
) -> KeyDetailResponse:
    """Update an API key's metadata (role, name, scopes, etc.)."""
    from spiderfoot.api_keys import get_api_key_manager
    mgr = get_api_key_manager()
    try:
        record = mgr.update_key(
            key_id,
            name=request.name,
            role=request.role,
            scopes=request.scopes,
            enabled=request.enabled,
            description=request.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not record:
        raise HTTPException(status_code=404, detail="API key not found")
    return KeyDetailResponse(**record.to_dict())


@router.delete("/{key_id}", status_code=204)
async def delete_key(
    key_id: str,
    api_key: str = api_key_dep,
) -> None:
    """Permanently delete an API key."""
    from spiderfoot.api_keys import get_api_key_manager
    mgr = get_api_key_manager()
    if not mgr.delete_key(key_id):
        raise HTTPException(status_code=404, detail="API key not found")


@router.post("/{key_id}/revoke", response_model=dict)
async def revoke_key(
    key_id: str,
    api_key: str = api_key_dep,
) -> dict:
    """Revoke (disable) an API key without deleting it."""
    from spiderfoot.api_keys import get_api_key_manager
    mgr = get_api_key_manager()
    if not mgr.revoke_key(key_id):
        raise HTTPException(status_code=404, detail="API key not found")
    return {"key_id": key_id, "message": "Key revoked"}
