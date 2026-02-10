"""Tests for spiderfoot.reranker_service — cross-encoder reranking."""

from __future__ import annotations

import math
import pytest
from spiderfoot.reranker_service import (
    MockRerankerBackend,
    RerankerConfig,
    RerankerProvider,
    RerankerService,
    RerankItem,
    RerankResponse,
    RerankResult,
    ScoreNormalization,
    _sigmoid,
    _minmax_normalize,
    normalize_scores,
    reciprocal_rank_fusion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_items(n: int = 5) -> list:
    return [
        RerankItem(
            id=f"d{i}", text=f"Document about topic{i} with relevant data",
            retrieval_score=0.9 - i * 0.1,
            metadata={"source": f"src{i}"},
        )
        for i in range(n)
    ]


def _make_service(**kwargs) -> RerankerService:
    cfg = RerankerConfig(provider=RerankerProvider.MOCK, **kwargs)
    return RerankerService(cfg)


# ---------------------------------------------------------------------------
# Score normalization
# ---------------------------------------------------------------------------

class TestSigmoid:
    def test_zero(self):
        assert abs(_sigmoid(0) - 0.5) < 1e-6

    def test_large_positive(self):
        assert _sigmoid(100) > 0.99

    def test_large_negative(self):
        assert _sigmoid(-100) < 0.01

    def test_overflow(self):
        assert _sigmoid(-1000) == 0.0
        assert _sigmoid(1000) == 1.0


class TestMinmaxNormalize:
    def test_basic(self):
        result = _minmax_normalize([1.0, 3.0, 5.0])
        assert abs(result[0] - 0.0) < 1e-6
        assert abs(result[2] - 1.0) < 1e-6

    def test_equal_values(self):
        result = _minmax_normalize([5.0, 5.0, 5.0])
        assert all(abs(v - 0.5) < 1e-6 for v in result)

    def test_empty(self):
        assert _minmax_normalize([]) == []


class TestNormalizeScores:
    def test_none(self):
        scores = [0.5, 1.0, -0.5]
        assert normalize_scores(scores, ScoreNormalization.NONE) == scores

    def test_sigmoid(self):
        result = normalize_scores([0.0, 1.0], ScoreNormalization.SIGMOID)
        assert abs(result[0] - 0.5) < 1e-6
        assert result[1] > 0.5

    def test_minmax(self):
        result = normalize_scores([1.0, 3.0, 5.0], ScoreNormalization.MINMAX)
        assert abs(result[0] - 0.0) < 1e-6
        assert abs(result[2] - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

class TestRRF:
    def test_basic(self):
        scores = reciprocal_rank_fusion([1, 2, 3], [1, 3, 2], k=60)
        assert len(scores) == 3
        # Document ranked 1st in both should have highest RRF
        assert scores[0] > scores[1]

    def test_same_ranks(self):
        scores = reciprocal_rank_fusion([1, 2], [1, 2], k=60)
        assert scores[0] > scores[1]

    def test_swapped_ranks(self):
        scores = reciprocal_rank_fusion([1, 2], [2, 1], k=60)
        # Both documents get same RRF when ranks are swapped symmetrically
        assert abs(scores[0] - scores[1]) < 1e-6


# ---------------------------------------------------------------------------
# RerankResult
# ---------------------------------------------------------------------------

class TestRerankResult:
    def test_to_dict(self):
        r = RerankResult(
            id="r1", text="hello world" * 100,
            retrieval_score=0.9, rerank_score=0.85,
            combined_score=0.033, retrieval_rank=1, rerank_rank=2,
        )
        d = r.to_dict()
        assert len(d["text"]) <= 200
        assert d["retrieval_score"] == 0.9
        assert d["rerank_rank"] == 2


# ---------------------------------------------------------------------------
# RerankResponse
# ---------------------------------------------------------------------------

class TestRerankResponse:
    def test_to_dict(self):
        r = RerankResponse(
            query="test", results=[
                RerankResult(id="r1", text="hi", rerank_score=0.9),
            ],
            model="mock", elapsed_ms=5.5, input_count=3,
        )
        d = r.to_dict()
        assert d["input_count"] == 3
        assert d["output_count"] == 1


# ---------------------------------------------------------------------------
# RerankerConfig
# ---------------------------------------------------------------------------

class TestRerankerConfig:
    def test_defaults(self):
        cfg = RerankerConfig()
        assert cfg.provider == RerankerProvider.MOCK
        assert cfg.top_k == 5

    def test_from_env(self):
        env = {
            "SF_RERANKER_PROVIDER": "cohere",
            "SF_RERANKER_MODEL": "rerank-v3.5",
            "SF_RERANKER_API_KEY": "key123",
            "SF_RERANKER_TOP_K": "10",
            "SF_RERANKER_THRESHOLD": "0.3",
        }
        cfg = RerankerConfig.from_env(env)
        assert cfg.provider == RerankerProvider.COHERE
        assert cfg.top_k == 10
        assert cfg.score_threshold == 0.3


# ---------------------------------------------------------------------------
# MockRerankerBackend
# ---------------------------------------------------------------------------

class TestMockRerankerBackend:
    def test_score(self):
        backend = MockRerankerBackend()
        scores = backend.score("topic0", [
            "Document about topic0 data",
            "Unrelated random text here",
        ])
        assert len(scores) == 2
        assert scores[0] > scores[1]

    def test_empty_query(self):
        backend = MockRerankerBackend()
        scores = backend.score("", ["doc1", "doc2"])
        assert len(scores) == 2

    def test_model_name(self):
        assert MockRerankerBackend().model_name() == "mock-reranker"


# ---------------------------------------------------------------------------
# RerankerService
# ---------------------------------------------------------------------------

class TestRerankerService:
    def test_rerank_basic(self):
        svc = _make_service(top_k=3)
        items = _sample_items(5)
        response = svc.rerank("topic0 data", items)
        assert len(response.results) == 3
        assert response.input_count == 5
        assert response.elapsed_ms >= 0

    def test_rerank_empty(self):
        svc = _make_service()
        response = svc.rerank("test", [])
        assert len(response.results) == 0

    def test_results_have_scores(self):
        svc = _make_service(top_k=3)
        response = svc.rerank("topic0", _sample_items())
        for r in response.results:
            assert r.rerank_score >= 0
            assert r.combined_score > 0
            assert r.rerank_rank > 0

    def test_top_k_override(self):
        svc = _make_service(top_k=5)
        response = svc.rerank("test", _sample_items(10), top_k=2)
        assert len(response.results) == 2

    def test_score_threshold(self):
        svc = _make_service(top_k=10)
        response = svc.rerank("test", _sample_items(5), score_threshold=0.9)
        # With sigmoid normalization, most scores cluster around 0.5
        # so a 0.9 threshold should filter most
        assert len(response.results) < 5

    def test_ranking_order(self):
        svc = _make_service(top_k=5)
        response = svc.rerank("topic0 data", _sample_items(5))
        # Results should be sorted by combined score descending
        scores = [r.combined_score for r in response.results]
        assert scores == sorted(scores, reverse=True)

    def test_batch_scoring(self):
        svc = _make_service(top_k=5, batch_size=2)
        response = svc.rerank("test", _sample_items(5))
        assert len(response.results) == 5

    def test_stats(self):
        svc = _make_service()
        s = svc.stats()
        assert s["provider"] == "mock"
        assert s["model"] == "mock-reranker"

    def test_normalization_none(self):
        svc = _make_service(normalization=ScoreNormalization.NONE)
        response = svc.rerank("topic0", _sample_items(3))
        assert len(response.results) == 3

    def test_normalization_minmax(self):
        svc = _make_service(normalization=ScoreNormalization.MINMAX)
        response = svc.rerank("topic0", _sample_items(3))
        scores = [r.rerank_score for r in response.results]
        assert all(0 <= s <= 1 for s in scores)

    def test_response_to_dict(self):
        svc = _make_service(top_k=2)
        response = svc.rerank("test", _sample_items(3))
        d = response.to_dict()
        assert "query" in d
        assert "results" in d
        assert d["input_count"] == 3
