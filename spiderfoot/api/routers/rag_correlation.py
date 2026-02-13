"""RAG-powered vector correlation API endpoints.

Exposes the Qdrant vector correlation engine and multi-dimensional
analyzer through REST endpoints for on-demand OSINT correlation
queries, event indexing, and cross-scan discovery.

Endpoints
---------
POST /rag/index        — index OSINT events into vector store
POST /rag/correlate    — run vector correlation query
POST /rag/multidim     — run multi-dimensional analysis
GET  /rag/stats        — engine statistics
DELETE /rag/collection — reset vector collection
POST /rag/search       — raw semantic search
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..dependencies import optional_auth

log = logging.getLogger("spiderfoot.api.rag_correlation")

router = APIRouter()
optional_auth_dep = Depends(optional_auth)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class EventPayload(BaseModel):
    """Single OSINT event for indexing or analysis."""

    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="SpiderFoot event type")
    data: str = Field(..., description="Event data value")
    scan_id: str = Field("", description="Scan that produced the event")
    timestamp: float = Field(0.0, description="Unix epoch timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexRequest(BaseModel):
    """Batch event indexing request."""

    events: list[EventPayload] = Field(..., min_length=1,
                                       description="Events to index")
    collection: str = Field("osint_events",
                            description="Target Qdrant collection")


class IndexResponse(BaseModel):
    """Result of indexing operation."""

    indexed: int
    collection: str
    elapsed_ms: float


class CorrelateRequest(BaseModel):
    """Vector correlation query."""

    query: str = Field(..., description="Natural language query or event data")
    strategy: str = Field("similarity",
                          description="Correlation strategy: similarity, "
                                      "cross_scan, multi_hop, infrastructure")
    scan_id: str | None = Field(None, description="Restrict to scan")
    top_k: int = Field(20, ge=1, le=200, description="Max results")
    threshold: float = Field(0.5, ge=0.0, le=1.0,
                             description="Minimum similarity threshold")
    use_reranker: bool = Field(True, description="Apply cross-encoder reranking")
    use_rag: bool = Field(True, description="Generate RAG analysis")


class CorrelationHitResponse(BaseModel):
    """Single correlation hit in response."""

    event_id: str
    event_type: str
    data: str
    scan_id: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorrelateResponse(BaseModel):
    """Vector correlation result."""

    query: str
    strategy: str
    total_hits: int
    hits: list[CorrelationHitResponse]
    analysis: str | None = None
    confidence: float = 0.0
    risk_level: str = "INFO"
    elapsed_ms: float = 0.0


class MultiDimRequest(BaseModel):
    """Multi-dimensional correlation request."""

    query: str = Field(..., description="Correlation query context")
    events: list[EventPayload] = Field(..., min_length=1,
                                       description="Events to analyze")
    dimensions: list[str] | None = Field(
        None, description="Dimensions to evaluate: entity, temporal, "
                          "network, identity, behavioral, geographic")
    fusion_method: str = Field("weighted",
                               description="Score fusion: weighted, max, "
                                           "harmonic")
    min_score: float = Field(0.3, ge=0.0, le=1.0,
                             description="Minimum fused score threshold")


class DimensionScoreResponse(BaseModel):
    """Dimension score in multi-dim result."""

    dimension: str
    score: float
    evidence_count: int = 0
    details: str = ""


class PairResponse(BaseModel):
    """Correlated event pair."""

    event_a_id: str
    event_b_id: str
    fused_score: float
    dimensions: list[DimensionScoreResponse]


class MultiDimResponse(BaseModel):
    """Multi-dimensional analysis result."""

    query: str
    total_events: int
    total_pairs: int
    total_clusters: int
    pairs: list[PairResponse]
    clusters: list[list[str]]
    dimension_summary: dict[str, float]
    elapsed_ms: float


class SearchRequest(BaseModel):
    """Raw semantic search request."""

    query: str = Field(..., description="Text to embed and search")
    top_k: int = Field(10, ge=1, le=200)
    scan_id: str | None = None
    event_type: str | None = None


class SearchHitResponse(BaseModel):
    """Semantic search hit."""

    event_id: str
    score: float
    payload: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Semantic search result."""

    query: str
    total: int
    hits: list[SearchHitResponse]
    elapsed_ms: float


class StatsResponse(BaseModel):
    """Engine statistics."""

    qdrant_available: bool
    embedding_available: bool
    collection: str
    total_vectors: int
    dimensions: int
    stats: dict[str, Any] = Field(default_factory=dict)


