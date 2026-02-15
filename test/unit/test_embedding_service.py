"""Tests for spiderfoot.embedding_service — text-to-vector embeddings."""
from __future__ import annotations

import math
import pytest
from spiderfoot.services.embedding_service import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    EmbeddingService,
    MockEmbeddingBackend,
    _EmbeddingCache,
    _normalize,
    _truncate,
)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_unit_vector(self):
        v = _normalize([3.0, 4.0])
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-6

    def test_zero_vector(self):
        v = _normalize([0.0, 0.0])
        assert v == [0.0, 0.0]

    def test_already_unit(self):
        v = _normalize([1.0, 0.0])
        assert abs(v[0] - 1.0) < 1e-6


class TestTruncate:
    def test_no_truncation(self):
        assert _truncate("hello world", 10) == "hello world"

    def test_truncation(self):
        text = " ".join(f"w{i}" for i in range(100))
        result = _truncate(text, 10)
        assert len(result.split()) == 10


# ---------------------------------------------------------------------------
# EmbeddingResult
# ---------------------------------------------------------------------------

class TestEmbeddingResult:
    def test_to_dict(self):
        r = EmbeddingResult(vectors=[[1.0, 2.0]], model="test",
                            dimensions=2, elapsed_ms=1.5)
        d = r.to_dict()
        assert d["count"] == 1
        assert d["model"] == "test"
        assert d["elapsed_ms"] == 1.5


# ---------------------------------------------------------------------------
# EmbeddingConfig
# ---------------------------------------------------------------------------

class TestEmbeddingConfig:
    def test_defaults(self):
        cfg = EmbeddingConfig()
        assert cfg.provider == EmbeddingProvider.MOCK
        assert cfg.dimensions == 384

    def test_from_env(self):
        env = {
            "SF_EMBEDDING_PROVIDER": "openai",
            "SF_EMBEDDING_MODEL": "text-embedding-3-small",
            "SF_EMBEDDING_DIMENSIONS": "1536",
            "SF_EMBEDDING_API_KEY": "sk-test",
        }
        cfg = EmbeddingConfig.from_env(env)
        assert cfg.provider == EmbeddingProvider.OPENAI
        assert cfg.model_name == "text-embedding-3-small"
        assert cfg.dimensions == 1536
        assert cfg.api_key == "sk-test"


# ---------------------------------------------------------------------------
# MockEmbeddingBackend
# ---------------------------------------------------------------------------

class TestMockEmbeddingBackend:
    def setup_method(self):
        self.backend = MockEmbeddingBackend(dims=64)

    def test_embed_single(self):
        result = self.backend.embed(["hello world"])
        assert len(result.vectors) == 1
        assert len(result.vectors[0]) == 64
        assert result.model == "mock"
        assert result.dimensions == 64

    def test_embed_batch(self):
        result = self.backend.embed(["a", "b", "c"])
        assert len(result.vectors) == 3

    def test_deterministic(self):
        r1 = self.backend.embed(["test"])
        r2 = self.backend.embed(["test"])
        assert r1.vectors[0] == r2.vectors[0]

    def test_different_texts_different_vectors(self):
        result = self.backend.embed(["foo", "bar"])
        assert result.vectors[0] != result.vectors[1]

    def test_normalized(self):
        result = self.backend.embed(["check norm"])
        vec = result.vectors[0]
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-6

    def test_dimensions(self):
        assert self.backend.dimensions() == 64

    def test_model_name(self):
        assert self.backend.model_name() == "mock"

    def test_token_count(self):
        result = self.backend.embed(["hello world"])
        assert result.token_count == 2


# ---------------------------------------------------------------------------
# Embedding cache
# ---------------------------------------------------------------------------

