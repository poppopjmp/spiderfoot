"""
Tag & Group API router — manage tags, asset groups, and assignments.

v5.7.3
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from ..dependencies import get_api_key
from pydantic import BaseModel, Field
from typing import Any

from spiderfoot.tag_group import TagGroupManager, TagColor

router = APIRouter(dependencies=[Depends(get_api_key)])

_manager = TagGroupManager()


# -------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------

class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    color: str = Field("blue")
    parent_tag: str = ""
    tenant_id: str = ""


class TagUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    parent_tag: str | None = None


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    members: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    dynamic_rules: list[dict] = Field(default_factory=list)
    owner: str = ""
    tenant_id: str = ""


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    dynamic_rules: list[dict] | None = None


class AssignRequest(BaseModel):
    tag_id: str = Field(...)
    resource_type: str = Field(..., description="scan | event | asset | group | target")
    resource_id: str = Field(...)


class MemberRequest(BaseModel):
    member: str = Field(..., min_length=1)


# -------------------------------------------------------------------
# Tag CRUD
# -------------------------------------------------------------------

@router.get("/tags", tags=["tags-groups"])
async def list_tags(
    parent: str | None = Query(None),
    tenant_id: str | None = Query(None),
):
    tags = _manager.list_tags(parent=parent, tenant_id=tenant_id)
    return {"tags": [t.to_dict() for t in tags]}


@router.post("/tags", tags=["tags-groups"], status_code=201)
async def create_tag(body: TagCreate):
    t = _manager.create_tag(body.model_dump())
    return {"tag": t.to_dict()}


@router.get("/tags/tree", tags=["tags-groups"])
async def tag_tree():
    return {"tree": _manager.get_tag_tree()}


@router.get("/tags/{tag_id}", tags=["tags-groups"])
async def get_tag(tag_id: str):
    t = _manager.get_tag(tag_id)
    if not t:
        raise HTTPException(404, "Tag not found")
    return t.to_dict()


@router.patch("/tags/{tag_id}", tags=["tags-groups"])
async def update_tag(tag_id: str, body: TagUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    t = _manager.update_tag(tag_id, updates)
    if not t:
        raise HTTPException(404, "Tag not found")
    return {"updated": t.to_dict()}


@router.delete("/tags/{tag_id}", tags=["tags-groups"])
async def delete_tag(tag_id: str):
    if not _manager.delete_tag(tag_id):
        raise HTTPException(404, "Tag not found")
    return {"deleted": tag_id}


# -------------------------------------------------------------------
# Groups
# -------------------------------------------------------------------

@router.get("/groups", tags=["tags-groups"])
async def list_groups(tenant_id: str | None = Query(None)):
    groups = _manager.list_groups(tenant_id=tenant_id)
    return {"groups": [g.to_dict() for g in groups]}


@router.post("/groups", tags=["tags-groups"], status_code=201)
async def create_group(body: GroupCreate):
    g = _manager.create_group(body.model_dump())
    return {"group": g.to_dict()}


@router.get("/groups/{group_id}", tags=["tags-groups"])
async def get_group(group_id: str):
    g = _manager.get_group(group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    return g.to_dict()


@router.patch("/groups/{group_id}", tags=["tags-groups"])
async def update_group(group_id: str, body: GroupUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    g = _manager.update_group(group_id, updates)
    if not g:
        raise HTTPException(404, "Group not found")
    return {"updated": g.to_dict()}


@router.delete("/groups/{group_id}", tags=["tags-groups"])
async def delete_group(group_id: str):
    if not _manager.delete_group(group_id):
        raise HTTPException(404, "Group not found")
    return {"deleted": group_id}


@router.post("/groups/{group_id}/members", tags=["tags-groups"])
async def add_member(group_id: str, body: MemberRequest):
    if not _manager.add_member(group_id, body.member):
        raise HTTPException(404, "Group not found")
    return {"added": body.member, "group_id": group_id}


@router.delete("/groups/{group_id}/members/{member}", tags=["tags-groups"])
async def remove_member(group_id: str, member: str):
    if not _manager.remove_member(group_id, member):
        raise HTTPException(404, "Group or member not found")
    return {"removed": member}


# -------------------------------------------------------------------
# Tag assignments
# -------------------------------------------------------------------

@router.post("/tags/assign", tags=["tags-groups"])
async def assign_tag(body: AssignRequest):
    a = _manager.assign_tag(body.tag_id, body.resource_type, body.resource_id)
    if not a:
        raise HTTPException(404, "Tag not found")
    return {"assignment": a.to_dict()}


@router.post("/tags/unassign", tags=["tags-groups"])
async def unassign_tag(body: AssignRequest):
    if not _manager.unassign_tag(body.tag_id, body.resource_type, body.resource_id):
        raise HTTPException(404, "Assignment not found")
    return {"unassigned": True}


@router.get("/tags/for/{resource_type}/{resource_id}", tags=["tags-groups"])
async def get_tags_for_resource(resource_type: str, resource_id: str):
    tags = _manager.get_tags_for_resource(resource_type, resource_id)
    return {"tags": [t.to_dict() for t in tags]}


@router.get("/tags/{tag_id}/resources", tags=["tags-groups"])
async def get_resources_by_tag(
    tag_id: str,
    resource_type: str | None = Query(None),
):
    resources = _manager.get_resources_by_tag(tag_id, resource_type)
    return {"resources": [r.to_dict() for r in resources]}


# -------------------------------------------------------------------
# Auto-tagging & stats
# -------------------------------------------------------------------

@router.post("/tags/auto-tag", tags=["tags-groups"])
async def auto_tag_event(event_type: str, resource_id: str):
    applied = _manager.auto_tag_event(event_type, resource_id)
    return {"applied": [a.to_dict() for a in applied]}


@router.get("/tags/stats", tags=["tags-groups"])
async def tag_stats():
    return _manager.get_stats()


@router.get("/tags/colors", tags=["tags-groups"])
async def list_colors():
    return {"colors": [c.value for c in TagColor]}