class CollectionInfoResponse(BaseModel):
    """Information about a single Qdrant collection."""

    name: str
    total_vectors: int = 0
    dimensions: int = 0
    scope: str = "unknown"  # scan, workspace, global
    scan_id: str | None = None
    workspace_id: str | None = None


class CollectionListResponse(BaseModel):
    """List of managed Qdrant collections."""

    collections: list[CollectionInfoResponse]
    total: int


class WorkspaceCollectionRequest(BaseModel):
    """Request to create or refresh a workspace meta-collection."""

    workspace_id: str = Field(..., description="Workspace ID")
    scan_ids: list[str] = Field(..., min_length=1,
                                description="Scan IDs to include")
    strategy: str | None = Field(
        None, description="Strategy: 'federated' or 'materialized'. "
                          "Uses server default if not set.")


class WorkspaceSearchRequest(BaseModel):
    """Search across all scans in a workspace."""

    workspace_id: str = Field(..., description="Workspace ID")
    query: str = Field(..., description="Text to embed and search")
    top_k: int = Field(10, ge=1, le=200)
    event_type: str | None = None


# ---------------------------------------------------------------------------
# Lazy engine singletons
# ---------------------------------------------------------------------------

_vector_engine = None
_multidim_analyzer = None


def _get_vector_engine():
    """Lazy-initialise VectorCorrelationEngine."""
    global _vector_engine
    if _vector_engine is None:
        try:
            from spiderfoot.vector_correlation import VectorCorrelationEngine
            _vector_engine = VectorCorrelationEngine()
            log.info("Vector correlation engine initialised")
        except Exception as exc:
            log.error("Failed to init vector engine: %s", exc)
            raise HTTPException(status_code=503,
                                detail=f"Vector engine unavailable: {exc}")
    return _vector_engine


def _get_multidim():
    """Lazy-initialise MultiDimAnalyzer."""
    global _multidim_analyzer
    if _multidim_analyzer is None:
        try:
            from spiderfoot.multidim_correlation import MultiDimAnalyzer
            _multidim_analyzer = MultiDimAnalyzer()
            log.info("Multi-dimensional analyzer initialised")
        except Exception as exc:
            log.error("Failed to init multidim analyzer: %s", exc)
            raise HTTPException(status_code=503,
                                detail=f"Multi-dim analyzer unavailable: {exc}")
    return _multidim_analyzer


_collection_mgr = None


def _get_collection_manager():
    """Lazy-initialise VectorCollectionManager."""
    global _collection_mgr
    if _collection_mgr is None:
        try:
            from spiderfoot.correlations.vector_collection_manager import (
                get_collection_manager,
            )
            _collection_mgr = get_collection_manager()
            log.info("Collection manager initialised")
        except Exception as exc:
            log.error("Failed to init collection manager: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=f"Collection manager unavailable: {exc}",
            )
    return _collection_mgr


def _get_workspace_scan_ids(workspace_id: str) -> list[str]:
    """Retrieve scan IDs belonging to a workspace from the database."""
    try:
        from spiderfoot.db import SpiderFootDb
        dbh = SpiderFootDb(SpiderFootDb.build_config_from_env())
        rows = dbh.scanInstanceList(workspace_id=workspace_id)
        dbh.close()
        return [row[0] for row in rows] if rows else []
    except Exception as e:
        log.warning("Failed to get workspace scan IDs for %s: %s",
                    workspace_id, e)
        return []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/rag/index", response_model=IndexResponse,
             summary="Index OSINT events into vector store")
async def index_events(req: IndexRequest,
                       _auth: str = optional_auth_dep) -> IndexResponse:
    """Embed and store OSINT events as vectors in Qdrant."""
    engine = _get_vector_engine()
    t0 = time.perf_counter()

    from spiderfoot.vector_correlation import OSINTEvent
    osint_events = [
        OSINTEvent(
            event_id=e.event_id,
            event_type=e.event_type,
            data=e.data,
            source_module=e.metadata.get("source_module", "api"),
            scan_id=e.scan_id,
            timestamp=e.timestamp,
            extra=e.metadata,
        )
        for e in req.events
    ]

    try:
        engine.index_events(osint_events)
    except Exception as exc:
        log.error("Indexing failed: %s", exc)
        raise HTTPException(status_code=500,
                            detail=f"Indexing failed: {exc}")

    elapsed = (time.perf_counter() - t0) * 1000
    return IndexResponse(
        indexed=len(osint_events),
        collection=req.collection,
        elapsed_ms=round(elapsed, 2),
    )


@router.post("/rag/correlate", response_model=CorrelateResponse,
             summary="Run vector correlation query")