class TestEmbeddingCache:
    def setup_method(self):
        self.cache = _EmbeddingCache(max_size=3)

    def test_put_and_get(self):
        self.cache.put("hello", "mock", [1.0, 2.0])
        vec = self.cache.get("hello", "mock")
        assert vec == [1.0, 2.0]

    def test_miss(self):
        assert self.cache.get("missing", "mock") is None

    def test_eviction(self):
        self.cache.put("a", "m", [1.0])
        self.cache.put("b", "m", [2.0])
        self.cache.put("c", "m", [3.0])
        self.cache.put("d", "m", [4.0])  # evicts 'a'
        assert self.cache.get("a", "m") is None
        assert self.cache.get("d", "m") == [4.0]

    def test_stats(self):
        self.cache.put("x", "m", [1.0])
        self.cache.get("x", "m")  # hit
        self.cache.get("y", "m")  # miss
        s = self.cache.stats
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["size"] == 1

    def test_clear(self):
        self.cache.put("x", "m", [1.0])
        self.cache.clear()
        assert self.cache.get("x", "m") is None
        assert self.cache.stats["size"] == 0

    def test_duplicate_put(self):
        self.cache.put("x", "m", [1.0])
        self.cache.put("x", "m", [2.0])  # should not overwrite
        assert self.cache.get("x", "m") == [1.0]
        assert self.cache.stats["size"] == 1


# ---------------------------------------------------------------------------
# EmbeddingService
# ---------------------------------------------------------------------------

class TestEmbeddingService:
    def setup_method(self):
        cfg = EmbeddingConfig(
            provider=EmbeddingProvider.MOCK,
            dimensions=64,
            cache_enabled=True,
            cache_max_size=100,
        )
        self.svc = EmbeddingService(cfg)

    def test_embed_text(self):
        vec = self.svc.embed_text("hello world")
        assert len(vec) == 64

    def test_embed_texts(self):
        vecs = self.svc.embed_texts(["a", "b", "c"])
        assert len(vecs) == 3
        assert all(len(v) == 64 for v in vecs)

    def test_embed_empty(self):
        assert self.svc.embed_texts([]) == []

    def test_caching(self):
        self.svc.embed_texts(["cached"])
        stats_after = self.svc.cache_stats()
        assert stats_after["size"] == 1

        self.svc.embed_texts(["cached"])  # should hit cache
        stats_hit = self.svc.cache_stats()
        assert stats_hit["hits"] == 1

    def test_no_cache(self):
        cfg = EmbeddingConfig(
            provider=EmbeddingProvider.MOCK,
            dimensions=64,
            cache_enabled=False,
        )
        svc = EmbeddingService(cfg)
        vec = svc.embed_text("test")
        assert len(vec) == 64
        assert svc.cache_stats()["size"] == 0

    def test_dimensions_property(self):
        assert self.svc.dimensions == 64

    def test_model_property(self):
        assert self.svc.model == "mock"

    def test_provider_property(self):
        assert self.svc.provider == EmbeddingProvider.MOCK

    def test_clear_cache(self):
        self.svc.embed_text("hello")
        self.svc.clear_cache()
        assert self.svc.cache_stats()["size"] == 0

    def test_stats(self):
        s = self.svc.stats()
        assert s["provider"] == "mock"
        assert s["model"] == "mock"
        assert s["dimensions"] == 64
        assert "cache" in s

    def test_batch_processing(self):
        cfg = EmbeddingConfig(
            provider=EmbeddingProvider.MOCK,
            dimensions=64,
            batch_size=2,
        )
        svc = EmbeddingService(cfg)
        vecs = svc.embed_texts(["a", "b", "c", "d", "e"])
        assert len(vecs) == 5

    def test_deterministic(self):
        v1 = self.svc.embed_text("same text")
        self.svc.clear_cache()
        v2 = self.svc.embed_text("same text")
        assert v1 == v2

    def test_different_texts(self):
        v1 = self.svc.embed_text("alpha")
        v2 = self.svc.embed_text("beta")
        assert v1 != v2

    def test_truncation(self):
        long_text = " ".join(f"word{i}" for i in range(1000))
        vec = self.svc.embed_text(long_text)
        assert len(vec) == 64  # should still work
