"""MinIO / S3 object storage management API endpoints.

Exposes MinIO storage operations for scan reports, backups,
Qdrant snapshots, and general data artefacts.

Endpoints
---------
GET  /storage/health      — MinIO connectivity & bucket status
POST /storage/buckets     — ensure all required buckets exist
GET  /storage/reports/{scan_id}  — list reports for a scan
GET  /storage/reports/{scan_id}/{report_id} — download (presigned URL)
DELETE /storage/reports/{scan_id}/{report_id} — delete report
GET  /storage/backups     — list PostgreSQL backups
POST /storage/backups/cleanup  — remove old backups
GET  /storage/snapshots   — list Qdrant snapshots
POST /storage/snapshots/{collection} — create Qdrant snapshot
POST /storage/snapshots/all  — snapshot all collections
GET  /storage/objects/{bucket} — list objects in a bucket
"""

from __future__ import annotations

import logging
import re as _re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..dependencies import optional_auth, get_api_key

log = logging.getLogger("spiderfoot.api.storage")

_SAFE_BUCKET_RE = _re.compile(r'^[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$')
_SAFE_NAME_RE = _re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._\-]{0,253}$')


def _validate_bucket(name: str) -> str:
    """Validate S3 bucket name — only SpiderFoot buckets allowed."""
    if not _SAFE_BUCKET_RE.match(name) or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid bucket name")
    if not name.startswith("sf-"):
        raise HTTPException(status_code=403, detail="Access to non-SpiderFoot buckets is denied")
    return name


def _validate_name(name: str, label: str = "name") -> str:
    """Reject path-traversal characters in storage names."""
    if ".." in name or "/" in name or "\\" in name or not _SAFE_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail=f"Invalid {label}")
    return name

router = APIRouter(dependencies=[Depends(get_api_key)])
optional_auth_dep = Depends(optional_auth)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class StorageHealth(BaseModel):
    """MinIO health check response."""
    status: str
    endpoint: str = ""
    buckets_found: int = 0
    missing_buckets: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    message: str = ""


class BucketInitResponse(BaseModel):
    """Response from bucket initialization."""
    created: list[str] = Field(default_factory=list)
    message: str = ""


class ObjectInfo(BaseModel):
    """Object metadata."""
    key: str
    size: int | None = None
    last_modified: str | None = None
    etag: str | None = None


class SnapshotRequest(BaseModel):
    """Qdrant snapshot request."""
    collection_prefix: str = Field("sf_", description="Collection name prefix filter")


class BackupCleanupRequest(BaseModel):
    """Backup cleanup parameters."""
    retention_days: int = Field(30, ge=1, le=365, description="Days to retain")


class SnapshotResult(BaseModel):
    """Qdrant snapshot result."""
    collection: str
    snapshot_name: str = ""
    size_bytes: int = 0
    minio_key: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Storage manager dependency
# ---------------------------------------------------------------------------

def _get_storage():
    """Get the MinIO storage manager."""
    try:
        from spiderfoot.storage.minio_manager import get_storage_manager
        return get_storage_manager()
    except Exception as e:
        log.exception("MinIO storage not available")
        raise HTTPException(
            status_code=503,
            detail="MinIO storage not available",
        )


def _get_qdrant_backup():
    """Get the Qdrant backup manager."""
    try:
        from spiderfoot.storage.qdrant_backup import QdrantBackupManager
        return QdrantBackupManager()
    except Exception as e:
        log.exception("Qdrant backup manager not available")
        raise HTTPException(
            status_code=503,
            detail="Qdrant backup manager not available",
        )


# ---------------------------------------------------------------------------
# Health & initialization
# ---------------------------------------------------------------------------

@router.get("/health", response_model=StorageHealth, dependencies=[optional_auth_dep])
async def storage_health():
    """Check MinIO connectivity and bucket status."""
    mgr = _get_storage()
    result = mgr.health_check()
    return StorageHealth(**result)


@router.post("/buckets", response_model=BucketInitResponse, dependencies=[optional_auth_dep])
async def ensure_buckets():
    """Create all required MinIO buckets if they don't exist."""
    mgr = _get_storage()
    try:
        created = mgr.ensure_buckets()
        return BucketInitResponse(
            created=created,
            message=f"Created {len(created)} buckets" if created else "All buckets already exist",
        )
    except Exception as e:
        log.exception("Storage operation failed")
        raise HTTPException(status_code=500, detail="Storage operation failed")


# ---------------------------------------------------------------------------
# Report management
# ---------------------------------------------------------------------------

@router.get("/reports/{scan_id}", dependencies=[optional_auth_dep])
async def list_scan_reports(scan_id: str) -> list[ObjectInfo]:
    """List all reports stored in MinIO for a scan."""
    mgr = _get_storage()
    objects = mgr.list_reports(scan_id)
    return [ObjectInfo(**obj) for obj in objects]


