"""
Qdrant Snapshot Manager — backs up Qdrant collections to MinIO.

Provides scheduled and on-demand snapshotting of Qdrant vector
collections, uploading the snapshots to the sf-qdrant-snapshots
MinIO bucket for disaster recovery.

Usage::

    from spiderfoot.storage.qdrant_backup import QdrantBackupManager

    mgr = QdrantBackupManager()
    mgr.snapshot_collection("sf_scan_ABC123")
    mgr.snapshot_all_collections()

The backup manager uses the Qdrant HTTP API to create snapshots,
downloads them, and then uploads to MinIO via the storage manager.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger("spiderfoot.storage.qdrant_backup")


class QdrantBackupManager:
    """Manages Qdrant collection snapshots and uploads to MinIO."""

    def __init__(
        self,
        qdrant_url: str | None = None,
        storage_manager: Any | None = None,
    ) -> None:
        import os
        host = os.environ.get("SF_QDRANT_HOST", "qdrant")
        port = os.environ.get("SF_QDRANT_PORT", "6333")
        self._qdrant_url = qdrant_url or f"http://{host}:{port}"
        self._storage = storage_manager

    @property
    def storage(self) -> Any:
        """Lazy-load the MinIO storage manager."""
        if self._storage is None:
            from spiderfoot.storage.minio_manager import get_storage_manager
            self._storage = get_storage_manager()
        return self._storage

    def snapshot_collection(self, collection_name: str) -> dict[str, Any]:
        """Create a snapshot of a single collection and upload to MinIO.

        Returns metadata about the snapshot.
        """
        log.info("Creating snapshot for collection: %s", collection_name)

        # 1. Create snapshot via Qdrant REST API
        resp = requests.post(
            f"{self._qdrant_url}/collections/{collection_name}/snapshots",
            timeout=120,
        )
        resp.raise_for_status()
        snapshot_info = resp.json().get("result", {})
        snapshot_name = snapshot_info.get("name", "")

        if not snapshot_name:
            raise ValueError(f"Failed to create snapshot for {collection_name}")

        log.info("Snapshot created: %s/%s", collection_name, snapshot_name)

        # 2. Download snapshot from Qdrant
        dl_resp = requests.get(
            f"{self._qdrant_url}/collections/{collection_name}/snapshots/{snapshot_name}",
            stream=True,
            timeout=300,
        )
        dl_resp.raise_for_status()
        snapshot_data = dl_resp.content

        # 3. Upload to MinIO
        snapshot_id = snapshot_name.replace(".snapshot", "")
        self.storage.put_qdrant_snapshot(collection_name, snapshot_id, snapshot_data)

        # 4. Clean up snapshot on Qdrant (optional - saves disk space)
        try:
            requests.delete(
                f"{self._qdrant_url}/collections/{collection_name}/snapshots/{snapshot_name}",
                timeout=30,
            )
        except Exception:
            pass  # Non-critical

        result = {
            "collection": collection_name,
            "snapshot_name": snapshot_name,
            "size_bytes": len(snapshot_data),
            "minio_key": f"collections/{collection_name}/{snapshot_id}.snapshot",
            "timestamp": time.time(),
        }
        log.info(
            "Snapshot uploaded to MinIO: %s (%d bytes)",
            result["minio_key"],
            result["size_bytes"],
        )
        return result

    def snapshot_all_collections(self, prefix: str = "sf_") -> list[dict[str, Any]]:
        """Snapshot all SpiderFoot collections (matching prefix) to MinIO."""
        resp = requests.get(f"{self._qdrant_url}/collections", timeout=30)
        resp.raise_for_status()

        collections = resp.json().get("result", {}).get("collections", [])
        results: list[dict[str, Any]] = []

        for col in collections:
            name = col.get("name", "")
            if not name.startswith(prefix):
                continue
            try:
                result = self.snapshot_collection(name)
                results.append(result)
            except Exception as e:
                log.warning("Failed to snapshot collection %s: %s", name, e)
                results.append({
                    "collection": name,
                    "error": str(e),
                })

        log.info("Snapshotted %d collections to MinIO", len(results))
        return results

    def restore_collection(
        self, collection_name: str, snapshot_id: str
    ) -> dict[str, Any]:
        """Restore a collection from a MinIO snapshot.

        Downloads the snapshot from MinIO and uploads it to Qdrant
        for restoration.
        """
        log.info("Restoring collection %s from snapshot %s", collection_name, snapshot_id)

        # Download from MinIO
        data = self.storage.get_qdrant_snapshot(collection_name, snapshot_id)

        # Upload to Qdrant for recovery
        snapshot_name = f"{snapshot_id}.snapshot"
        resp = requests.post(
            f"{self._qdrant_url}/collections/{collection_name}/snapshots/upload",
            files={"snapshot": (snapshot_name, data)},
            timeout=300,
        )
        resp.raise_for_status()

        return {
            "collection": collection_name,
            "snapshot_id": snapshot_id,
            "size_bytes": len(data),
            "status": "restored",
        }

    def list_snapshots(self, collection_name: str = "") -> list[dict[str, Any]]:
        """List all snapshots stored in MinIO."""
        return self.storage.list_qdrant_snapshots(collection_name)
