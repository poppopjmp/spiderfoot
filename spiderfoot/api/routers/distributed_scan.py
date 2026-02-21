"""
Distributed Scanning API router — manage worker pools and distributed scans.

Endpoints for worker registration, scan distribution, chunk progress,
and pool statistics.

v5.7.0
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from spiderfoot.distributed_scan import (
    DistributedScanManager,
    BalancingStrategy,
    WorkerStatus,
)
from ..dependencies import get_api_key

router = APIRouter(dependencies=[Depends(get_api_key)])

_manager = DistributedScanManager()


# -------------------------------------------------------------------
# Pydantic schemas
# -------------------------------------------------------------------

class WorkerRegister(BaseModel):
    hostname: str = Field(..., min_length=1)
    ip_address: str = ""
    capabilities: list[str] = Field(default_factory=list)
    max_concurrent: int = Field(4, ge=1, le=64)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HeartbeatRequest(BaseModel):
    current_load: int | None = None


class DistributeRequest(BaseModel):
    scan_id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    modules: list[str] = Field(..., min_length=1)
    strategy: str = Field(
        BalancingStrategy.LEAST_LOADED.value,
        description="round_robin | least_loaded | capability_match | random",
    )


class ChunkUpdate(BaseModel):
    progress_pct: float | None = Field(None, ge=0, le=100)
    events_found: int | None = Field(None, ge=0)
    status: str | None = None
    error: str | None = None


# -------------------------------------------------------------------
# Worker endpoints
# -------------------------------------------------------------------

@router.post("/distributed/workers", tags=["distributed-scan"], status_code=201)
async def register_worker(body: WorkerRegister):
    """Register a new worker node in the pool."""
    node = _manager.register_worker(body.model_dump())
    return {"worker": node.to_dict()}


@router.get("/distributed/workers", tags=["distributed-scan"])
async def list_workers(
    status: str | None = Query(None, description="Filter by status"),
):
    """List all registered workers."""
    workers = _manager.list_workers(status=status)
    return {"workers": [w.to_dict() for w in workers]}


@router.get("/distributed/workers/{worker_id}", tags=["distributed-scan"])
async def get_worker(worker_id: str):
    """Get a specific worker's details."""
    node = _manager.get_worker(worker_id)
    if not node:
        raise HTTPException(404, f"Worker '{worker_id}' not found")
    return node.to_dict()


@router.post("/distributed/workers/{worker_id}/heartbeat", tags=["distributed-scan"])
async def worker_heartbeat(worker_id: str, body: HeartbeatRequest):
    """Send a heartbeat from a worker."""
    if not _manager.heartbeat(worker_id, load=body.current_load):
        raise HTTPException(404, f"Worker '{worker_id}' not found")
    return {"ok": True}


@router.post("/distributed/workers/{worker_id}/drain", tags=["distributed-scan"])
async def drain_worker(worker_id: str):
    """Put a worker in draining mode (no new work)."""
    if not _manager.drain_worker(worker_id):
        raise HTTPException(404, f"Worker '{worker_id}' not found")
    return {"drained": worker_id}


@router.delete("/distributed/workers/{worker_id}", tags=["distributed-scan"])
async def deregister_worker(worker_id: str):
    """Remove a worker from the pool."""
    if not _manager.deregister_worker(worker_id):
        raise HTTPException(404, f"Worker '{worker_id}' not found")
    return {"deregistered": worker_id}


# -------------------------------------------------------------------
# Scan distribution
# -------------------------------------------------------------------

@router.post("/distributed/scans", tags=["distributed-scan"], status_code=201)
async def distribute_scan(body: DistributeRequest):
    """Distribute a scan across available workers."""
    try:
        BalancingStrategy(body.strategy)
    except ValueError:
        raise HTTPException(400, f"Invalid strategy: {body.strategy}")

    dscan = _manager.distribute_scan(
        scan_id=body.scan_id,
        target=body.target,
        modules=body.modules,
        strategy=body.strategy,
    )
    return dscan.to_dict()


@router.get("/distributed/scans", tags=["distributed-scan"])
async def list_distributed_scans(
    status: str | None = Query(None),
):
    """List distributed scans."""
    scans = _manager.list_scans(status=status)
    return {"scans": [s.to_dict() for s in scans]}


@router.get("/distributed/scans/{scan_id}", tags=["distributed-scan"])
async def get_distributed_scan(scan_id: str):
    """Get details of a distributed scan."""
    dscan = _manager.get_scan(scan_id)
    if not dscan:
        raise HTTPException(404, f"Scan '{scan_id}' not found")
    return dscan.to_dict()


@router.get("/distributed/scans/{scan_id}/progress", tags=["distributed-scan"])
async def scan_progress(scan_id: str):
    """Get aggregated progress for a distributed scan."""
    progress = _manager.get_scan_progress(scan_id)
    if not progress:
        raise HTTPException(404, f"Scan '{scan_id}' not found")
    return progress


# -------------------------------------------------------------------
# Chunk management
# -------------------------------------------------------------------

@router.patch("/distributed/chunks/{chunk_id}", tags=["distributed-scan"])
async def update_chunk(chunk_id: str, body: ChunkUpdate):
    """Update progress/status for a scan chunk."""
    chunk = _manager.update_chunk_progress(
        chunk_id=chunk_id,
        progress_pct=body.progress_pct,
        events_found=body.events_found,
        status=body.status,
        error=body.error,
    )
    if not chunk:
        raise HTTPException(404, f"Chunk '{chunk_id}' not found")
    return chunk.to_dict()


# -------------------------------------------------------------------
# Pool statistics
# -------------------------------------------------------------------

@router.get("/distributed/pool/stats", tags=["distributed-scan"])
async def pool_stats():
    """Get worker pool statistics."""
    return _manager.get_pool_stats()


@router.get("/distributed/strategies", tags=["distributed-scan"])
async def list_strategies():
    """List available load balancing strategies."""
    return {
        "strategies": [
            {"id": s.value, "description": {
                "round_robin": "Cycle through workers sequentially",
                "least_loaded": "Assign to worker with fewest active chunks",
                "capability_match": "Prefer workers with matching module capabilities",
                "random": "Random worker selection",
            }.get(s.value, s.value)}
            for s in BalancingStrategy
        ]
    }
