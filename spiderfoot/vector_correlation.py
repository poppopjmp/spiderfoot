"""Vector correlation engine — Qdrant + RAG + Reranker for OSINT correlation.

Ties together the vector store, embedding service, RAG pipeline, and
reranker into a unified correlation engine that discovers patterns
across OSINT scan data using semantic similarity.

Pipeline flow::

    Events → Embed → Store in Qdrant
                          ↓
    Query → Embed → Search Qdrant → Rerank → RAG Generate
                                                    ↓
                                             CorrelationResult

Features:

* **Event ingestion** — index OSINT events as vectors with metadata
* **Semantic search** — find related events across scans and types
* **Cross-scan correlation** — identify patterns spanning multiple scans
* **Multi-hop discovery** — follow chains of related entities
* **Configurable correlation strategies** — similarity, clustering, temporal
"""

from __future__ import annotations

import hashlib
import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger("spiderfoot.vector_correlation")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class CorrelationStrategy(Enum):
    SIMILARITY = "similarity"         # direct vector similarity
    CROSS_SCAN = "cross_scan"         # find same entities across scans
    TEMPORAL = "temporal"             # time-based clustering
    INFRASTRUCTURE = "infrastructure" # shared hosting/network
    MULTI_HOP = "multi_hop"           # follow entity chains


