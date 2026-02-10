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
from typing import Any, Dict, List, Optional

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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/rag/index", response_model=IndexResponse,
             summary="Index OSINT events into vector store")
async def index_events(req: IndexRequest,
                       _auth: str = optional_auth_dep):
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
                    _auth: str = optional_auth_dep):
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
            top_k=req.top_k,
            threshold=req.threshold,
        )
    except Exception as exc:
        log.error("Correlation failed: %s", exc)
        raise HTTPException(status_code=500,
                            detail=f"Correlation failed: {exc}")

    elapsed = (time.perf_counter() - t0) * 1000
    hits = [
        CorrelationHitResponse(
            event_id=h.event_id,
            event_type=h.event_type,
            data=h.data,
            scan_id=h.scan_id,
            score=round(h.score, 4),
            metadata=h.metadata,
        )
        for h in result.hits
    ]

    return CorrelateResponse(
        query=req.query,
        strategy=req.strategy,
        total_hits=len(hits),
        hits=hits,
        analysis=result.analysis,
        confidence=round(result.confidence, 4),
        risk_level=result.risk_level,
        elapsed_ms=round(elapsed, 2),
    )


@router.post("/rag/multidim", response_model=MultiDimResponse,
             summary="Run multi-dimensional correlation analysis")
async def multidim_analyze(req: MultiDimRequest,
                           _auth: str = optional_auth_dep):
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
                          _auth: str = optional_auth_dep):
    """Embed query text and retrieve nearest neighbours from Qdrant."""
    engine = _get_vector_engine()
    t0 = time.perf_counter()

    try:
        from spiderfoot.embedding_service import get_embedding_service
        from spiderfoot.qdrant_client import get_qdrant_client, Filter

        emb = get_embedding_service()
        vec = emb.embed_text(req.query)

        payload_filter = None
        conditions: dict[str, Any] = {}
        if req.scan_id:
            conditions["scan_id"] = req.scan_id
        if req.event_type:
            conditions["event_type"] = req.event_type
        if conditions:
            payload_filter = Filter.must_match(conditions)

        qd = get_qdrant_client()
        results = qd.search(
            collection="osint_events",
            vector=vec.vector,
            top_k=req.top_k,
            payload_filter=payload_filter,
        )

        hits = [
            SearchHitResponse(
                event_id=r.id,
                score=round(r.score, 4),
                payload=r.payload,
            )
            for r in results
        ]
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
async def stats(_auth: str = optional_auth_dep):
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
        from spiderfoot.embedding_service import get_embedding_service
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
):
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
