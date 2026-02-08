"""Qdrant vector store client — abstraction for vector similarity search.

Provides a clean Python interface to `Qdrant <https://qdrant.tech/>`_
for storing, indexing, and querying dense vector embeddings.

Features:

* **Collection management** — create, delete, and list collections
  with configurable distance metrics and HNSW parameters.
* **Point CRUD** — upsert, get, delete, and search vectors with
  payload filtering.
* **Batch operations** — efficient bulk upsert with configurable
  batch sizes.
* **Multiple backends** — in-memory (testing), HTTP REST (production),
  and gRPC (high-throughput).
* **Payload filtering** — Qdrant filter conditions for metadata queries.
* **Scroll / pagination** — iterate over large collections.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

log = logging.getLogger("spiderfoot.qdrant")


# ---------------------------------------------------------------------------
# Enums & config
# ---------------------------------------------------------------------------

class DistanceMetric(Enum):
    COSINE = "Cosine"
    EUCLID = "Euclid"
    DOT = "Dot"


class QdrantBackend(Enum):
    MEMORY = "memory"      # in-process dict (testing)
    HTTP = "http"          # REST API
    GRPC = "grpc"          # gRPC


@dataclass
class QdrantConfig:
    """Connection configuration for Qdrant."""

    backend: QdrantBackend = QdrantBackend.MEMORY
    host: str = "localhost"
    port: int = 6333
    grpc_port: int = 6334
    api_key: str = ""
    https: bool = False
    timeout: float = 30.0
    collection_prefix: str = "sf_"

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "QdrantConfig":
        import os
        e = env or os.environ
        return cls(
            backend=QdrantBackend(e.get("SF_QDRANT_BACKEND", "memory")),
            host=e.get("SF_QDRANT_HOST", "localhost"),
            port=int(e.get("SF_QDRANT_PORT", "6333")),
            grpc_port=int(e.get("SF_QDRANT_GRPC_PORT", "6334")),
            api_key=e.get("SF_QDRANT_API_KEY", ""),
            https=e.get("SF_QDRANT_HTTPS", "").lower() in ("1", "true", "yes"),
            timeout=float(e.get("SF_QDRANT_TIMEOUT", "30")),
            collection_prefix=e.get("SF_QDRANT_PREFIX", "sf_"),
        )


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class VectorPoint:
    """A single point in a vector collection."""

    id: str
    vector: List[float]
    payload: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0  # populated on search results

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "vector": self.vector,
            "payload": self.payload,
            "score": self.score,
        }


@dataclass
class CollectionInfo:
    """Metadata about a vector collection."""

    name: str
    vector_size: int
    distance: DistanceMetric
    point_count: int = 0
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "vector_size": self.vector_size,
            "distance": self.distance.value,
            "point_count": self.point_count,
        }


@dataclass
class SearchResult:
    """Result of a vector similarity search."""

    points: List[VectorPoint]
    query_time_ms: float = 0.0
    total_found: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "points": [p.to_dict() for p in self.points],
            "query_time_ms": round(self.query_time_ms, 2),
            "total_found": self.total_found,
        }


@dataclass
class Filter:
    """Simple payload filter for Qdrant queries."""

    must: List[Dict[str, Any]] = field(default_factory=list)
    must_not: List[Dict[str, Any]] = field(default_factory=list)
    should: List[Dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def match(key: str, value: Any) -> Dict[str, Any]:
        return {"key": key, "match": {"value": value}}

    @staticmethod
    def range(key: str, gte: Optional[float] = None, lte: Optional[float] = None) -> Dict[str, Any]:
        r: Dict[str, Any] = {"key": key, "range": {}}
        if gte is not None:
            r["range"]["gte"] = gte
        if lte is not None:
            r["range"]["lte"] = lte
        return r

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.must:
            d["must"] = self.must
        if self.must_not:
            d["must_not"] = self.must_not
        if self.should:
            d["should"] = self.should
        return d

    @property
    def is_empty(self) -> bool:
        return not self.must and not self.must_not and not self.should


# ---------------------------------------------------------------------------
# Backend ABC
# ---------------------------------------------------------------------------

class VectorStoreBackend:
    """Abstract base for vector store backends."""

    def create_collection(self, name: str, vector_size: int,
                          distance: DistanceMetric = DistanceMetric.COSINE) -> bool:
        raise NotImplementedError

    def delete_collection(self, name: str) -> bool:
        raise NotImplementedError

    def collection_exists(self, name: str) -> bool:
        raise NotImplementedError

    def collection_info(self, name: str) -> Optional[CollectionInfo]:
        raise NotImplementedError

    def list_collections(self) -> List[str]:
        raise NotImplementedError

    def upsert(self, collection: str, points: List[VectorPoint]) -> int:
        raise NotImplementedError

    def get(self, collection: str, ids: List[str]) -> List[VectorPoint]:
        raise NotImplementedError

    def delete(self, collection: str, ids: List[str]) -> int:
        raise NotImplementedError

    def search(self, collection: str, query_vector: List[float],
               limit: int = 10, score_threshold: float = 0.0,
               filter_: Optional[Filter] = None) -> SearchResult:
        raise NotImplementedError

    def scroll(self, collection: str, limit: int = 100,
               offset: Optional[str] = None,
               filter_: Optional[Filter] = None) -> Tuple[List[VectorPoint], Optional[str]]:
        raise NotImplementedError

    def count(self, collection: str) -> int:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# In-memory backend (testing / development)
# ---------------------------------------------------------------------------

def _cosine_sim(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _euclid_dist(a: List[float], b: List[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _dot_product(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _matches_filter(payload: Dict[str, Any], filter_: Filter) -> bool:
    """Evaluate a simple filter against a payload."""
    def _check_condition(cond: Dict[str, Any]) -> bool:
        key = cond.get("key", "")
        if "match" in cond:
            return payload.get(key) == cond["match"].get("value")
        if "range" in cond:
            val = payload.get(key)
            if val is None:
                return False
            r = cond["range"]
            if "gte" in r and val < r["gte"]:
                return False
            if "lte" in r and val > r["lte"]:
                return False
            return True
        return True

    for c in filter_.must:
        if not _check_condition(c):
            return False
    for c in filter_.must_not:
        if _check_condition(c):
            return False
    if filter_.should:
        if not any(_check_condition(c) for c in filter_.should):
            return False
    return True


class MemoryVectorBackend(VectorStoreBackend):
    """In-memory vector store for testing."""

    def __init__(self) -> None:
        self._collections: Dict[str, CollectionInfo] = {}
        self._points: Dict[str, Dict[str, VectorPoint]] = {}
        self._lock = threading.Lock()

    def create_collection(self, name: str, vector_size: int,
                          distance: DistanceMetric = DistanceMetric.COSINE) -> bool:
        with self._lock:
            if name in self._collections:
                return False
            self._collections[name] = CollectionInfo(
                name=name, vector_size=vector_size,
                distance=distance, created_at=time.time(),
            )
            self._points[name] = {}
            return True

    def delete_collection(self, name: str) -> bool:
        with self._lock:
            if name not in self._collections:
                return False
            del self._collections[name]
            del self._points[name]
            return True

    def collection_exists(self, name: str) -> bool:
        return name in self._collections

    def collection_info(self, name: str) -> Optional[CollectionInfo]:
        with self._lock:
            info = self._collections.get(name)
            if info:
                info.point_count = len(self._points.get(name, {}))
            return info

    def list_collections(self) -> List[str]:
        return list(self._collections.keys())

    def upsert(self, collection: str, points: List[VectorPoint]) -> int:
        with self._lock:
            store = self._points.get(collection)
            if store is None:
                return 0
            for p in points:
                if not p.id:
                    p.id = str(uuid.uuid4())
                store[p.id] = VectorPoint(
                    id=p.id, vector=list(p.vector),
                    payload=dict(p.payload),
                )
            return len(points)

    def get(self, collection: str, ids: List[str]) -> List[VectorPoint]:
        with self._lock:
            store = self._points.get(collection, {})
            return [store[i] for i in ids if i in store]

    def delete(self, collection: str, ids: List[str]) -> int:
        with self._lock:
            store = self._points.get(collection, {})
            deleted = 0
            for i in ids:
                if i in store:
                    del store[i]
                    deleted += 1
            return deleted

    def search(self, collection: str, query_vector: List[float],
               limit: int = 10, score_threshold: float = 0.0,
               filter_: Optional[Filter] = None) -> SearchResult:
        start = time.time()
        with self._lock:
            store = self._points.get(collection, {})
            info = self._collections.get(collection)
            if not info:
                return SearchResult(points=[], query_time_ms=0, total_found=0)

            dist = info.distance
            scored: List[Tuple[float, VectorPoint]] = []

            for p in store.values():
                if filter_ and not _matches_filter(p.payload, filter_):
                    continue

                if dist == DistanceMetric.COSINE:
                    score = _cosine_sim(query_vector, p.vector)
                elif dist == DistanceMetric.DOT:
                    score = _dot_product(query_vector, p.vector)
                else:
                    score = -_euclid_dist(query_vector, p.vector)

                if score >= score_threshold:
                    scored.append((score, p))

        # Sort descending
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, p in scored[:limit]:
            results.append(VectorPoint(
                id=p.id, vector=p.vector,
                payload=p.payload, score=score,
            ))

        elapsed = (time.time() - start) * 1000
        return SearchResult(
            points=results,
            query_time_ms=elapsed,
            total_found=len(scored),
        )

    def scroll(self, collection: str, limit: int = 100,
               offset: Optional[str] = None,
               filter_: Optional[Filter] = None) -> Tuple[List[VectorPoint], Optional[str]]:
        with self._lock:
            store = self._points.get(collection, {})
            all_ids = sorted(store.keys())

        start_idx = 0
        if offset:
            try:
                start_idx = all_ids.index(offset) + 1
            except ValueError:
                start_idx = 0

        result: List[VectorPoint] = []
        for pid in all_ids[start_idx:]:
            p = store.get(pid)
            if p and (not filter_ or _matches_filter(p.payload, filter_)):
                result.append(p)
                if len(result) >= limit:
                    break

        next_offset = result[-1].id if len(result) == limit else None
        return result, next_offset

    def count(self, collection: str) -> int:
        return len(self._points.get(collection, {}))


# ---------------------------------------------------------------------------
# HTTP backend (production Qdrant REST API)
# ---------------------------------------------------------------------------

class HttpVectorBackend(VectorStoreBackend):
    """Qdrant REST API backend."""

    def __init__(self, config: QdrantConfig) -> None:
        self._config = config
        scheme = "https" if config.https else "http"
        self._base = f"{scheme}://{config.host}:{config.port}"
        self._headers: Dict[str, str] = {"Content-Type": "application/json"}
        if config.api_key:
            self._headers["api-key"] = config.api_key

    def _request(self, method: str, path: str,
                 body: Optional[Dict] = None) -> Dict[str, Any]:
        import urllib.request
        url = f"{self._base}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=self._headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._config.timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            log.error("Qdrant HTTP %s %s failed: %s", method, path, e)
            return {"status": "error", "error": str(e)}

    def create_collection(self, name: str, vector_size: int,
                          distance: DistanceMetric = DistanceMetric.COSINE) -> bool:
        body = {
            "vectors": {
                "size": vector_size,
                "distance": distance.value,
            }
        }
        resp = self._request("PUT", f"/collections/{name}", body)
        return resp.get("result") is True or resp.get("status") == "ok"

    def delete_collection(self, name: str) -> bool:
        resp = self._request("DELETE", f"/collections/{name}")
        return resp.get("result") is True or resp.get("status") == "ok"

    def collection_exists(self, name: str) -> bool:
        resp = self._request("GET", f"/collections/{name}")
        return "result" in resp and "error" not in resp

    def collection_info(self, name: str) -> Optional[CollectionInfo]:
        resp = self._request("GET", f"/collections/{name}")
        result = resp.get("result")
        if not result:
            return None
        cfg = result.get("config", {}).get("params", {}).get("vectors", {})
        return CollectionInfo(
            name=name,
            vector_size=cfg.get("size", 0),
            distance=DistanceMetric(cfg.get("distance", "Cosine")),
            point_count=result.get("points_count", 0),
        )

    def list_collections(self) -> List[str]:
        resp = self._request("GET", "/collections")
        collections = resp.get("result", {}).get("collections", [])
        return [c.get("name", "") for c in collections]

    def upsert(self, collection: str, points: List[VectorPoint]) -> int:
        body = {
            "points": [
                {"id": p.id, "vector": p.vector, "payload": p.payload}
                for p in points
            ]
        }
        resp = self._request("PUT", f"/collections/{collection}/points", body)
        return len(points) if resp.get("status") == "ok" else 0

    def get(self, collection: str, ids: List[str]) -> List[VectorPoint]:
        body = {"ids": ids, "with_vector": True, "with_payload": True}
        resp = self._request("POST", f"/collections/{collection}/points", body)
        result = resp.get("result", [])
        return [
            VectorPoint(id=str(r["id"]), vector=r.get("vector", []),
                        payload=r.get("payload", {}))
            for r in result
        ]

    def delete(self, collection: str, ids: List[str]) -> int:
        body = {"points": ids}
        resp = self._request("POST", f"/collections/{collection}/points/delete", body)
        return len(ids) if resp.get("status") == "ok" else 0

    def search(self, collection: str, query_vector: List[float],
               limit: int = 10, score_threshold: float = 0.0,
               filter_: Optional[Filter] = None) -> SearchResult:
        start = time.time()
        body: Dict[str, Any] = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": True,
        }
        if score_threshold > 0:
            body["score_threshold"] = score_threshold
        if filter_ and not filter_.is_empty:
            body["filter"] = filter_.to_dict()

        resp = self._request("POST", f"/collections/{collection}/points/search", body)
        elapsed = (time.time() - start) * 1000
        result = resp.get("result", [])
        points = [
            VectorPoint(
                id=str(r["id"]), vector=r.get("vector", []),
                payload=r.get("payload", {}), score=r.get("score", 0.0),
            )
            for r in result
        ]
        return SearchResult(points=points, query_time_ms=elapsed,
                            total_found=len(points))

    def scroll(self, collection: str, limit: int = 100,
               offset: Optional[str] = None,
               filter_: Optional[Filter] = None) -> Tuple[List[VectorPoint], Optional[str]]:
        body: Dict[str, Any] = {
            "limit": limit,
            "with_payload": True,
            "with_vector": True,
        }
        if offset:
            body["offset"] = offset
        if filter_ and not filter_.is_empty:
            body["filter"] = filter_.to_dict()

        resp = self._request("POST", f"/collections/{collection}/points/scroll", body)
        result = resp.get("result", {})
        points = [
            VectorPoint(id=str(r["id"]), vector=r.get("vector", []),
                        payload=r.get("payload", {}))
            for r in result.get("points", [])
        ]
        next_offset = result.get("next_page_offset")
        return points, str(next_offset) if next_offset else None

    def count(self, collection: str) -> int:
        resp = self._request("POST", f"/collections/{collection}/points/count",
                             {"exact": True})
        return resp.get("result", {}).get("count", 0)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_vector_store(config: Optional[QdrantConfig] = None) -> VectorStoreBackend:
    """Create a vector store backend from config."""
    if config is None:
        config = QdrantConfig()

    if config.backend == QdrantBackend.MEMORY:
        return MemoryVectorBackend()
    elif config.backend == QdrantBackend.HTTP:
        return HttpVectorBackend(config)
    elif config.backend == QdrantBackend.GRPC:
        # gRPC backend would require qdrant-client package
        # Fall back to HTTP for now
        log.warning("gRPC backend not yet implemented, falling back to HTTP")
        return HttpVectorBackend(config)
    else:
        return MemoryVectorBackend()


# ---------------------------------------------------------------------------
# High-level client
# ---------------------------------------------------------------------------

class QdrantClient:
    """High-level Qdrant vector store client.

    Usage::

        client = QdrantClient()
        client.ensure_collection("events", vector_size=384)
        client.upsert("events", [
            VectorPoint(id="1", vector=[0.1, 0.2, ...], payload={"type": "IP"})
        ])
        results = client.search("events", query_vector=[0.1, 0.2, ...], limit=5)
    """

    def __init__(self, config: Optional[QdrantConfig] = None) -> None:
        self._config = config or QdrantConfig()
        self._backend = create_vector_store(self._config)
        self._prefix = self._config.collection_prefix

    def _cname(self, name: str) -> str:
        """Apply collection prefix."""
        if name.startswith(self._prefix):
            return name
        return f"{self._prefix}{name}"

    # Collections
    def ensure_collection(self, name: str, vector_size: int,
                          distance: DistanceMetric = DistanceMetric.COSINE) -> bool:
        cname = self._cname(name)
        if self._backend.collection_exists(cname):
            return True
        return self._backend.create_collection(cname, vector_size, distance)

    def delete_collection(self, name: str) -> bool:
        return self._backend.delete_collection(self._cname(name))

    def list_collections(self) -> List[str]:
        return [c for c in self._backend.list_collections()
                if c.startswith(self._prefix)]

    def collection_info(self, name: str) -> Optional[CollectionInfo]:
        return self._backend.collection_info(self._cname(name))

    # Points
    def upsert(self, collection: str, points: List[VectorPoint],
               batch_size: int = 100) -> int:
        cname = self._cname(collection)
        total = 0
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            total += self._backend.upsert(cname, batch)
        return total

    def get(self, collection: str, ids: List[str]) -> List[VectorPoint]:
        return self._backend.get(self._cname(collection), ids)

    def delete(self, collection: str, ids: List[str]) -> int:
        return self._backend.delete(self._cname(collection), ids)

    # Search
    def search(self, collection: str, query_vector: List[float],
               limit: int = 10, score_threshold: float = 0.0,
               filter_: Optional[Filter] = None) -> SearchResult:
        return self._backend.search(
            self._cname(collection), query_vector, limit,
            score_threshold, filter_,
        )

    # Scroll
    def scroll(self, collection: str, limit: int = 100,
               offset: Optional[str] = None,
               filter_: Optional[Filter] = None) -> Tuple[List[VectorPoint], Optional[str]]:
        return self._backend.scroll(self._cname(collection), limit, offset, filter_)

    def count(self, collection: str) -> int:
        return self._backend.count(self._cname(collection))

    # Stats
    def stats(self) -> Dict[str, Any]:
        collections = self.list_collections()
        total_points = 0
        for c in collections:
            total_points += self._backend.count(c)
        return {
            "backend": self._config.backend.value,
            "host": self._config.host,
            "port": self._config.port,
            "collections": len(collections),
            "total_points": total_points,
            "prefix": self._prefix,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[QdrantClient] = None
_instance_lock = threading.Lock()


def get_qdrant_client(**kwargs: Any) -> QdrantClient:
    """Return the global QdrantClient singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                config = QdrantConfig(**kwargs) if kwargs else QdrantConfig.from_env()
                _instance = QdrantClient(config)
    return _instance
