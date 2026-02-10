"""Embedding service — text-to-vector abstraction layer.

Provides a unified interface for generating dense vector embeddings
from text, supporting multiple embedding backends:

* **SentenceTransformer** — local models via ``sentence-transformers``
* **OpenAI** — ``text-embedding-3-small/large`` via API
* **HuggingFace API** — inference endpoints
* **Mock** — deterministic embeddings for testing

Features:

* Batch embedding with configurable chunk sizes
* Automatic truncation to model max token length
* Embedding caching for deduplication
* Normalization to unit vectors
* Dimensionality metadata for collection creation
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from spiderfoot.constants import DEFAULT_OPENAI_BASE_URL
from typing import Any, Dict, List, Optional, Tuple

from collections.abc import Sequence

log = logging.getLogger("spiderfoot.embeddings")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class EmbeddingProvider(Enum):
    MOCK = "mock"
    SENTENCE_TRANSFORMER = "sentence_transformer"
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"


@dataclass
class EmbeddingConfig:
    """Embedding service configuration."""

    provider: EmbeddingProvider = EmbeddingProvider.MOCK
    model_name: str = "all-MiniLM-L6-v2"
    dimensions: int = 384
    api_key: str = ""
    api_base: str = ""
    batch_size: int = 32
    max_tokens: int = 512
    normalize: bool = True
    cache_enabled: bool = True
    cache_max_size: int = 10_000
    timeout: float = 30.0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> EmbeddingConfig:
        import os
        e = env or os.environ
        return cls(
            provider=EmbeddingProvider(e.get("SF_EMBEDDING_PROVIDER", "mock")),
            model_name=e.get("SF_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            dimensions=int(e.get("SF_EMBEDDING_DIMENSIONS", "384")),
            api_key=e.get("SF_EMBEDDING_API_KEY", ""),
            api_base=e.get("SF_EMBEDDING_API_BASE", ""),
            batch_size=int(e.get("SF_EMBEDDING_BATCH_SIZE", "32")),
            max_tokens=int(e.get("SF_EMBEDDING_MAX_TOKENS", "512")),
            normalize=e.get("SF_EMBEDDING_NORMALIZE", "true").lower() in ("1", "true"),
            cache_enabled=e.get("SF_EMBEDDING_CACHE", "true").lower() in ("1", "true"),
        )


# ---------------------------------------------------------------------------
# Embedding result
# ---------------------------------------------------------------------------

@dataclass
class EmbeddingResult:
    """Result from embedding one or more texts."""

    vectors: list[list[float]]
    model: str = ""
    dimensions: int = 0
    token_count: int = 0
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self.vectors),
            "model": self.model,
            "dimensions": self.dimensions,
            "token_count": self.token_count,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


# ---------------------------------------------------------------------------
# Provider ABC
# ---------------------------------------------------------------------------

class EmbeddingBackend(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    def embed(self, texts: list[str]) -> EmbeddingResult:
        ...

    @abstractmethod
    def dimensions(self) -> int:
        ...

    @abstractmethod
    def model_name(self) -> str:
        ...


# ---------------------------------------------------------------------------
# Mock (deterministic, testing)
# ---------------------------------------------------------------------------

class MockEmbeddingBackend(EmbeddingBackend):
    """Deterministic mock embeddings for testing.

    Generates consistent embeddings from text hashes so that
    identical text always produces the same vector.
    """

    def __init__(self, dims: int = 384) -> None:
        self._dims = dims

    def embed(self, texts: list[str]) -> EmbeddingResult:
        start = time.time()
        vectors = []
        for text in texts:
            vec = self._text_to_vector(text)
            vectors.append(vec)
        elapsed = (time.time() - start) * 1000
        return EmbeddingResult(
            vectors=vectors, model="mock",
            dimensions=self._dims, elapsed_ms=elapsed,
            token_count=sum(len(t.split()) for t in texts),
        )

    def _text_to_vector(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).hexdigest()
        raw = []
        for i in range(self._dims):
            byte_idx = i % 32
            val = int(h[byte_idx * 2:(byte_idx + 1) * 2], 16) / 255.0
            # Alternate sign for diversity
            if i % 2 == 1:
                val = -val
            raw.append(val)
        return _normalize(raw)

    def dimensions(self) -> int:
        return self._dims

    def model_name(self) -> str:
        return "mock"


# ---------------------------------------------------------------------------
# SentenceTransformer (local)
# ---------------------------------------------------------------------------

class SentenceTransformerBackend(EmbeddingBackend):
    """Local embedding via sentence-transformers library."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2",
                 dims: int = 384) -> None:
        self._model_name = model_name
        self._dims = dims
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self) -> Any:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                        self._model = SentenceTransformer(self._model_name)
                        self._dims = self._model.get_sentence_embedding_dimension()
                    except ImportError:
                        log.error("sentence-transformers not installed, "
                                  "falling back to mock")
                        self._model = "UNAVAILABLE"
        return self._model

    def embed(self, texts: list[str]) -> EmbeddingResult:
        start = time.time()
        model = self._get_model()
        if model == "UNAVAILABLE":
            return MockEmbeddingBackend(self._dims).embed(texts)

        embeddings = model.encode(texts, normalize_embeddings=True)
        vectors = [emb.tolist() for emb in embeddings]
        elapsed = (time.time() - start) * 1000
        return EmbeddingResult(
            vectors=vectors, model=self._model_name,
            dimensions=self._dims, elapsed_ms=elapsed,
            token_count=sum(len(t.split()) for t in texts),
        )

    def dimensions(self) -> int:
        return self._dims

    def model_name(self) -> str:
        return self._model_name


