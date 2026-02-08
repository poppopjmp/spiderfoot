"""Tests for spiderfoot.rag_pipeline — RAG pipeline core."""

import pytest
from spiderfoot.rag_pipeline import (
    LLMProvider,
    MockLLMBackend,
    MockReranker,
    MockRetriever,
    PassthroughReranker,
    PipelineMetrics,
    PROMPT_TEMPLATES,
    RAGConfig,
    RAGContext,
    RAGPipeline,
    RAGResponse,
    RetrievedChunk,
    _estimate_tokens,
    _format_evidence,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_chunks(n: int = 5) -> list:
    return [
        RetrievedChunk(
            id=f"c{i}", text=f"Evidence item {i} about target{i}.com",
            score=0.9 - i * 0.1,
            metadata={"type": f"type{i}", "scan": "s1"},
        )
        for i in range(n)
    ]


def _make_pipeline(chunks=None, rerank=True) -> RAGPipeline:
    cfg = RAGConfig(
        llm_provider=LLMProvider.MOCK,
        rerank_enabled=rerank,
        retrieval_top_k=10,
        rerank_top_k=3,
    )
    retriever = MockRetriever(chunks if chunks is not None else _sample_chunks())
    return RAGPipeline(config=cfg, retriever=retriever)


# ---------------------------------------------------------------------------
# RetrievedChunk
# ---------------------------------------------------------------------------

class TestRetrievedChunk:
    def test_to_dict(self):
        c = RetrievedChunk(id="c1", text="hello", score=0.95,
                           metadata={"k": "v"}, rerank_score=0.88)
        d = c.to_dict()
        assert d["id"] == "c1"
        assert d["rerank_score"] == 0.88

    def test_to_dict_no_rerank(self):
        c = RetrievedChunk(id="c1", text="t", score=0.5)
        d = c.to_dict()
        assert "rerank_score" not in d


# ---------------------------------------------------------------------------
# RAGContext
# ---------------------------------------------------------------------------

class TestRAGContext:
    def test_to_dict(self):
        ctx = RAGContext(query="test", chunks=_sample_chunks(3),
                         token_estimate=500)
        d = ctx.to_dict()
        assert d["query"] == "test"
        assert d["num_chunks"] == 3
        assert d["token_estimate"] == 500


# ---------------------------------------------------------------------------
# RAGResponse
# ---------------------------------------------------------------------------

class TestRAGResponse:
    def test_to_dict(self):
        r = RAGResponse(query="q", answer="a",
                        chunks=_sample_chunks(2), model="mock",
                        metrics={"total_ms": 100.0})
        d = r.to_dict()
        assert d["model"] == "mock"
        assert len(d["chunks"]) == 2
        assert d["metrics"]["total_ms"] == 100.0


# ---------------------------------------------------------------------------
# PipelineMetrics
# ---------------------------------------------------------------------------

class TestPipelineMetrics:
    def test_to_dict(self):
        m = PipelineMetrics(retrieval_ms=10.5, rerank_ms=5.3,
                            context_ms=1.2, generation_ms=50.1,
                            total_ms=67.1)
        d = m.to_dict()
        assert d["retrieval_ms"] == 10.5
        assert d["total_ms"] == 67.1


# ---------------------------------------------------------------------------
# RAGConfig
# ---------------------------------------------------------------------------

class TestRAGConfig:
    def test_defaults(self):
        cfg = RAGConfig()
        assert cfg.llm_provider == LLMProvider.MOCK
        assert cfg.rerank_enabled is True

    def test_from_env(self):
        env = {
            "SF_LLM_PROVIDER": "openai",
            "SF_LLM_MODEL": "gpt-4o",
            "SF_LLM_API_KEY": "sk-test",
            "SF_RAG_RETRIEVAL_K": "30",
            "SF_RAG_RERANK": "false",
            "SF_RAG_RERANK_K": "10",
        }
        cfg = RAGConfig.from_env(env)
        assert cfg.llm_provider == LLMProvider.OPENAI
        assert cfg.llm_model == "gpt-4o"
        assert cfg.retrieval_top_k == 30
        assert cfg.rerank_enabled is False
        assert cfg.rerank_top_k == 10


# ---------------------------------------------------------------------------
# MockLLMBackend
# ---------------------------------------------------------------------------

class TestMockLLMBackend:
    def test_generate(self):
        llm = MockLLMBackend()
        text, meta = llm.generate("system", "user [Evidence 1] [Evidence 2]")
        assert "2 evidence" in text
        assert meta["model"] == "mock"

    def test_model_name(self):
        assert MockLLMBackend().model_name() == "mock"


# ---------------------------------------------------------------------------
# MockRetriever
# ---------------------------------------------------------------------------

class TestMockRetriever:
    def test_retrieve(self):
        chunks = _sample_chunks(3)
        retriever = MockRetriever(chunks)
        result = retriever.retrieve("test", top_k=2)
        assert len(result) == 2

    def test_retrieve_with_filter(self):
        chunks = _sample_chunks(5)
        retriever = MockRetriever(chunks)
        result = retriever.retrieve("test", filter_metadata={"type": "type0"})
        assert len(result) == 1

    def test_add_chunk(self):
        retriever = MockRetriever()
        retriever.add_chunk(RetrievedChunk(id="x", text="hi", score=0.9))
        assert len(retriever.retrieve("test")) == 1


# ---------------------------------------------------------------------------
# Rerankers
# ---------------------------------------------------------------------------

class TestMockReranker:
    def test_rerank(self):
        chunks = _sample_chunks(5)
        reranker = MockReranker()
        result = reranker.rerank("target0", chunks, top_k=3)
        assert len(result) == 3
        assert all(c.rerank_score is not None for c in result)

    def test_rerank_boosts_relevant(self):
        chunks = [
            RetrievedChunk(id="a", text="information about target", score=0.5),
            RetrievedChunk(id="b", text="unrelated random text", score=0.9),
        ]
        reranker = MockReranker()
        result = reranker.rerank("target information", chunks, top_k=2)
        # 'a' should be boosted due to word overlap
        assert result[0].id == "a"


class TestPassthroughReranker:
    def test_passthrough(self):
        chunks = _sample_chunks(5)
        reranker = PassthroughReranker()
        result = reranker.rerank("q", chunks, top_k=3)
        assert len(result) == 3
        assert result[0].id == chunks[0].id


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

class TestPromptHelpers:
    def test_format_evidence(self):
        chunks = _sample_chunks(2)
        text = _format_evidence(chunks)
        assert "[Evidence 1]" in text
        assert "[Evidence 2]" in text

    def test_format_evidence_with_rerank(self):
        c = RetrievedChunk(id="c1", text="test", score=0.9, rerank_score=0.8)
        text = _format_evidence([c])
        assert "rerank=0.800" in text

    def test_estimate_tokens(self):
        assert _estimate_tokens("a" * 400) == 100

    def test_prompt_templates_exist(self):
        assert "osint_correlation" in PROMPT_TEMPLATES
        assert "threat_assessment" in PROMPT_TEMPLATES
        assert "attribution" in PROMPT_TEMPLATES


# ---------------------------------------------------------------------------
# RAGPipeline — full pipeline
# ---------------------------------------------------------------------------

class TestRAGPipeline:
    def test_basic_query(self):
        pipeline = _make_pipeline()
        response = pipeline.query("find correlations for target.com")
        assert response.query == "find correlations for target.com"
        assert len(response.answer) > 0
        assert response.model == "mock"
        assert "total_ms" in response.metrics

    def test_query_with_chunks(self):
        pipeline = _make_pipeline()
        response = pipeline.query("test")
        assert len(response.chunks) == 3  # rerank_top_k

    def test_query_no_rerank(self):
        pipeline = _make_pipeline(rerank=False)
        response = pipeline.query("test")
        # Without rerank, gets retrieval_top_k (10) capped at available (5)
        assert len(response.chunks) == 5

    def test_query_empty_chunks(self):
        pipeline = _make_pipeline(chunks=[])
        response = pipeline.query("test")
        assert "No relevant evidence" in response.answer

    def test_query_with_filter(self):
        pipeline = _make_pipeline()
        response = pipeline.query("test", filter_metadata={"type": "type0"})
        # Only 1 chunk matches filter
        assert len(response.chunks) <= 3

    def test_query_with_template(self):
        pipeline = _make_pipeline()
        response = pipeline.query("test", template="threat_assessment")
        assert len(response.answer) > 0

    def test_metrics(self):
        pipeline = _make_pipeline()
        response = pipeline.query("test")
        assert "retrieval_ms" in response.metrics
        assert "rerank_ms" in response.metrics
        assert "generation_ms" in response.metrics
        assert response.metrics["total_ms"] >= 0

    def test_set_retriever(self):
        pipeline = _make_pipeline()
        new_retriever = MockRetriever([
            RetrievedChunk(id="new", text="new chunk", score=0.99)
        ])
        pipeline.set_retriever(new_retriever)
        response = pipeline.query("test")
        assert any(c.id == "new" for c in response.chunks)

    def test_set_reranker(self):
        pipeline = _make_pipeline()
        pipeline.set_reranker(PassthroughReranker())
        response = pipeline.query("test")
        assert len(response.chunks) == 3

    def test_set_llm(self):
        pipeline = _make_pipeline()
        pipeline.set_llm(MockLLMBackend())
        response = pipeline.query("test")
        assert response.model == "mock"

    def test_config_property(self):
        pipeline = _make_pipeline()
        assert pipeline.config.llm_provider == LLMProvider.MOCK

    def test_response_to_dict(self):
        pipeline = _make_pipeline()
        response = pipeline.query("test")
        d = response.to_dict()
        assert isinstance(d, dict)
        assert "query" in d
        assert "answer" in d
        assert "chunks" in d
