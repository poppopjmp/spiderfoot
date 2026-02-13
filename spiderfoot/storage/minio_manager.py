"""
MinIO / S3-compatible Object Storage Manager for SpiderFoot.

Provides a unified interface for storing and retrieving:
  - Scan reports (HTML, PDF, JSON, CSV)
  - Log archives (from Vector.dev S3 sink)
  - PostgreSQL backups (pg_dump files)
  - Qdrant snapshots
  - General data artefacts

All data is organised under a ``data/`` prefix structure::

    sf-reports/
        scans/{scan_id}/reports/{report_id}.{ext}
        scans/{scan_id}/exports/{export_id}.{ext}
    sf-logs/
        events/{category}/{YYYY}/{MM}/{DD}/events-*.json.gz
        logs/{YYYY}/{MM}/{DD}/logs-*.json.gz
    sf-pg-backups/
        daily/{YYYY-MM-DD}/spiderfoot.sql.gz
        wal/{timeline}/{segment}.gz
    sf-qdrant-snapshots/
        collections/{collection_name}/{snapshot_id}.snapshot
    sf-data/
        scans/{scan_id}/artefacts/{filename}
        cache/{hash}.bin

Usage::

    from spiderfoot.storage.minio_manager import MinIOStorageManager, MinIOConfig

    mgr = MinIOStorageManager(MinIOConfig.from_env())
    mgr.put_report(scan_id, report_id, data, content_type="application/pdf")
    url = mgr.presign_report(scan_id, report_id, expires=3600)

    # Streaming upload
    mgr.put_object("sf-data", "scans/ABC123/raw.json", fp, length)

    # Backup PostgreSQL
    mgr.put_pg_backup("2026-02-13", data)
"""

from __future__ import annotations

import io
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, BinaryIO

log = logging.getLogger("spiderfoot.storage.minio")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class MinIOConfig:
    """MinIO / S3-compatible storage configuration."""

    endpoint: str = "localhost:9000"
    access_key: str = "spiderfoot"
    secret_key: str = "changeme123"
    secure: bool = False
    region: str = "us-east-1"

    # Bucket names
    reports_bucket: str = "sf-reports"
    logs_bucket: str = "sf-logs"
    pg_backups_bucket: str = "sf-pg-backups"
    qdrant_snapshots_bucket: str = "sf-qdrant-snapshots"
    data_bucket: str = "sf-data"

    @classmethod
    def from_env(cls) -> MinIOConfig:
        """Build config from SF_MINIO_* environment variables."""
        return cls(
            endpoint=os.environ.get("SF_MINIO_ENDPOINT", "localhost:9000").replace("http://", "").replace("https://", ""),
            access_key=os.environ.get("SF_MINIO_ACCESS_KEY", "spiderfoot"),
            secret_key=os.environ.get("SF_MINIO_SECRET_KEY", "changeme123"),
            secure=os.environ.get("SF_MINIO_SECURE", "false").lower() in ("true", "1", "yes"),
            region=os.environ.get("SF_MINIO_REGION", "us-east-1"),
            reports_bucket=os.environ.get("SF_MINIO_REPORTS_BUCKET", "sf-reports"),
            logs_bucket=os.environ.get("SF_MINIO_LOGS_BUCKET", "sf-logs"),
            pg_backups_bucket=os.environ.get("SF_MINIO_PG_BACKUPS_BUCKET", "sf-pg-backups"),
            qdrant_snapshots_bucket=os.environ.get("SF_MINIO_QDRANT_BUCKET", "sf-qdrant-snapshots"),
            data_bucket=os.environ.get("SF_MINIO_DATA_BUCKET", "sf-data"),
        )


# ---------------------------------------------------------------------------
# MinIO Storage Manager
# ---------------------------------------------------------------------------