# ---------------------------------------------------------------------------
# OpenAI API
# ---------------------------------------------------------------------------

class OpenAIEmbeddingBackend(EmbeddingBackend):
    """OpenAI embedding API backend."""

    def __init__(self, model: str = "text-embedding-3-small",
                 api_key: str = "", api_base: str = "",
                 dims: int = 1536, timeout: float = 30.0) -> None:
        self._model = model
        self._api_key = api_key
        self._api_base = api_base or DEFAULT_OPENAI_BASE_URL
        self._dims = dims
        self._timeout = timeout

    def embed(self, texts: list[str]) -> EmbeddingResult:
        import urllib.error
        import urllib.request
        start = time.time()

        url = f"{self._api_base}/embeddings"
        body = json.dumps({
            "input": texts,
            "model": self._model,
        }).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            log.error("OpenAI embedding failed: %s", e)
            return EmbeddingResult(vectors=[], model=self._model)

        vectors = [item["embedding"] for item in data.get("data", [])]
        usage = data.get("usage", {})
        elapsed = (time.time() - start) * 1000

        if vectors:
            self._dims = len(vectors[0])

        return EmbeddingResult(
            vectors=vectors, model=self._model,
            dimensions=self._dims, elapsed_ms=elapsed,
            token_count=usage.get("total_tokens", 0),
        )

    def dimensions(self) -> int:
        return self._dims

    def model_name(self) -> str:
        return self._model


# ---------------------------------------------------------------------------
# HuggingFace Inference API
# ---------------------------------------------------------------------------