async def correlate(req: CorrelateRequest,
                    _auth: str = optional_auth_dep) -> CorrelateResponse:
    """Execute a correlation query using the chosen strategy."""
    engine = _get_vector_engine()
    t0 = time.perf_counter()

    from spiderfoot.vector_correlation import CorrelationStrategy
    try:
        strategy = CorrelationStrategy(req.strategy)
    except ValueError:
        raise HTTPException(status_code=400,
                            detail=f"Unknown strategy: {req.strategy}")

    try:
        result = engine.correlate(
            query=req.query,
            strategy=strategy,
            scan_id=req.scan_id,
            event_type=None,
        )
    except Exception as exc:
        log.error("Correlation failed: %s", exc)
        raise HTTPException(status_code=500,
                            detail=f"Correlation failed: {exc}")

    elapsed = (time.perf_counter() - t0) * 1000
    hits = [
        CorrelationHitResponse(
            event_id=h.event.event_id,
            event_type=h.event.event_type,
            data=h.event.data,
            scan_id=h.event.scan_id,
            score=round(h.score, 4),
            metadata=h.event.extra if hasattr(h.event, 'extra') else {},
        )
        for h in result.hits
    ]

    return CorrelateResponse(
        query=req.query,
        strategy=req.strategy,
        total_hits=len(hits),
        hits=hits,
        analysis=result.rag_analysis or None,
        confidence=round(result.confidence, 4),
        risk_level=result.risk_assessment or "INFO",
        elapsed_ms=round(elapsed, 2),
    )


@router.post("/rag/multidim", response_model=MultiDimResponse,
             summary="Run multi-dimensional correlation analysis")
async def multidim_analyze(req: MultiDimRequest,
                           _auth: str = optional_auth_dep) -> MultiDimResponse:
    """Analyze events across multiple OSINT dimensions."""
    analyzer = _get_multidim()
    t0 = time.perf_counter()

    from spiderfoot.multidim_correlation import Dimension, EventData

    dims = None
    if req.dimensions:
        try:
            dims = [Dimension(d.lower()) for d in req.dimensions]
        except ValueError as exc:
            raise HTTPException(status_code=400,
                                detail=f"Unknown dimension: {exc}")

    events = [
        EventData(
            event_id=e.event_id,
            event_type=e.event_type,
            data=e.data,
            scan_id=e.scan_id,
            timestamp=e.timestamp,
            metadata=e.metadata,
        )
        for e in req.events
    ]

    try:
        result = analyzer.analyze(
            query=req.query,
            events=events,
            dimensions=dims,
        )
    except Exception as exc:
        log.error("Multi-dim analysis failed: %s", exc)
        raise HTTPException(status_code=500,
                            detail=f"Analysis failed: {exc}")

    elapsed = (time.perf_counter() - t0) * 1000
    pairs = [
        PairResponse(
            event_a_id=p.event_a_id,
            event_b_id=p.event_b_id,
            fused_score=round(p.fused_score, 4),
            dimensions=[
                DimensionScoreResponse(
                    dimension=ds.dimension.value,
                    score=round(ds.score, 4),
                    evidence_count=ds.evidence_count,
                    details=ds.details,
                )
                for ds in p.dimension_scores
            ],
        )
        for p in result.pairs
    ]

    return MultiDimResponse(
        query=req.query,
        total_events=result.total_events,
        total_pairs=len(pairs),
        total_clusters=len(result.clusters),
        pairs=pairs,
        clusters=result.clusters,
        dimension_summary=result.dimension_summary,
        elapsed_ms=round(elapsed, 2),
    )


@router.post("/rag/search", response_model=SearchResponse,
             summary="Raw semantic search in vector store")