@dataclass
class VectorCorrelationConfig:
    """Vector correlation engine configuration."""

    collection_name: str = "osint_events"
    vector_dimensions: int = 384
    similarity_threshold: float = 0.7
    cross_scan_threshold: float = 0.8
    max_results: int = 50
    max_hops: int = 3
    rerank_top_k: int = 10
    min_cluster_size: int = 3
    strategies: List[CorrelationStrategy] = field(
        default_factory=lambda: [CorrelationStrategy.SIMILARITY]
    )


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class OSINTEvent:
    """An OSINT event to be indexed and correlated."""

    event_id: str
    event_type: str         # e.g., "IP_ADDRESS", "DOMAIN_NAME", "EMAIL"
    data: str               # the actual data (IP, domain, etc.)
    source_module: str      # which module produced it
    scan_id: str = ""
    scan_target: str = ""
    confidence: float = 100.0
    risk: int = 0           # 0=info, 1=low, 2=medium, 3=high, 4=critical
    timestamp: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_text(self) -> str:
        """Convert to text for embedding."""
        parts = [
            f"type:{self.event_type}",
            f"data:{self.data}",
            f"source:{self.source_module}",
            f"target:{self.scan_target}",
        ]
        if self.extra:
            for k, v in self.extra.items():
                parts.append(f"{k}:{v}")
        return " | ".join(parts)

    def to_payload(self) -> Dict[str, Any]:
        """Convert to Qdrant payload."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "data": self.data,
            "source_module": self.source_module,
            "scan_id": self.scan_id,
            "scan_target": self.scan_target,
            "confidence": self.confidence,
            "risk": self.risk,
            "timestamp": self.timestamp,
        }


@dataclass
class CorrelationHit:
    """A single correlation match."""

    event: OSINTEvent
    score: float
    rerank_score: Optional[float] = None
    strategy: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "event_id": self.event.event_id,
            "event_type": self.event.event_type,
            "data": self.event.data,
            "source_module": self.event.source_module,
            "scan_id": self.event.scan_id,
            "score": round(self.score, 4),
            "strategy": self.strategy,
        }
        if self.rerank_score is not None:
            d["rerank_score"] = round(self.rerank_score, 4)
        return d


@dataclass
class VectorCorrelationResult:
    """Result of vector correlation analysis."""

    query: str
    strategy: str
    hits: List[CorrelationHit] = field(default_factory=list)
    clusters: List[List[CorrelationHit]] = field(default_factory=list)
    rag_analysis: str = ""
    risk_assessment: str = ""
    confidence: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "strategy": self.strategy,
            "hit_count": len(self.hits),
            "cluster_count": len(self.clusters),
            "rag_analysis": self.rag_analysis[:500] if self.rag_analysis else "",
            "risk_assessment": self.risk_assessment,
            "confidence": round(self.confidence, 3),
            "metrics": {k: round(v, 2) for k, v in self.metrics.items()},
            "hits": [h.to_dict() for h in self.hits[:10]],
        }


# ---------------------------------------------------------------------------
# Vector Correlation Engine
# ---------------------------------------------------------------------------

class VectorCorrelationEngine:
    """Main correlation engine combining vector search with RAG analysis.

    Usage::

        from spiderfoot.qdrant_client import QdrantClient
        from spiderfoot.embedding_service import EmbeddingService
        from spiderfoot.rag_pipeline import RAGPipeline
        from spiderfoot.reranker_service import RerankerService

        engine = VectorCorrelationEngine(
            qdrant=QdrantClient(),
            embeddings=EmbeddingService(),
            rag=RAGPipeline(),
            reranker=RerankerService(),
        )
        engine.index_event(event)
        results = engine.correlate("Find IP correlations for 1.2.3.4")
    """

    def __init__(
        self,
        qdrant: Any = None,
        embeddings: Any = None,
        rag: Any = None,
        reranker: Any = None,
        config: Optional[VectorCorrelationConfig] = None,
    ) -> None:
        self._config = config or VectorCorrelationConfig()
        self._qdrant = qdrant
        self._embeddings = embeddings
        self._rag = rag
        self._reranker = reranker
        self._lock = threading.Lock()
        self._indexed_count = 0

        # Initialize collection
        if self._qdrant:
            self._qdrant.ensure_collection(
                self._config.collection_name,
                vector_size=self._config.vector_dimensions,
            )

    # -----------------------------------------------------------------------
    # Indexing
    # -----------------------------------------------------------------------

    def index_event(self, event: OSINTEvent) -> bool:
        """Index a single OSINT event into the vector store."""
        if not self._qdrant or not self._embeddings:
            log.warning("Qdrant or embedding service not configured")
            return False

        text = event.to_text()
        vector = self._embeddings.embed_text(text)
        if not vector:
            return False

        from spiderfoot.qdrant_client import VectorPoint
        point = VectorPoint(
            id=event.event_id,
            vector=vector,
            payload=event.to_payload(),
        )
        count = self._qdrant.upsert(self._config.collection_name, [point])
        if count > 0:
            with self._lock:
                self._indexed_count += 1
        return count > 0

    def index_events(self, events: List[OSINTEvent],
                     batch_size: int = 100) -> int:
        """Batch index OSINT events."""
        if not self._qdrant or not self._embeddings:
            return 0

        total = 0
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            texts = [e.to_text() for e in batch]
            vectors = self._embeddings.embed_texts(texts)

            from spiderfoot.qdrant_client import VectorPoint
            points = []
            for event, vec in zip(batch, vectors):
                points.append(VectorPoint(
                    id=event.event_id,
                    vector=vec,
                    payload=event.to_payload(),
                ))
            count = self._qdrant.upsert(self._config.collection_name, points)
            total += count

        with self._lock:
            self._indexed_count += total
        return total

    # -----------------------------------------------------------------------
    # Correlation
    # -----------------------------------------------------------------------

    def correlate(self, query: str,
                  strategy: Optional[CorrelationStrategy] = None,
                  scan_id: Optional[str] = None,
                  event_type: Optional[str] = None) -> VectorCorrelationResult:
        """Run a vector correlation query."""
        strat = strategy or self._config.strategies[0]
        start = time.time()

        if strat == CorrelationStrategy.SIMILARITY:
            result = self._correlate_similarity(query, scan_id, event_type)
        elif strat == CorrelationStrategy.CROSS_SCAN:
            result = self._correlate_cross_scan(query, scan_id)
        elif strat == CorrelationStrategy.MULTI_HOP:
            result = self._correlate_multi_hop(query, scan_id, event_type)
        elif strat == CorrelationStrategy.INFRASTRUCTURE:
            result = self._correlate_infrastructure(query, scan_id)
        else:
            result = self._correlate_similarity(query, scan_id, event_type)

        result.strategy = strat.value
        result.metrics["total_ms"] = (time.time() - start) * 1000
        return result

    def _correlate_similarity(self, query: str,
                              scan_id: Optional[str] = None,
                              event_type: Optional[str] = None
                              ) -> VectorCorrelationResult:
        """Direct vector similarity search."""
        result = VectorCorrelationResult(query=query, strategy="similarity")

        if not self._qdrant or not self._embeddings:
            return result

        # Embed query
        t0 = time.time()
        qvec = self._embeddings.embed_text(query)
        result.metrics["embed_ms"] = (time.time() - t0) * 1000

        if not qvec:
            return result

        # Build filter
        from spiderfoot.qdrant_client import Filter
        filter_ = None
        if scan_id or event_type:
            must = []
            if scan_id:
                must.append(Filter.match("scan_id", scan_id))
            if event_type:
                must.append(Filter.match("event_type", event_type))
            filter_ = Filter(must=must)

        # Search
        t0 = time.time()
        search_result = self._qdrant.search(
            self._config.collection_name, qvec,
            limit=self._config.max_results,
            score_threshold=self._config.similarity_threshold,
            filter_=filter_,
        )
        result.metrics["search_ms"] = (time.time() - t0) * 1000

        # Convert to correlation hits
        hits = []
        for p in search_result.points:
            event = self._payload_to_event(p.payload)
            hits.append(CorrelationHit(
                event=event, score=p.score, strategy="similarity",
            ))
        result.hits = hits

        # Rerank if available
        if self._reranker and hits:
            t0 = time.time()
            result.hits = self._rerank_hits(query, hits)
            result.metrics["rerank_ms"] = (time.time() - t0) * 1000

        # RAG analysis if available
        if self._rag and hits:
            t0 = time.time()
            result.rag_analysis = self._rag_analyze(query, result.hits)
            result.metrics["rag_ms"] = (time.time() - t0) * 1000

        result.confidence = self._compute_confidence(result.hits)
        result.risk_assessment = self._assess_risk(result.hits)
        return result

    def _correlate_cross_scan(self, query: str,
                              scan_id: Optional[str] = None
                              ) -> VectorCorrelationResult:
        """Find entities that appear across multiple scans."""
        result = VectorCorrelationResult(query=query, strategy="cross_scan")

        if not self._qdrant or not self._embeddings:
            return result

        qvec = self._embeddings.embed_text(query)
        if not qvec:
            return result

        # Search without scan filter to find cross-scan matches
        search_result = self._qdrant.search(
            self._config.collection_name, qvec,
            limit=self._config.max_results,
            score_threshold=self._config.cross_scan_threshold,
        )

        # Group by scan_id
        scan_groups: Dict[str, List[CorrelationHit]] = {}
        for p in search_result.points:
            event = self._payload_to_event(p.payload)
            hit = CorrelationHit(event=event, score=p.score, strategy="cross_scan")
            sid = event.scan_id or "unknown"
            scan_groups.setdefault(sid, []).append(hit)

        # Only keep items found in 2+ scans
        multi_scan_hits = []
        seen_data: Dict[str, Set[str]] = {}
        for sid, hits in scan_groups.items():
            for h in hits:
                key = f"{h.event.event_type}:{h.event.data}"
                seen_data.setdefault(key, set()).add(sid)

        for sid, hits in scan_groups.items():
            for h in hits:
                key = f"{h.event.event_type}:{h.event.data}"
                if len(seen_data.get(key, set())) >= 2:
                    multi_scan_hits.append(h)

        result.hits = multi_scan_hits

        # Cluster by data value
        clusters: Dict[str, List[CorrelationHit]] = {}
        for h in multi_scan_hits:
            key = f"{h.event.event_type}:{h.event.data}"
            clusters.setdefault(key, []).append(h)
        result.clusters = [v for v in clusters.values()
                           if len(v) >= self._config.min_cluster_size]

        if self._rag and multi_scan_hits:
            result.rag_analysis = self._rag_analyze(query, multi_scan_hits)

        result.confidence = self._compute_confidence(multi_scan_hits)
        result.risk_assessment = self._assess_risk(multi_scan_hits)
        return result

    def _correlate_multi_hop(self, query: str,
                             scan_id: Optional[str] = None,
                             event_type: Optional[str] = None
                             ) -> VectorCorrelationResult:
        """Follow chains of related entities (multi-hop)."""
        result = VectorCorrelationResult(query=query, strategy="multi_hop")

        if not self._qdrant or not self._embeddings:
            return result

        all_hits: List[CorrelationHit] = []
        seen_ids: Set[str] = set()
        current_query = query

        for hop in range(self._config.max_hops):
            qvec = self._embeddings.embed_text(current_query)
            if not qvec:
                break

            search_result = self._qdrant.search(
                self._config.collection_name, qvec,
                limit=5,
                score_threshold=self._config.similarity_threshold,
            )

            hop_hits = []
            for p in search_result.points:
                if p.id in seen_ids:
                    continue
                seen_ids.add(p.id)
                event = self._payload_to_event(p.payload)
                hit = CorrelationHit(
                    event=event, score=p.score,
                    strategy=f"multi_hop_h{hop}",
                )
                hop_hits.append(hit)
                all_hits.append(hit)

            if not hop_hits:
                break

            # Use top hit's data as next query
            current_query = hop_hits[0].event.to_text()

        result.hits = all_hits
        if self._rag and all_hits:
            result.rag_analysis = self._rag_analyze(query, all_hits)
        result.confidence = self._compute_confidence(all_hits)
        result.risk_assessment = self._assess_risk(all_hits)
        return result

    def _correlate_infrastructure(self, query: str,
                                  scan_id: Optional[str] = None
                                  ) -> VectorCorrelationResult:
        """Find shared infrastructure patterns."""
        result = VectorCorrelationResult(query=query, strategy="infrastructure")

        if not self._qdrant or not self._embeddings:
            return result

        # Search for infrastructure-related event types
        infra_types = {"IP_ADDRESS", "INTERNET_NAME", "PROVIDER_HOSTING",
                       "WEBSERVER_BANNER", "TCP_PORT_OPEN", "PROVIDER_DNS"}

        qvec = self._embeddings.embed_text(query)
        if not qvec:
            return result

        search_result = self._qdrant.search(
            self._config.collection_name, qvec,
            limit=self._config.max_results,
            score_threshold=self._config.similarity_threshold,
        )

        hits = []
        for p in search_result.points:
            event = self._payload_to_event(p.payload)
            if event.event_type in infra_types:
                hits.append(CorrelationHit(
                    event=event, score=p.score,
                    strategy="infrastructure",
                ))

        result.hits = hits
        if self._rag and hits:
            result.rag_analysis = self._rag_analyze(query, hits)
        result.confidence = self._compute_confidence(hits)
        result.risk_assessment = self._assess_risk(hits)
        return result

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _payload_to_event(self, payload: Dict[str, Any]) -> OSINTEvent:
        """Convert Qdrant payload back to OSINTEvent."""
        return OSINTEvent(
            event_id=payload.get("event_id", ""),
            event_type=payload.get("event_type", ""),
            data=payload.get("data", ""),
            source_module=payload.get("source_module", ""),
            scan_id=payload.get("scan_id", ""),
            scan_target=payload.get("scan_target", ""),
            confidence=payload.get("confidence", 100.0),
            risk=payload.get("risk", 0),
            timestamp=payload.get("timestamp", 0.0),
        )

    def _rerank_hits(self, query: str,
                     hits: List[CorrelationHit]) -> List[CorrelationHit]:
        """Rerank correlation hits using the reranker service."""
        from spiderfoot.reranker_service import RerankItem
        items = [
            RerankItem(
                id=h.event.event_id,
                text=h.event.to_text(),
                retrieval_score=h.score,
                metadata=h.event.to_payload(),
            )
            for h in hits
        ]
        response = self._reranker.rerank(
            query, items, top_k=self._config.rerank_top_k,
        )
        # Map back to CorrelationHit
        result_map = {r.id: r for r in response.results}
        reranked = []
        for h in hits:
            rr = result_map.get(h.event.event_id)
            if rr:
                h.rerank_score = rr.rerank_score
                reranked.append(h)
        reranked.sort(key=lambda x: x.rerank_score or 0, reverse=True)
        return reranked

    def _rag_analyze(self, query: str,
                     hits: List[CorrelationHit]) -> str:
        """Run RAG analysis on correlation hits."""
        from spiderfoot.rag_pipeline import RetrievedChunk, MockRetriever

        chunks = [
            RetrievedChunk(
                id=h.event.event_id,
                text=h.event.to_text(),
                score=h.score,
                metadata=h.event.to_payload(),
            )
            for h in hits[:self._config.rerank_top_k]
        ]

        # Temporarily set retriever with pre-loaded chunks
        retriever = MockRetriever(chunks)
        self._rag.set_retriever(retriever)
        response = self._rag.query(query)
        return response.answer

    def _compute_confidence(self, hits: List[CorrelationHit]) -> float:
        """Compute overall confidence from hit scores."""
        if not hits:
            return 0.0
        avg_score = sum(h.score for h in hits) / len(hits)
        count_factor = min(1.0, len(hits) / 10.0)
        return avg_score * 0.7 + count_factor * 0.3

    def _assess_risk(self, hits: List[CorrelationHit]) -> str:
        """Assess overall risk level from hits."""
        if not hits:
            return "INFO"
        max_risk = max(h.event.risk for h in hits)
        risk_map = {0: "INFO", 1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}
        return risk_map.get(max_risk, "INFO")

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        s: Dict[str, Any] = {
            "indexed_count": self._indexed_count,
            "collection": self._config.collection_name,
            "strategies": [s.value for s in self._config.strategies],
        }
        if self._qdrant:
            s["qdrant"] = self._qdrant.stats()
        return s
