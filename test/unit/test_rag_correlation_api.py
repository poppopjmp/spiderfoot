"""Tests for spiderfoot.api.routers.rag_correlation — REST endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Reset singletons before importing
import spiderfoot.api.routers.rag_correlation as rag_mod
rag_mod._vector_engine = None
rag_mod._multidim_analyzer = None

from spiderfoot.api.main import app

client = TestClient(app, raise_server_exceptions=False)

API = "/api/rag"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singletons():
    """Clear singletons between tests."""
    rag_mod._vector_engine = None
    rag_mod._multidim_analyzer = None
    yield
    rag_mod._vector_engine = None
    rag_mod._multidim_analyzer = None


def _mock_engine():
    """Return a mock VectorCorrelationEngine."""
    engine = MagicMock()
    engine.index_events = MagicMock(return_value=None)

    from types import SimpleNamespace
    hit = SimpleNamespace(
        event_id="e1", event_type="IP_ADDRESS", data="1.2.3.4",
        scan_id="s1", score=0.95, metadata={"asn": "AS13335"},
    )
    result = SimpleNamespace(
        hits=[hit], analysis="RAG analysis text",
        confidence=0.87, risk_level="MEDIUM",
    )
    engine.correlate = MagicMock(return_value=result)
    return engine


def _mock_multidim():
    """Return a mock MultiDimAnalyzer."""
    from spiderfoot.multidim_correlation import (
        CorrelationPair, DimensionScore, Dimension, MultiDimResult,
    )
    analyzer = MagicMock()
    pair = CorrelationPair(
        event_a_id="a", event_b_id="b", fused_score=0.75,
        dimension_scores=[DimensionScore(Dimension.ENTITY, 0.8)],
    )
    result = MultiDimResult(
        query="test", total_events=2, elapsed_ms=5.0,
        pairs=[pair], clusters=[["a", "b"]],
        dimension_summary={"entity": 0.8},
    )
    analyzer.analyze = MagicMock(return_value=result)
    analyzer.stats = MagicMock(return_value={"fusion_method": "weighted"})
    return analyzer


# ---------------------------------------------------------------------------
# Index endpoint
# ---------------------------------------------------------------------------

class TestIndex:
    def test_index_success(self):
        engine = _mock_engine()
        rag_mod._vector_engine = engine
        resp = client.post(f"{API}/index", json={
            "events": [
                {"event_id": "e1", "event_type": "IP_ADDRESS",
                 "data": "1.2.3.4", "scan_id": "s1"},
            ],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["indexed"] == 1
        assert body["collection"] == "osint_events"
        assert "elapsed_ms" in body

    def test_index_empty_fails(self):
        resp = client.post(f"{API}/index", json={"events": []})
        assert resp.status_code == 422  # validation error


# ---------------------------------------------------------------------------
# Correlate endpoint
# ---------------------------------------------------------------------------

class TestCorrelate:
    def test_correlate_success(self):
        engine = _mock_engine()
        rag_mod._vector_engine = engine
        resp = client.post(f"{API}/correlate", json={
            "query": "find related IPs",
            "strategy": "similarity",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_hits"] == 1
        assert body["hits"][0]["event_id"] == "e1"
        assert body["analysis"] == "RAG analysis text"

    def test_correlate_bad_strategy(self):
        engine = _mock_engine()
        rag_mod._vector_engine = engine
        resp = client.post(f"{API}/correlate", json={
            "query": "test", "strategy": "invalid",
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Multi-dim endpoint
# ---------------------------------------------------------------------------

class TestMultiDim:
    def test_multidim_success(self):
        analyzer = _mock_multidim()
        rag_mod._multidim_analyzer = analyzer
        resp = client.post(f"{API}/multidim", json={
            "query": "test",
            "events": [
                {"event_id": "a", "event_type": "IP_ADDRESS", "data": "1.1.1.1"},
                {"event_id": "b", "event_type": "IP_ADDRESS", "data": "1.1.1.2"},
            ],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_events"] == 2
        assert len(body["pairs"]) == 1
        assert body["pairs"][0]["fused_score"] == 0.75

    def test_multidim_bad_dimension(self):
        analyzer = _mock_multidim()
        rag_mod._multidim_analyzer = analyzer
        resp = client.post(f"{API}/multidim", json={
            "query": "test",
            "events": [
                {"event_id": "a", "event_type": "IP_ADDRESS", "data": "1.1.1.1"},
            ],
            "dimensions": ["nonexistent"],
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_partial(self):
        """Stats should return even if Qdrant is unavailable."""
        resp = client.get(f"{API}/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "qdrant_available" in body
        assert "embedding_available" in body


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------

class TestSearch:
    @patch("spiderfoot.embedding_service.get_embedding_service")
    @patch("spiderfoot.qdrant_client.get_qdrant_client")
    def test_search_success(self, mock_qd_fn, mock_emb_fn):
        from types import SimpleNamespace

        mock_emb = MagicMock()
        mock_emb.embed_text.return_value = SimpleNamespace(vector=[0.1] * 384)
        mock_emb_fn.return_value = mock_emb

        mock_qd = MagicMock()
        sr = SimpleNamespace(id="e1", score=0.9, payload={"data": "1.2.3.4"})
        mock_qd.search.return_value = [sr]
        mock_qd_fn.return_value = mock_qd

        engine = _mock_engine()
        rag_mod._vector_engine = engine

        resp = client.post(f"{API}/search", json={
            "query": "find malicious IPs",
            "top_k": 5,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1


# ---------------------------------------------------------------------------
# Delete collection endpoint
# ---------------------------------------------------------------------------

class TestDeleteCollection:
    def test_delete_success(self):
        with patch("spiderfoot.qdrant_client.get_qdrant_client") as mock_fn:
            mock_qd = MagicMock()
            mock_fn.return_value = mock_qd
            resp = client.delete(f"{API}/collection",
                                 params={"collection": "test_col"})
            assert resp.status_code == 200
            mock_qd.delete_collection.assert_called_once_with("test_col")


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------

class TestModels:
    def test_event_payload(self):
        from spiderfoot.api.routers.rag_correlation import EventPayload
        e = EventPayload(event_id="x", event_type="IP_ADDRESS", data="1.2.3.4")
        assert e.scan_id == ""
        assert e.metadata == {}

    def test_correlate_request_defaults(self):
        from spiderfoot.api.routers.rag_correlation import CorrelateRequest
        r = CorrelateRequest(query="test")
        assert r.strategy == "similarity"
        assert r.top_k == 20
        assert r.use_reranker is True

    def test_multidim_request_defaults(self):
        from spiderfoot.api.routers.rag_correlation import MultiDimRequest
        r = MultiDimRequest(query="q", events=[
            {"event_id": "a", "event_type": "IP_ADDRESS", "data": "1.1.1.1"},
        ])
        assert r.fusion_method == "weighted"
        assert r.min_score == 0.3