async def semantic_search(req: SearchRequest,
                          _auth: str = optional_auth_dep) -> SearchResponse:
    """Embed query text and retrieve nearest neighbours from Qdrant.

    When ``scan_id`` is provided, the search is scoped to the per-scan
    collection managed by the collection manager (``scan_{scan_id}``).
    Otherwise falls back to the global ``osint_events`` collection.
    """
    t0 = time.perf_counter()

    try:
        from spiderfoot.services.embedding_service import get_embedding_service

        emb = get_embedding_service()
        vec = emb.embed_text(req.query)

        # If a scan_id is provided, route through the collection manager
        if req.scan_id:
            mgr = _get_collection_manager()
            points = mgr.search_scan(
                scan_id=req.scan_id,
                query_vector=vec,
                top_k=req.top_k,
            )
            hits = [
                SearchHitResponse(
                    event_id=str(p.id),
                    score=round(p.score, 4),
                    payload=p.payload,
                )
                for p in points
            ]
        else:
            from spiderfoot.qdrant_client import get_qdrant_client, Filter

            payload_filter = None
            conditions: dict[str, Any] = {}
            if req.event_type:
                conditions["event_type"] = req.event_type
            if conditions:
                filter_conditions = [Filter.match(k, v) for k, v in conditions.items()]
                payload_filter = Filter(must=filter_conditions)

            qd = get_qdrant_client()
            search_result = qd.search(
                collection="osint_events",
                query_vector=vec,
                limit=req.top_k,
                filter_=payload_filter,
            )

            hits = [
                SearchHitResponse(
                    event_id=str(p.id),
                    score=round(p.score, 4),
                    payload=p.payload,
                )
                for p in search_result.points
            ]
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Semantic search failed: %s", exc)
        raise HTTPException(status_code=500,
                            detail=f"Search failed: {exc}")

    elapsed = (time.perf_counter() - t0) * 1000
    return SearchResponse(
        query=req.query,
        total=len(hits),
        hits=hits,
        elapsed_ms=round(elapsed, 2),
    )


@router.get("/rag/stats", response_model=StatsResponse,
            summary="Get RAG correlation engine statistics")
async def stats(_auth: str = optional_auth_dep) -> StatsResponse:
    """Return current engine status and vector store stats."""
    qdrant_ok = False
    emb_ok = False
    total_vectors = 0
    dims = 0
    extra: dict[str, Any] = {}

    try:
        from spiderfoot.qdrant_client import get_qdrant_client
        qd = get_qdrant_client()
        info = qd.collection_stats("osint_events")
        total_vectors = info.get("point_count", 0)
        dims = info.get("vector_dimensions", 0)
        qdrant_ok = True
    except Exception as e:
        log.debug("Qdrant client unavailable for stats: %s", e)

    try:
        from spiderfoot.services.embedding_service import get_embedding_service
        emb = get_embedding_service()
        emb_ok = True
        extra["embedding_cache"] = emb.cache_stats()
    except Exception as e:
        log.debug("Embedding service unavailable for stats: %s", e)

    try:
        analyzer = _get_multidim()
        extra["multidim"] = analyzer.stats()
    except Exception as e:
        log.debug("Multidim analyzer unavailable for stats: %s", e)

    return StatsResponse(
        qdrant_available=qdrant_ok,
        embedding_available=emb_ok,
        collection="osint_events",
        total_vectors=total_vectors,
        dimensions=dims,
        stats=extra,
    )


@router.delete("/rag/collection",
               summary="Reset vector collection")
async def delete_collection(
    collection: str = Query("osint_events",
                            description="Collection to delete"),
    _auth: str = optional_auth_dep,
) -> dict:
    """Delete and re-create the vector collection."""
    try:
        from spiderfoot.qdrant_client import get_qdrant_client
        qd = get_qdrant_client()
        qd.delete_collection(collection)
        return {"deleted": collection, "status": "ok"}
    except Exception as exc:
        log.error("Collection delete failed: %s", exc)
        raise HTTPException(status_code=500,
                            detail=f"Delete failed: {exc}")


# ---------------------------------------------------------------------------
# Collection-aware endpoints (per-scan / per-workspace)
# ---------------------------------------------------------------------------


@router.get("/rag/collections", response_model=CollectionListResponse,
            summary="List managed Qdrant collections")
async def list_collections(
    _auth: str = optional_auth_dep,
) -> CollectionListResponse:
    """List all SpiderFoot-managed Qdrant collections with stats."""
    mgr = _get_collection_manager()
    try:
        from spiderfoot.qdrant_client import get_qdrant_client
        qd = get_qdrant_client()
        all_cols = qd.list_collections()
    except Exception as exc:
        raise HTTPException(status_code=503,
                            detail=f"Qdrant unavailable: {exc}")

    # The collection manager names use scan_/workspace_/global prefixes
    # plus the Qdrant client may prepend its own prefix
    prefix = getattr(mgr._qdrant, '_prefix', '') or ""
    items: list[CollectionInfoResponse] = []
    for name in all_cols:
        info = CollectionInfoResponse(name=name)
        try:
            stats = qd.collection_stats(name)
            info.total_vectors = stats.get("point_count", 0)
            info.dimensions = stats.get("vector_dimensions", 0)
        except Exception:
            pass

        # Identify scope from name (strip any Qdrant prefix)
        suffix = name[len(prefix):] if prefix and name.startswith(prefix) else name
        if suffix.startswith("scan_"):
            info.scope = "scan"
            info.scan_id = suffix[5:]
        elif suffix.startswith("workspace_"):
            info.scope = "workspace"
            info.workspace_id = suffix[10:]
        elif suffix == "global":
            info.scope = "global"
        items.append(info)

    return CollectionListResponse(collections=items, total=len(items))