@router.get("/reports/{scan_id}/{report_id}/url", dependencies=[optional_auth_dep])
async def presign_report(
    scan_id: str,
    report_id: str,
    extension: str = Query("json", description="File extension"),
    expires: int = Query(3600, ge=60, le=86400, description="URL expiry in seconds"),
) -> dict[str, str]:
    """Generate a presigned download URL for a report."""
    mgr = _get_storage()
    try:
        url = mgr.presign_report(scan_id, report_id, extension=extension, expires=expires)
        return {"url": url, "expires_in": str(expires)}
    except Exception as e:
        log.warning("Report not found: %s", e)
        raise HTTPException(status_code=404, detail="Report not found")


@router.delete("/reports/{scan_id}/{report_id}", dependencies=[optional_auth_dep])
async def delete_report(
    scan_id: str,
    report_id: str,
    extension: str = Query("json", description="File extension"),
) -> dict[str, str]:
    """Delete a report from MinIO."""
    mgr = _get_storage()
    try:
        mgr.delete_report(scan_id, report_id, extension=extension)
        return {"status": "deleted", "scan_id": scan_id, "report_id": report_id}
    except Exception as e:
        log.warning("Snapshot not found: %s", e)
        raise HTTPException(status_code=404, detail="Snapshot not found")


@router.delete("/scans/{scan_id}", dependencies=[optional_auth_dep])
async def delete_scan_data(scan_id: str) -> dict[str, Any]:
    """Delete ALL MinIO objects for a scan (reports, exports, artefacts)."""
    mgr = _get_storage()
    removed = mgr.delete_scan_data(scan_id)
    return {"scan_id": scan_id, "objects_removed": removed}


# ---------------------------------------------------------------------------
# PostgreSQL backup management
# ---------------------------------------------------------------------------

@router.get("/backups", dependencies=[optional_auth_dep])
async def list_pg_backups() -> list[ObjectInfo]:
    """List all PostgreSQL backups in MinIO."""
    mgr = _get_storage()
    objects = mgr.list_pg_backups()
    return [ObjectInfo(**obj) for obj in objects]


@router.post("/backups/cleanup", dependencies=[optional_auth_dep])
async def cleanup_old_backups(req: BackupCleanupRequest) -> dict[str, Any]:
    """Remove PostgreSQL backups older than retention period."""
    mgr = _get_storage()
    removed = mgr.cleanup_old_backups(retention_days=req.retention_days)
    return {"removed": removed, "retention_days": req.retention_days}


# ---------------------------------------------------------------------------
# Qdrant snapshot management
# ---------------------------------------------------------------------------

@router.get("/snapshots", dependencies=[optional_auth_dep])
async def list_qdrant_snapshots(
    collection: str = Query("", description="Filter by collection name"),
) -> list[ObjectInfo]:
    """List Qdrant snapshots stored in MinIO."""
    mgr = _get_storage()
    objects = mgr.list_qdrant_snapshots(collection)
    return [ObjectInfo(**obj) for obj in objects]


@router.post("/snapshots/{collection}", dependencies=[optional_auth_dep])
async def snapshot_collection(collection: str) -> SnapshotResult:
    """Create a snapshot of a single Qdrant collection and upload to MinIO."""
    _validate_name(collection, "collection")
    backup = _get_qdrant_backup()
    try:
        result = backup.snapshot_collection(collection)
        return SnapshotResult(**result)
    except Exception as e:
        log.exception("Storage operation failed")
        raise HTTPException(status_code=500, detail="Storage operation failed")


@router.post("/snapshots/all", dependencies=[optional_auth_dep])
async def snapshot_all_collections(req: SnapshotRequest | None = None) -> list[SnapshotResult]:
    """Snapshot all SpiderFoot Qdrant collections to MinIO."""
    backup = _get_qdrant_backup()
    prefix = req.collection_prefix if req else "sf_"
    results = backup.snapshot_all_collections(prefix=prefix)
    return [SnapshotResult(**r) for r in results]


# ---------------------------------------------------------------------------
# Generic object browser
# ---------------------------------------------------------------------------

@router.get("/objects/{bucket}", dependencies=[optional_auth_dep])
async def list_bucket_objects(
    bucket: str,
    prefix: str = Query("", description="Key prefix filter"),
    max_results: int = Query(100, ge=1, le=1000),
) -> list[ObjectInfo]:
    """List objects in any MinIO bucket with optional prefix filter."""
    _validate_bucket(bucket)
    mgr = _get_storage()
    objects = mgr.list_objects(bucket, prefix=prefix)
    return [ObjectInfo(**obj) for obj in objects[:max_results]]
