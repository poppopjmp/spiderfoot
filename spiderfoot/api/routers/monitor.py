# -*- coding: utf-8 -*-
"""
Subdomain monitoring router — Manage and query monitored domains.

Endpoints:
  GET    /api/monitor/domains           - List monitored domains
  POST   /api/monitor/domains           - Add a domain to monitor
  GET    /api/monitor/domains/{domain}  - Get domain details + snapshot
  PUT    /api/monitor/domains/{domain}  - Update domain settings
  DELETE /api/monitor/domains/{domain}  - Remove domain from monitoring
  GET    /api/monitor/domains/{domain}/changes - Get change history
  POST   /api/monitor/domains/{domain}/check   - Trigger immediate check
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..dependencies import get_api_key

log = logging.getLogger("spiderfoot.api.monitor")

router = APIRouter(prefix="/api/monitor", tags=["monitoring"])

api_key_dep = Depends(get_api_key)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MonitorDomainRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=500)
    check_interval_hours: float = Field(24.0, ge=0.5, le=720)
    notify_on_change: bool = True
    tags: list[str] = []


class MonitorDomainResponse(BaseModel):
    domain: str
    enabled: bool
    check_interval_hours: float
    last_check_at: float
    next_check_at: float
    subdomain_count: int
    total_changes: int
    created_at: float
    notify_on_change: bool
    tags: list[str] = []


class SubdomainChangeResponse(BaseModel):
    change_type: str
    hostname: str
    old_ips: list[str] = []
    new_ips: list[str] = []
    detected_at: float


class DomainDetailResponse(BaseModel):
    domain: MonitorDomainResponse
    subdomains: list[dict] = []
    recent_changes: list[SubdomainChangeResponse] = []


class DomainListResponse(BaseModel):
    domains: list[MonitorDomainResponse]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/domains", response_model=DomainListResponse)
async def list_monitored_domains(
    api_key: str = api_key_dep,
) -> DomainListResponse:
    """List all monitored domains."""
    from spiderfoot.subdomain_monitor import get_subdomain_monitor
    monitor = get_subdomain_monitor()
    domains = monitor.list_domains()
    return DomainListResponse(
        domains=[MonitorDomainResponse(**d.to_dict()) for d in domains],
        total=len(domains),
    )


@router.post("/domains", status_code=201, response_model=MonitorDomainResponse)
async def add_monitored_domain(
    request: MonitorDomainRequest,
    api_key: str = api_key_dep,
) -> MonitorDomainResponse:
    """Add a domain to the monitoring list."""
    from spiderfoot.subdomain_monitor import get_subdomain_monitor
    monitor = get_subdomain_monitor()

    existing = monitor.get_domain(request.domain)
    if existing:
        raise HTTPException(status_code=409, detail="Domain already monitored")

    md = monitor.add_domain(
        domain=request.domain,
        check_interval_hours=request.check_interval_hours,
        notify_on_change=request.notify_on_change,
        tags=request.tags,
    )
    return MonitorDomainResponse(**md.to_dict())


@router.get("/domains/{domain}", response_model=DomainDetailResponse)
async def get_monitored_domain(
    domain: str,
    api_key: str = api_key_dep,
) -> DomainDetailResponse:
    """Get monitored domain details with snapshot and recent changes."""
    from spiderfoot.subdomain_monitor import get_subdomain_monitor
    monitor = get_subdomain_monitor()

    md = monitor.get_domain(domain)
    if not md:
        raise HTTPException(status_code=404, detail="Domain not monitored")

    snapshot = monitor.get_snapshot(domain)
    changes = monitor.get_change_history(domain, limit=50)

    return DomainDetailResponse(
        domain=MonitorDomainResponse(**md.to_dict()),
        subdomains=[s.to_dict() for s in snapshot.values()],
        recent_changes=[SubdomainChangeResponse(**c.to_dict()) for c in changes],
    )


@router.put("/domains/{domain}", response_model=MonitorDomainResponse)
async def update_monitored_domain(
    domain: str,
    request: MonitorDomainRequest,
    api_key: str = api_key_dep,
) -> MonitorDomainResponse:
    """Update a monitored domain's settings."""
    from spiderfoot.subdomain_monitor import get_subdomain_monitor
    monitor = get_subdomain_monitor()

    md = monitor.update_domain(
        domain,
        check_interval_hours=request.check_interval_hours,
        notify_on_change=request.notify_on_change,
        tags=request.tags,
    )
    if not md:
        raise HTTPException(status_code=404, detail="Domain not monitored")

    return MonitorDomainResponse(**md.to_dict())


@router.delete("/domains/{domain}", status_code=204)
async def remove_monitored_domain(
    domain: str,
    api_key: str = api_key_dep,
) -> None:
    """Remove a domain from monitoring."""
    from spiderfoot.subdomain_monitor import get_subdomain_monitor
    monitor = get_subdomain_monitor()

    md = monitor.get_domain(domain)
    if not md:
        raise HTTPException(status_code=404, detail="Domain not monitored")

    monitor.remove_domain(domain)


@router.get("/domains/{domain}/changes", response_model=list[SubdomainChangeResponse])
async def get_domain_changes(
    domain: str,
    limit: int = Query(100, ge=1, le=1000),
    api_key: str = api_key_dep,
) -> list[SubdomainChangeResponse]:
    """Get change history for a monitored domain."""
    from spiderfoot.subdomain_monitor import get_subdomain_monitor
    monitor = get_subdomain_monitor()

    md = monitor.get_domain(domain)
    if not md:
        raise HTTPException(status_code=404, detail="Domain not monitored")

    changes = monitor.get_change_history(domain, limit=limit)
    return [SubdomainChangeResponse(**c.to_dict()) for c in changes]


@router.post("/domains/{domain}/check", response_model=dict)
async def trigger_domain_check(
    domain: str,
    api_key: str = api_key_dep,
) -> dict:
    """Trigger an immediate subdomain check for a domain.

    Dispatches a Celery task if available, otherwise returns instructions.
    """
    from spiderfoot.subdomain_monitor import get_subdomain_monitor
    monitor = get_subdomain_monitor()

    md = monitor.get_domain(domain)
    if not md:
        raise HTTPException(status_code=404, detail="Domain not monitored")

    try:
        from spiderfoot.celery_app import is_celery_available
        if is_celery_available():
            from spiderfoot.tasks.monitor import check_subdomain_changes
            task = check_subdomain_changes.apply_async(
                kwargs={"target": domain},
                queue="monitor",
            )
            return {
                "domain": domain,
                "task_id": task.id,
                "message": "Subdomain check dispatched",
            }
    except Exception as e:
        log.warning("Celery dispatch failed: %s", e)

    return {
        "domain": domain,
        "message": "Manual check required (Celery not available)",
    }