@router.post("/rag/collections/workspace",
             summary="Create or refresh workspace meta-collection")
async def create_workspace_collection(
    req: WorkspaceCollectionRequest,
    _auth: str = optional_auth_dep,
) -> dict:
    """Create a workspace collection aggregating one or more scan collections.

    Strategy ``federated`` (default): no data is copied; workspace queries
    fan out to each scan collection and merge results.

    Strategy ``materialized``: all vectors from constituent scan collections
    are copied into a dedicated workspace collection for faster queries.
    """
    mgr = _get_collection_manager()
    t0 = time.perf_counter()
    try:
        # Override strategy temporarily if requested
        original_strategy = mgr._config.workspace_strategy
        if req.strategy:
            mgr._config.workspace_strategy = req.strategy
        try:
            mgr.create_workspace_collection(
                workspace_id=req.workspace_id,
                scan_ids=req.scan_ids,
            )
        finally:
            mgr._config.workspace_strategy = original_strategy
    except Exception as exc:
        log.error("Workspace collection creation failed: %s", exc)
        raise HTTPException(status_code=500,
                            detail=f"Failed to create workspace collection: {exc}")

    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "workspace_id": req.workspace_id,
        "scan_ids": req.scan_ids,
        "strategy": req.strategy or mgr._config.workspace_strategy,
        "elapsed_ms": round(elapsed, 2),
        "status": "ok",
    }


@router.post("/rag/collections/workspace/search",
             response_model=SearchResponse,
             summary="Search across all scans in a workspace")
async def workspace_search(
    req: WorkspaceSearchRequest,
    _auth: str = optional_auth_dep,
) -> SearchResponse:
    """Run a semantic search across all scans within a workspace.

    Uses the workspace strategy (federated fan-out or materialized
    collection) configured for this workspace.
    """
    mgr = _get_collection_manager()
    t0 = time.perf_counter()

    try:
        from spiderfoot.services.embedding_service import get_embedding_service
        emb = get_embedding_service()
        vec = emb.embed_text(req.query)

        # Get scan_ids for this workspace from DB
        scan_ids = _get_workspace_scan_ids(req.workspace_id)

        points = mgr.search_workspace(
            workspace_id=req.workspace_id,
            scan_ids=scan_ids,
            query_vector=vec,
            top_k=req.top_k,
        )

        hits = [
            SearchHitResponse(
                event_id=str(p.id),
                score=round(p.score or 0.0, 4),
                payload=p.payload,
            )
            for p in points
        ]
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Workspace search failed: %s", exc)
        raise HTTPException(status_code=500,
                            detail=f"Workspace search failed: {exc}")

    elapsed = (time.perf_counter() - t0) * 1000
    return SearchResponse(
        query=req.query,
        total=len(hits),
        hits=hits,
        elapsed_ms=round(elapsed, 2),
    )


@router.delete("/rag/collections/scan/{scan_id}",
               summary="Delete a scan's vector collection")
async def delete_scan_collection(
    scan_id: str,
    _auth: str = optional_auth_dep,
) -> dict:
    """Remove a per-scan Qdrant collection and all its vectors."""
    mgr = _get_collection_manager()
    try:
        mgr.delete_scan_collection(scan_id)
        return {"scan_id": scan_id, "status": "deleted"}
    except Exception as exc:
        log.error("Failed to delete scan collection %s: %s", scan_id, exc)
        raise HTTPException(status_code=500,
                            detail=f"Delete failed: {exc}")


@router.get("/rag/collections/{collection_name}/stats",
            summary="Stats for a specific collection")
async def collection_stats(
    collection_name: str,
    _auth: str = optional_auth_dep,
) -> dict:
    """Get detailed statistics for a named Qdrant collection."""
    try:
        from spiderfoot.qdrant_client import get_qdrant_client
        qd = get_qdrant_client()
        if not qd.collection_exists(collection_name):
            return {"exists": False, "collection": collection_name}
        info = qd.collection_info(collection_name)
        return {
            "exists": True,
            "collection": collection_name,
            "vector_count": info.point_count if info else 0,
            "vector_size": info.vector_size if info else 0,
            "distance": info.distance.value if info and info.distance else "",
        }
    except Exception as exc:
        log.error("Collection stats failed for %s: %s", collection_name, exc)
        raise HTTPException(status_code=500,
                            detail=f"Stats failed: {exc}")
