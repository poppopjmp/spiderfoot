"""Tests for spiderfoot.vector_correlation — vector correlation engine."""

import pytest
from spiderfoot.qdrant_client import QdrantClient, QdrantConfig, QdrantBackend
from spiderfoot.embedding_service import EmbeddingConfig, EmbeddingProvider, EmbeddingService
from spiderfoot.rag_pipeline import RAGConfig, LLMProvider, RAGPipeline
from spiderfoot.reranker_service import RerankerConfig, RerankerProvider, RerankerService
from spiderfoot.vector_correlation import (
    CorrelationHit,
    CorrelationStrategy,
    OSINTEvent,
    VectorCorrelationConfig,
    VectorCorrelationEngine,
    VectorCorrelationResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_engine(**kwargs) -> VectorCorrelationEngine:
    qdrant_cfg = QdrantConfig(backend=QdrantBackend.MEMORY, collection_prefix="test_")
    qdrant = QdrantClient(qdrant_cfg)

    embed_cfg = EmbeddingConfig(provider=EmbeddingProvider.MOCK, dimensions=64)
    embeddings = EmbeddingService(embed_cfg)

    rag_cfg = RAGConfig(llm_provider=LLMProvider.MOCK, rerank_enabled=False)
    rag = RAGPipeline(config=rag_cfg)

    reranker_cfg = RerankerConfig(provider=RerankerProvider.MOCK, top_k=5)
    reranker = RerankerService(reranker_cfg)

    vcfg = VectorCorrelationConfig(
        vector_dimensions=64,
        similarity_threshold=0.0,
        cross_scan_threshold=0.0,
        max_results=20,
        **kwargs,
    )
    return VectorCorrelationEngine(
        qdrant=qdrant, embeddings=embeddings,
        rag=rag, reranker=reranker, config=vcfg,
    )


def _sample_events(n: int = 5, scan_id: str = "scan1") -> list:
    return [
        OSINTEvent(
            event_id=f"evt_{scan_id}_{i}",
            event_type=["IP_ADDRESS", "DOMAIN_NAME", "EMAIL", "URL", "WEBSERVER_BANNER"][i % 5],
            data=f"data_{i}.example.com",
            source_module=f"sfp_module{i}",
            scan_id=scan_id,
            scan_target="example.com",
            risk=i % 5,
            timestamp=1700000000 + i * 100,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# OSINTEvent
# ---------------------------------------------------------------------------

class TestOSINTEvent:
    def test_to_text(self):
        e = OSINTEvent(
            event_id="e1", event_type="IP_ADDRESS",
            data="1.2.3.4", source_module="sfp_dns",
            scan_target="example.com",
        )
        text = e.to_text()
        assert "IP_ADDRESS" in text
        assert "1.2.3.4" in text
        assert "sfp_dns" in text

    def test_to_payload(self):
        e = OSINTEvent(
            event_id="e1", event_type="DOMAIN_NAME",
            data="test.com", source_module="sfp_dns",
            scan_id="s1", risk=3,
        )
        p = e.to_payload()
        assert p["event_id"] == "e1"
        assert p["risk"] == 3

    def test_to_text_with_extra(self):
        e = OSINTEvent(
            event_id="e1", event_type="IP_ADDRESS",
            data="1.2.3.4", source_module="sfp_dns",
            extra={"asn": "AS12345"},
        )
        text = e.to_text()
        assert "AS12345" in text


# ---------------------------------------------------------------------------
# CorrelationHit
# ---------------------------------------------------------------------------

class TestCorrelationHit:
    def test_to_dict(self):
        e = OSINTEvent(event_id="e1", event_type="IP", data="1.2.3.4",
                       source_module="mod", scan_id="s1")
        h = CorrelationHit(event=e, score=0.95, strategy="similarity")
        d = h.to_dict()
        assert d["score"] == 0.95
        assert d["strategy"] == "similarity"

    def test_to_dict_with_rerank(self):
        e = OSINTEvent(event_id="e1", event_type="IP", data="1.2.3.4",
                       source_module="mod")
        h = CorrelationHit(event=e, score=0.9, rerank_score=0.85)
        d = h.to_dict()
        assert d["rerank_score"] == 0.85


# ---------------------------------------------------------------------------
# VectorCorrelationResult
# ---------------------------------------------------------------------------

class TestVectorCorrelationResult:
    def test_to_dict(self):
        r = VectorCorrelationResult(
            query="test", strategy="similarity",
            hits=[], confidence=0.8,
            risk_assessment="MEDIUM",
        )
        d = r.to_dict()
        assert d["strategy"] == "similarity"
        assert d["confidence"] == 0.8


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

class TestIndexing:
    def test_index_single_event(self):
        engine = _make_engine()
        event = _sample_events(1)[0]
        assert engine.index_event(event) is True

    def test_index_batch(self):
        engine = _make_engine()
        events = _sample_events(10)
        count = engine.index_events(events)
        assert count == 10

    def test_index_no_qdrant(self):
        engine = VectorCorrelationEngine()
        event = _sample_events(1)[0]
        assert engine.index_event(event) is False

    def test_index_batch_no_qdrant(self):
        engine = VectorCorrelationEngine()
        assert engine.index_events(_sample_events(5)) == 0


# ---------------------------------------------------------------------------
# Similarity correlation
# ---------------------------------------------------------------------------

class TestSimilarityCorrelation:
    def setup_method(self):
        self.engine = _make_engine()
        self.engine.index_events(_sample_events(10))

    def test_basic_search(self):
        result = self.engine.correlate(
            "IP_ADDRESS data_0.example.com",
            strategy=CorrelationStrategy.SIMILARITY,
        )
        assert result.strategy == "similarity"
        assert len(result.hits) > 0
        assert result.confidence > 0
        assert "total_ms" in result.metrics

    def test_search_with_event_type(self):
        result = self.engine.correlate(
            "data_0.example.com",
            strategy=CorrelationStrategy.SIMILARITY,
            event_type="IP_ADDRESS",
        )
        for h in result.hits:
            assert h.event.event_type == "IP_ADDRESS"

    def test_search_with_scan_filter(self):
        result = self.engine.correlate(
            "data_0.example.com",
            strategy=CorrelationStrategy.SIMILARITY,
            scan_id="scan1",
        )
        for h in result.hits:
            assert h.event.scan_id == "scan1"

    def test_empty_results(self):
        engine = _make_engine()  # no events indexed
        result = engine.correlate("test")
        assert len(result.hits) == 0

    def test_rag_analysis_present(self):
        result = self.engine.correlate("data_0.example.com")
        assert len(result.rag_analysis) > 0

    def test_risk_assessment(self):
        result = self.engine.correlate("data_0.example.com")
        assert result.risk_assessment in ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")


# ---------------------------------------------------------------------------
# Cross-scan correlation
# ---------------------------------------------------------------------------

class TestCrossScanCorrelation:
    def test_cross_scan(self):
        engine = _make_engine()
        # Index events with same data across two scans
        events_s1 = _sample_events(5, scan_id="scan_a")
        events_s2 = _sample_events(5, scan_id="scan_b")
        engine.index_events(events_s1)
        engine.index_events(events_s2)

        result = engine.correlate(
            "data_0.example.com",
            strategy=CorrelationStrategy.CROSS_SCAN,
        )
        assert result.strategy == "cross_scan"


# ---------------------------------------------------------------------------
# Multi-hop correlation
# ---------------------------------------------------------------------------

class TestMultiHopCorrelation:
    def test_multi_hop(self):
        engine = _make_engine(max_hops=2)
        engine.index_events(_sample_events(10))

        result = engine.correlate(
            "data_0.example.com",
            strategy=CorrelationStrategy.MULTI_HOP,
        )
        assert result.strategy == "multi_hop"
        # Should find hits across hops
        assert len(result.hits) > 0

    def test_multi_hop_no_data(self):
        engine = _make_engine(max_hops=2)
        result = engine.correlate(
            "unknown query",
            strategy=CorrelationStrategy.MULTI_HOP,
        )
        assert len(result.hits) == 0


# ---------------------------------------------------------------------------
# Infrastructure correlation
# ---------------------------------------------------------------------------

class TestInfrastructureCorrelation:
    def test_infrastructure(self):
        engine = _make_engine()
        # Index infrastructure-type events
        events = [
            OSINTEvent(
                event_id=f"infra_{i}", event_type="IP_ADDRESS",
                data=f"10.0.0.{i}", source_module="sfp_dns",
                scan_id="s1", scan_target="target.com",
            )
            for i in range(5)
        ]
        engine.index_events(events)

        result = engine.correlate(
            "IP_ADDRESS 10.0.0",
            strategy=CorrelationStrategy.INFRASTRUCTURE,
        )
        assert result.strategy == "infrastructure"


# ---------------------------------------------------------------------------
# Engine stats
# ---------------------------------------------------------------------------

class TestEngineStats:
    def test_stats(self):
        engine = _make_engine()
        engine.index_events(_sample_events(5))
        s = engine.stats()
        assert s["indexed_count"] == 5
        assert "qdrant" in s

    def test_stats_no_qdrant(self):
        engine = VectorCorrelationEngine()
        s = engine.stats()
        assert s["indexed_count"] == 0