class HuggingFaceEmbeddingBackend(EmbeddingBackend):
    """HuggingFace Inference API backend."""

    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2",
                 api_key: str = "", dims: int = 384,
                 timeout: float = 30.0) -> None:
        self._model = model
        self._api_key = api_key
        self._dims = dims
        self._timeout = timeout

    def embed(self, texts: list[str]) -> EmbeddingResult:
        import urllib.error
        import urllib.request
        start = time.time()

        url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self._model}"
        body = json.dumps({"inputs": texts}).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                vectors = json.loads(resp.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            log.error("HuggingFace embedding failed: %s", e)
            return EmbeddingResult(vectors=[], model=self._model)

        elapsed = (time.time() - start) * 1000

        if vectors and isinstance(vectors[0], list):
            self._dims = len(vectors[0])

        return EmbeddingResult(
            vectors=vectors, model=self._model,
            dimensions=self._dims, elapsed_ms=elapsed,
            token_count=sum(len(t.split()) for t in texts),
        )

    def dimensions(self) -> int:
        return self._dims

    def model_name(self) -> str:
        return self._model


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _normalize(vec: list[float]) -> list[float]:
    """L2-normalize a vector to unit length."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def _truncate(text: str, max_tokens: int) -> str:
    """Rough word-level truncation."""
    words = text.split()
    if len(words) <= max_tokens:
        return text
    return " ".join(words[:max_tokens])


# ---------------------------------------------------------------------------
# LRU embedding cache
# ---------------------------------------------------------------------------

class _EmbeddingCache:
    """Thread-safe LRU cache for embeddings."""

    def __init__(self, max_size: int = 10_000) -> None:
        self._max = max_size
        self._cache: dict[str, list[float]] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _key(self, text: str, model: str) -> str:
        return hashlib.md5(f"{model}:{text}".encode()).hexdigest()

    def get(self, text: str, model: str) -> list[float] | None:
        k = self._key(text, model)
        with self._lock:
            if k in self._cache:
                self._hits += 1
                return self._cache[k]
            self._misses += 1
            return None

    def put(self, text: str, model: str, vector: list[float]) -> None:
        k = self._key(text, model)
        with self._lock:
            if k in self._cache:
                return
            if len(self._cache) >= self._max:
                oldest = self._order.pop(0)
                self._cache.pop(oldest, None)
            self._cache[k] = vector
            self._order.append(k)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._order.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict[str, int]:
        return {
            "size": len(self._cache),
            "max_size": self._max,
            "hits": self._hits,
            "misses": self._misses,
        }


# ---------------------------------------------------------------------------
# Main embedding service
# ---------------------------------------------------------------------------

class EmbeddingService:
    """High-level embedding service with caching and batching.

    Usage::

        svc = EmbeddingService()
        vectors = svc.embed_texts(["Hello world", "SpiderFoot OSINT"])
        single = svc.embed_text("single query")
    """

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self._config = config or EmbeddingConfig()
        self._backend = self._create_backend()
        self._cache = _EmbeddingCache(self._config.cache_max_size) \
            if self._config.cache_enabled else None

    def _create_backend(self) -> EmbeddingBackend:
        cfg = self._config
        if cfg.provider == EmbeddingProvider.MOCK:
            return MockEmbeddingBackend(cfg.dimensions)
        elif cfg.provider == EmbeddingProvider.SENTENCE_TRANSFORMER:
            return SentenceTransformerBackend(cfg.model_name, cfg.dimensions)
        elif cfg.provider == EmbeddingProvider.OPENAI:
            return OpenAIEmbeddingBackend(
                cfg.model_name, cfg.api_key, cfg.api_base,
                cfg.dimensions, cfg.timeout,
            )
        elif cfg.provider == EmbeddingProvider.HUGGINGFACE:
            return HuggingFaceEmbeddingBackend(
                cfg.model_name, cfg.api_key, cfg.dimensions, cfg.timeout,
            )
        else:
            return MockEmbeddingBackend(cfg.dimensions)

    # Public API
    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string. Returns a vector."""
        result = self.embed_texts([text])
        return result[0] if result else []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts, using cache and batching."""
        if not texts:
            return []

        processed = [_truncate(t, self._config.max_tokens) for t in texts]

        # Check cache for hits
        results: list[list[float] | None] = [None] * len(processed)
        uncached_indices: list[int] = []
        model = self._backend.model_name()

        if self._cache:
            for i, text in enumerate(processed):
                cached = self._cache.get(text, model)
                if cached is not None:
                    results[i] = cached
                else:
                    uncached_indices.append(i)
        else:
            uncached_indices = list(range(len(processed)))

        # Batch-embed uncached texts
        if uncached_indices:
            uncached_texts = [processed[i] for i in uncached_indices]
            batch_size = self._config.batch_size

            all_vectors: list[list[float]] = []
            for batch_start in range(0, len(uncached_texts), batch_size):
                batch = uncached_texts[batch_start:batch_start + batch_size]
                embed_result = self._backend.embed(batch)
                for vec in embed_result.vectors:
                    if self._config.normalize:
                        vec = _normalize(vec)
                    all_vectors.append(vec)

            for vec_idx, orig_idx in enumerate(uncached_indices):
                if vec_idx < len(all_vectors):
                    results[orig_idx] = all_vectors[vec_idx]
                    if self._cache:
                        self._cache.put(processed[orig_idx], model,
                                        all_vectors[vec_idx])

        return [v for v in results if v is not None]

    # Metadata
    @property
    def dimensions(self) -> int:
        return self._backend.dimensions()

    @property
    def model(self) -> str:
        return self._backend.model_name()

    @property
    def provider(self) -> EmbeddingProvider:
        return self._config.provider

    # Cache management
    def clear_cache(self) -> None:
        if self._cache:
            self._cache.clear()

    def cache_stats(self) -> dict[str, int]:
        if self._cache:
            return self._cache.stats
        return {"size": 0, "max_size": 0, "hits": 0, "misses": 0}

    # Stats
    def stats(self) -> dict[str, Any]:
        return {
            "provider": self._config.provider.value,
            "model": self.model,
            "dimensions": self.dimensions,
            "cache": self.cache_stats(),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: EmbeddingService | None = None
_instance_lock = threading.Lock()


def get_embedding_service(**kwargs: Any) -> EmbeddingService:
    """Return the global EmbeddingService singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                config = EmbeddingConfig(**kwargs) if kwargs else EmbeddingConfig.from_env()
                _instance = EmbeddingService(config)
    return _instance
