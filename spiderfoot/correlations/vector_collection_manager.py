"""Qdrant collection manager for per-scan and per-workspace vector collections.

Naming conventions
------------------
- Scan collection:      ``sf_scan_{scan_id}``
- Workspace collection: ``sf_workspace_{workspace_id}``
- Global collection:    ``sf_global``

Each scan gets its own collection at scan start.  When a workspace-level
correlation is requested the manager either:
  (a) creates a workspace meta-collection by copying vectors from all
      constituent scan collections, or
  (b) performs a federated search across all scan collections in the workspace.

The manager is designed to be used both from the scan pipeline (index events
during scanning) and from the RAG correlation API endpoints (query/search).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from spiderfoot.qdrant_client import (
    QdrantClient, QdrantConfig, DistanceMetric,
    VectorPoint, Filter, create_vector_store,
)

log = logging.getLogger("spiderfoot.correlations.vector_collection_manager")

# Default vector dimensions for all-MiniLM-L6-v2
DEFAULT_DIMENSIONS = 384


@dataclass
class CollectionManagerConfig:
    """Configuration for the vector collection manager."""

    dimensions: int = DEFAULT_DIMENSIONS
    distance: DistanceMetric = DistanceMetric.COSINE
    # Whether to auto-create workspace meta-collections (copy vectors)
    # vs. federated search across scan collections
    workspace_strategy: str = "federated"  # "federated" | "materialized"
    # Batch size for copying vectors into materialized workspace collections
    materialize_batch_size: int = 500
    # Global collection for cross-workspace queries
    enable_global: bool = False

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> CollectionManagerConfig:
        """Build from environment variables."""
        import os
        e = env or os.environ
        return cls(
            dimensions=int(e.get("SF_EMBEDDING_DIMENSIONS", str(DEFAULT_DIMENSIONS))),
            workspace_strategy=e.get("SF_VECTOR_WORKSPACE_STRATEGY", "federated"),
            enable_global=e.get("SF_VECTOR_GLOBAL_COLLECTION", "").lower()
            in ("1", "true", "yes"),
        )


class VectorCollectionManager:
    """Manages Qdrant collections for scans, workspaces, and global scope."""

    def __init__(
        self,
        qdrant: QdrantClient | None = None,
        config: CollectionManagerConfig | None = None,
    ) -> None:
        self._config = config or CollectionManagerConfig.from_env()
        if qdrant is not None:
            self._qdrant = qdrant
        else:
            self._qdrant = QdrantClient(QdrantConfig.from_env())
        log.info(
            "VectorCollectionManager: dims=%d, strategy=%s",
            self._config.dimensions,
            self._config.workspace_strategy,
        )

    # ------------------------------------------------------------------
    # Naming helpers
    # ------------------------------------------------------------------

    def scan_collection_name(self, scan_id: str) -> str:
        """Return the Qdrant collection name for a scan."""
        return f"scan_{scan_id}"

    def workspace_collection_name(self, workspace_id: str) -> str:
        """Return the Qdrant collection name for a workspace."""
        return f"workspace_{workspace_id}"

    def global_collection_name(self) -> str:
        """Return the global collection name."""
        return "global"

    # ------------------------------------------------------------------
    # Lifecycle — scan collections
    # ------------------------------------------------------------------

    def create_scan_collection(self, scan_id: str) -> str:
        """Create a Qdrant collection for a new scan.

        Returns:
            The full collection name (with prefix).
        """
        name = self.scan_collection_name(scan_id)
        self._qdrant.ensure_collection(
            name,
            vector_size=self._config.dimensions,
            distance=self._config.distance,
        )
        log.info("Created scan collection: %s", name)
        return name

    def delete_scan_collection(self, scan_id: str) -> bool:
        """Delete a scan collection when no longer needed."""
        name = self.scan_collection_name(scan_id)
        try:
            self._qdrant.delete_collection(name)
            log.info("Deleted scan collection: %s", name)
            return True
        except Exception as exc:
            log.warning("Failed to delete scan collection %s: %s", name, exc)
            return False

    def scan_collection_exists(self, scan_id: str) -> bool:
        """Check if a scan collection exists."""
        return self._qdrant.collection_exists(self.scan_collection_name(scan_id))

    # ------------------------------------------------------------------
    # Indexing — scan events
    # ------------------------------------------------------------------

    def index_events(
        self,
        scan_id: str,
        points: list[VectorPoint],
    ) -> int:
        """Upsert vector points into a scan collection.

        Creates the collection if it does not exist yet.

        Args:
            scan_id: Target scan.
            points: Embedded event vectors.

        Returns:
            Number of points indexed.
        """
        if not points:
            return 0
        name = self.scan_collection_name(scan_id)
        if not self._qdrant.collection_exists(name):
            self.create_scan_collection(scan_id)
        self._qdrant.upsert(name, points)
        return len(points)

    # ------------------------------------------------------------------
    # Lifecycle — workspace meta-collections
    # ------------------------------------------------------------------

    def create_workspace_collection(
        self,
        workspace_id: str,
        scan_ids: list[str],
    ) -> str:
        """Create or refresh a workspace meta-collection.

        For ``materialized`` strategy this copies vectors from all scan
        collections into a single workspace collection.  For ``federated``
        strategy this only records the scan_ids (no data copy) — queries
        fan out to each scan collection at query time.

        Returns:
            The workspace collection name.
        """
        ws_name = self.workspace_collection_name(workspace_id)

        if self._config.workspace_strategy == "materialized":
            self._materialize_workspace(ws_name, scan_ids)
        else:
            # Federated: ensure the workspace collection exists but empty
            # (used for metadata / bookkeeping)
            self._qdrant.ensure_collection(
                ws_name,
                vector_size=self._config.dimensions,
                distance=self._config.distance,
            )
            # Store the scan list as a metadata point
            self._qdrant.upsert(ws_name, [
                VectorPoint(
                    id="__workspace_meta__",
                    vector=[0.0] * self._config.dimensions,
                    payload={
                        "type": "workspace_meta",
                        "workspace_id": workspace_id,
                        "scan_ids": scan_ids,
                        "updated_at": time.time(),
                    },
                ),
            ])
        log.info(
            "Workspace collection %s ready (%s, %d scans)",
            ws_name,
            self._config.workspace_strategy,
            len(scan_ids),
        )
        return ws_name

    def delete_workspace_collection(self, workspace_id: str) -> bool:
        """Delete a workspace collection."""
        ws_name = self.workspace_collection_name(workspace_id)
        try:
            self._qdrant.delete_collection(ws_name)
            log.info("Deleted workspace collection: %s", ws_name)
            return True
        except Exception as exc:
            log.warning("Failed to delete workspace collection %s: %s", ws_name, exc)
            return False

    # ------------------------------------------------------------------
    # Search — scan scope
    # ------------------------------------------------------------------

    def search_scan(
        self,
        scan_id: str,
        query_vector: list[float],
        top_k: int = 20,
        score_threshold: float = 0.0,
        filter_payload: dict[str, Any] | None = None,
    ) -> list[VectorPoint]:
        """Search within a single scan collection."""
        name = self.scan_collection_name(scan_id)
        if not self._qdrant.collection_exists(name):
            return []
        filt = None
        if filter_payload:
            must_conditions = [
                Filter.match(k, v) for k, v in filter_payload.items()
            ]
            filt = Filter(must=must_conditions)
        result = self._qdrant.search(
            name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            filter_=filt,
        )
        return result.points

    # ------------------------------------------------------------------
    # Search — workspace scope (federated)
    # ------------------------------------------------------------------

    def search_workspace(
        self,
        workspace_id: str,
        scan_ids: list[str],
        query_vector: list[float],
        top_k: int = 20,
        score_threshold: float = 0.0,
        filter_payload: dict[str, Any] | None = None,
    ) -> list[VectorPoint]:
        """Search across all scans in a workspace.

        For ``federated`` strategy, queries each scan collection and merges
        results (top_k globally by score).  For ``materialized`` strategy,
        searches the single workspace collection.
        """
        ws_name = self.workspace_collection_name(workspace_id)

        if self._config.workspace_strategy == "materialized":
            if not self._qdrant.collection_exists(ws_name):
                return []
            filt = None
            if filter_payload:
                must_conditions = [
                    Filter.match(k, v) for k, v in filter_payload.items()
                ]
                filt = Filter(must=must_conditions)
            result = self._qdrant.search(
                ws_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                filter_=filt,
            )
            return result.points

        # Federated: query each scan collection, merge results
        all_hits: list[VectorPoint] = []
        for sid in scan_ids:
            hits = self.search_scan(
                sid, query_vector, top_k=top_k,
                score_threshold=score_threshold,
                filter_payload=filter_payload,
            )
            all_hits.extend(hits)

        # Sort by score descending, keep top_k
        all_hits.sort(key=lambda p: (p.score or 0.0), reverse=True)
        return all_hits[:top_k]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def collection_stats(self, scan_id: str | None = None,
                         workspace_id: str | None = None) -> dict[str, Any]:
        """Return stats for a scan, workspace, or all collections."""
        if scan_id:
            name = self.scan_collection_name(scan_id)
        elif workspace_id:
            name = self.workspace_collection_name(workspace_id)
        else:
            # List all SF collections
            try:
                all_cols = self._qdrant.list_collections()
                return {
                    "total_collections": len(all_cols),
                    "collections": [
                        {"name": c, "info": self._safe_info(c)}
                        for c in all_cols
                    ],
                }
            except Exception as exc:
                return {"error": str(exc)}

        if not self._qdrant.collection_exists(name):
            return {"exists": False, "collection": name}
        info = self._qdrant.collection_info(name)
        return {
            "exists": True,
            "collection": name,
            "vector_count": info.point_count if info else 0,
            "vector_size": info.vector_size if info else 0,
            "distance": info.distance.value if info else "",
        }

    def _safe_info(self, name: str) -> dict[str, Any]:
        """Get collection info, returning error dict on failure."""
        try:
            info = self._qdrant.collection_info(name)
            return {
                "point_count": info.point_count if info else 0,
                "vector_size": info.vector_size if info else 0,
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Internal — materialized workspace
    # ------------------------------------------------------------------

    def _materialize_workspace(
        self, ws_name: str, scan_ids: list[str]
    ) -> None:
        """Copy vectors from scan collections into a workspace collection."""
        # Re-create workspace collection fresh
        try:
            self._qdrant.delete_collection(ws_name)
        except Exception:
            pass
        self._qdrant.ensure_collection(
            ws_name,
            vector_size=self._config.dimensions,
            distance=self._config.distance,
        )

        total = 0
        for sid in scan_ids:
            src_name = self.scan_collection_name(sid)
            if not self._qdrant.collection_exists(src_name):
                log.debug("Scan collection %s does not exist, skipping", src_name)
                continue

            # Scroll all points from the scan collection
            offset = None
            while True:
                points, next_offset = self._qdrant.scroll(
                    src_name,
                    limit=self._config.materialize_batch_size,
                    offset=offset,
                )
                if not points:
                    break

                # Tag each point with its source scan_id
                for p in points:
                    if p.payload is None:
                        p.payload = {}
                    p.payload["source_scan_id"] = sid
                    # Namespace the ID to avoid collisions across scans
                    p.id = f"{sid}_{p.id}"

                self._qdrant.upsert(ws_name, points)
                total += len(points)

                if next_offset is None:
                    break
                offset = next_offset

        log.info(
            "Materialized workspace %s: %d vectors from %d scans",
            ws_name, total, len(scan_ids),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_manager: VectorCollectionManager | None = None


def get_collection_manager() -> VectorCollectionManager:
    """Return the singleton VectorCollectionManager."""
    global _manager
    if _manager is None:
        _manager = VectorCollectionManager()
    return _manager