class MinIOStorageManager:
    """Unified interface for all S3/MinIO operations."""

    def __init__(self, config: MinIOConfig | None = None) -> None:
        self._config = config or MinIOConfig.from_env()
        self._client: Any = None  # Lazy init

    @property
    def client(self) -> Any:
        """Lazy-initialise the MinIO client."""
        if self._client is None:
            try:
                from minio import Minio
                self._client = Minio(
                    self._config.endpoint,
                    access_key=self._config.access_key,
                    secret_key=self._config.secret_key,
                    secure=self._config.secure,
                    region=self._config.region,
                )
                log.info("MinIO client connected to %s", self._config.endpoint)
            except ImportError:
                raise ImportError(
                    "minio package is required. Install with: pip install minio"
                )
        return self._client

    # ------------------------------------------------------------------
    # Health / lifecycle
    # ------------------------------------------------------------------

    def health_check(self) -> dict[str, Any]:
        """Check MinIO connectivity and bucket availability."""
        t0 = time.monotonic()
        try:
            buckets = [b.name for b in self.client.list_buckets()]
            required = [
                self._config.reports_bucket,
                self._config.logs_bucket,
                self._config.pg_backups_bucket,
                self._config.qdrant_snapshots_bucket,
                self._config.data_bucket,
            ]
            missing = [b for b in required if b not in buckets]
            latency = (time.monotonic() - t0) * 1000
            return {
                "status": "up" if not missing else "degraded",
                "endpoint": self._config.endpoint,
                "buckets_found": len(buckets),
                "missing_buckets": missing,
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            return {
                "status": "down",
                "message": str(e),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            }

    def ensure_buckets(self) -> list[str]:
        """Create all required buckets if they don't exist.

        Returns list of newly created bucket names.
        """
        created: list[str] = []
        for bucket in [
            self._config.reports_bucket,
            self._config.logs_bucket,
            self._config.pg_backups_bucket,
            self._config.qdrant_snapshots_bucket,
            self._config.data_bucket,
        ]:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket, location=self._config.region)
                created.append(bucket)
                log.info("Created MinIO bucket: %s", bucket)
        return created

    # ------------------------------------------------------------------
    # Report storage
    # ------------------------------------------------------------------

    def put_report(
        self,
        scan_id: str,
        report_id: str,
        data: bytes | BinaryIO,
        content_type: str = "application/json",
        extension: str = "json",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Store a scan report in MinIO.

        Returns the object key.
        """
        key = f"scans/{scan_id}/reports/{report_id}.{extension}"
        self._put_data(self._config.reports_bucket, key, data, content_type, metadata)
        log.info("Stored report %s for scan %s", report_id, scan_id)
        return key

    def get_report(self, scan_id: str, report_id: str, extension: str = "json") -> bytes:
        """Retrieve a report from MinIO."""
        key = f"scans/{scan_id}/reports/{report_id}.{extension}"
        return self._get_data(self._config.reports_bucket, key)

    def presign_report(
        self, scan_id: str, report_id: str, extension: str = "json", expires: int = 3600
    ) -> str:
        """Generate a presigned URL for downloading a report."""
        key = f"scans/{scan_id}/reports/{report_id}.{extension}"
        return self.client.presigned_get_object(
            self._config.reports_bucket, key, expires=timedelta(seconds=expires)
        )

    def list_reports(self, scan_id: str) -> list[dict[str, Any]]:
        """List all reports for a scan."""
        prefix = f"scans/{scan_id}/reports/"
        return self._list_objects(self._config.reports_bucket, prefix)

    def delete_report(self, scan_id: str, report_id: str, extension: str = "json") -> None:
        """Delete a report from MinIO."""
        key = f"scans/{scan_id}/reports/{report_id}.{extension}"
        self.client.remove_object(self._config.reports_bucket, key)

    # ------------------------------------------------------------------
    # Export storage (CSV, GEXF, etc.)
    # ------------------------------------------------------------------

    def put_export(
        self,
        scan_id: str,
        export_id: str,
        data: bytes | BinaryIO,
        content_type: str = "text/csv",
        extension: str = "csv",
    ) -> str:
        """Store a scan export (CSV, GEXF, etc.) in MinIO."""
        key = f"scans/{scan_id}/exports/{export_id}.{extension}"
        self._put_data(self._config.reports_bucket, key, data, content_type)
        return key

    # ------------------------------------------------------------------
    # PostgreSQL backup storage
    # ------------------------------------------------------------------

    def put_pg_backup(
        self, date_str: str, data: bytes | BinaryIO, filename: str = "spiderfoot.sql.gz"
    ) -> str:
        """Store a pg_dump backup."""
        key = f"daily/{date_str}/{filename}"
        self._put_data(self._config.pg_backups_bucket, key, data, "application/gzip")
        log.info("Stored PG backup: %s", key)
        return key

    def list_pg_backups(self) -> list[dict[str, Any]]:
        """List all PostgreSQL backups."""
        return self._list_objects(self._config.pg_backups_bucket, "daily/")

    def get_pg_backup(self, date_str: str, filename: str = "spiderfoot.sql.gz") -> bytes:
        """Retrieve a PG backup for a given date."""
        key = f"daily/{date_str}/{filename}"
        return self._get_data(self._config.pg_backups_bucket, key)

    def cleanup_old_backups(self, retention_days: int = 30) -> int:
        """Remove PG backups older than retention_days. Returns count removed."""
        from datetime import datetime, timezone

        cutoff = time.time() - (retention_days * 86400)
        objects = self.client.list_objects(self._config.pg_backups_bucket, prefix="daily/", recursive=True)
        removed = 0
        for obj in objects:
            if obj.last_modified and obj.last_modified.timestamp() < cutoff:
                self.client.remove_object(self._config.pg_backups_bucket, obj.object_name)
                removed += 1
        if removed:
            log.info("Cleaned up %d old PG backups (retention=%d days)", removed, retention_days)
        return removed

    # ------------------------------------------------------------------
    # Qdrant snapshot storage
    # ------------------------------------------------------------------

    def put_qdrant_snapshot(
        self, collection_name: str, snapshot_id: str, data: bytes | BinaryIO
    ) -> str:
        """Store a Qdrant collection snapshot."""
        key = f"collections/{collection_name}/{snapshot_id}.snapshot"
        self._put_data(
            self._config.qdrant_snapshots_bucket, key, data, "application/octet-stream"
        )
        log.info("Stored Qdrant snapshot: %s/%s", collection_name, snapshot_id)
        return key

    def list_qdrant_snapshots(self, collection_name: str = "") -> list[dict[str, Any]]:
        """List Qdrant snapshots, optionally filtered by collection."""
        prefix = f"collections/{collection_name}/" if collection_name else "collections/"
        return self._list_objects(self._config.qdrant_snapshots_bucket, prefix)

    def get_qdrant_snapshot(self, collection_name: str, snapshot_id: str) -> bytes:
        """Retrieve a Qdrant snapshot."""
        key = f"collections/{collection_name}/{snapshot_id}.snapshot"
        return self._get_data(self._config.qdrant_snapshots_bucket, key)

    # ------------------------------------------------------------------
    # General data / artefact storage
    # ------------------------------------------------------------------

    def put_artefact(
        self,
        scan_id: str,
        filename: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Store a generic data artefact for a scan."""
        key = f"scans/{scan_id}/artefacts/{filename}"
        self._put_data(self._config.data_bucket, key, data, content_type)
        return key

    def get_artefact(self, scan_id: str, filename: str) -> bytes:
        """Retrieve a scan artefact."""
        key = f"scans/{scan_id}/artefacts/{filename}"
        return self._get_data(self._config.data_bucket, key)

    def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Low-level put to any bucket/key."""
        self._put_data(bucket, key, data, content_type, metadata)
        return key

    def get_object(self, bucket: str, key: str) -> bytes:
        """Low-level get from any bucket/key."""
        return self._get_data(bucket, key)

    def delete_object(self, bucket: str, key: str) -> None:
        """Delete object from bucket."""
        self.client.remove_object(bucket, key)

    def list_objects(
        self, bucket: str, prefix: str = "", recursive: bool = True
    ) -> list[dict[str, Any]]:
        """List objects in a bucket with optional prefix filter."""
        return self._list_objects(bucket, prefix, recursive)

    # ------------------------------------------------------------------
    # Scan data lifecycle helpers
    # ------------------------------------------------------------------

    def delete_scan_data(self, scan_id: str) -> int:
        """Delete all MinIO objects associated with a scan.

        Removes reports, exports, and artefacts. Returns total objects removed.
        """
        removed = 0
        for bucket in [self._config.reports_bucket, self._config.data_bucket]:
            prefix = f"scans/{scan_id}/"
            objects = self.client.list_objects(bucket, prefix=prefix, recursive=True)
            for obj in objects:
                self.client.remove_object(bucket, obj.object_name)
                removed += 1
        if removed:
            log.info("Deleted %d objects for scan %s", removed, scan_id)
        return removed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _put_data(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Upload data to MinIO."""
        if isinstance(data, bytes):
            stream = io.BytesIO(data)
            length = len(data)
        else:
            stream = data
            # Try to get length from the stream
            pos = stream.tell()
            stream.seek(0, 2)
            length = stream.tell() - pos
            stream.seek(pos)

        self.client.put_object(
            bucket,
            key,
            stream,
            length,
            content_type=content_type,
            metadata=metadata,
        )

    def _get_data(self, bucket: str, key: str) -> bytes:
        """Download data from MinIO."""
        response = None
        try:
            response = self.client.get_object(bucket, key)
            return response.read()
        finally:
            if response:
                response.close()
                response.release_conn()

    def _list_objects(
        self, bucket: str, prefix: str = "", recursive: bool = True
    ) -> list[dict[str, Any]]:
        """List objects and return structured metadata."""
        result: list[dict[str, Any]] = []
        objects = self.client.list_objects(bucket, prefix=prefix, recursive=recursive)
        for obj in objects:
            result.append({
                "key": obj.object_name,
                "size": obj.size,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                "etag": obj.etag,
                "content_type": getattr(obj, "content_type", None),
            })
        return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: MinIOStorageManager | None = None


def get_storage_manager() -> MinIOStorageManager:
    """Get or create the singleton MinIO storage manager."""
    global _manager
    if _manager is None:
        _manager = MinIOStorageManager(MinIOConfig.from_env())
    return _manager


def reset_storage_manager() -> None:
    """Reset the singleton (for testing)."""
    global _manager
    _manager = None
