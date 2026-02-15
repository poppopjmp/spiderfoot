"""Cross-encoder reranker service for RAG pipeline.

Provides reranking of retrieved chunks using cross-encoder models
that jointly encode query-document pairs for precise relevance scoring.

Backends:

* **Mock** — word-overlap scoring for testing
* **SentenceTransformer CrossEncoder** — local ``ms-marco-MiniLM-L-6-v2``
* **Cohere** — Cohere Rerank API
* **Jina** — Jina Reranker API
* **LiteLLM** — gateway-routed LLM-based relevance scoring
* **Ollama** — local LLM-based relevance scoring

Features:

* Configurable top-k and score thresholds
* Reciprocal Rank Fusion (RRF) for combining retrieval + rerank scores
* Batch scoring with configurable chunk sizes
* Score normalization (sigmoid / min-max)
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.reranker")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class RerankerProvider(Enum):
    """Enumeration of supported reranker backends."""
    MOCK = "mock"
    CROSS_ENCODER = "cross_encoder"
    COHERE = "cohere"
    JINA = "jina"
    LITELLM = "litellm"
    OLLAMA = "ollama"


class ScoreNormalization(Enum):
    """Enumeration of score normalization methods."""
    NONE = "none"
    SIGMOID = "sigmoid"
    MINMAX = "minmax"


@dataclass
class RerankerConfig:
    """Reranker configuration."""

    provider: RerankerProvider = RerankerProvider.MOCK
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    api_key: str = ""
    api_base: str = ""
    top_k: int = 5
    score_threshold: float = 0.0
    batch_size: int = 32
    normalization: ScoreNormalization = ScoreNormalization.SIGMOID
    rrf_k: int = 60  # Reciprocal Rank Fusion constant
    timeout: float = 30.0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> RerankerConfig:
        """Create a RerankerConfig from environment variables."""
        import os
        e = env or os.environ
        return cls(
            provider=RerankerProvider(e.get("SF_RERANKER_PROVIDER", "mock")),
            model_name=e.get("SF_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
            api_key=e.get("SF_RERANKER_API_KEY", ""),
            api_base=e.get("SF_RERANKER_API_BASE", ""),
            top_k=int(e.get("SF_RERANKER_TOP_K", "5")),
            score_threshold=float(e.get("SF_RERANKER_THRESHOLD", "0.0")),
        )


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class RerankItem:
    """A document to be reranked."""

    id: str
    text: str
    retrieval_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RerankResult:
    """Result of reranking a single document."""

    id: str
    text: str
    retrieval_score: float = 0.0
    rerank_score: float = 0.0
    combined_score: float = 0.0
    retrieval_rank: int = 0
    rerank_rank: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation."""
        return {
            "id": self.id,
            "text": self.text[:200],  # truncate for display
            "retrieval_score": round(self.retrieval_score, 4),
            "rerank_score": round(self.rerank_score, 4),
            "combined_score": round(self.combined_score, 4),
            "retrieval_rank": self.retrieval_rank,
            "rerank_rank": self.rerank_rank,
            "metadata": self.metadata,
        }


@dataclass
class RerankResponse:
    """Full reranking response."""

    query: str
    results: list[RerankResult] = field(default_factory=list)
    model: str = ""
    elapsed_ms: float = 0.0
    input_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation."""
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "model": self.model,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "input_count": self.input_count,
            "output_count": len(self.results),
        }


# ---------------------------------------------------------------------------
# Score normalization
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    """Sigmoid function for score normalization."""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _minmax_normalize(scores: list[float]) -> list[float]:
    """Min-max normalize scores to [0, 1]."""
    if not scores:
        return []
    mn = min(scores)
    mx = max(scores)
    if mn == mx:
        return [0.5] * len(scores)
    return [(s - mn) / (mx - mn) for s in scores]


def normalize_scores(scores: list[float],
                     method: ScoreNormalization) -> list[float]:
    """Normalize a list of scores."""
    if method == ScoreNormalization.NONE:
        return scores
    elif method == ScoreNormalization.SIGMOID:
        return [_sigmoid(s) for s in scores]
    elif method == ScoreNormalization.MINMAX:
        return _minmax_normalize(scores)
    return scores


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    retrieval_ranks: list[int],
    rerank_ranks: list[int],
    k: int = 60,
) -> list[float]:
    """Compute RRF scores combining two rank lists.

    RRF(d) = 1/(k + rank_retrieval(d)) + 1/(k + rank_rerank(d))
    """
    scores = []
    for ret_rank, rer_rank in zip(retrieval_ranks, rerank_ranks):
        rrf = 1.0 / (k + ret_rank) + 1.0 / (k + rer_rank)
        scores.append(rrf)
    return scores


# ---------------------------------------------------------------------------
# Backend ABC
# ---------------------------------------------------------------------------

class RerankerBackend(ABC):
    """Abstract reranker backend."""

    @abstractmethod
    def score(self, query: str, documents: list[str]) -> list[float]:
        """Score query-document pairs, returning raw scores."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        ...


# ---------------------------------------------------------------------------
# Mock backend (word overlap)
# ---------------------------------------------------------------------------

class MockRerankerBackend(RerankerBackend):
    """Mock reranker using word overlap + hashing for testing."""

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Score documents by word overlap with the query."""
        query_words = set(query.lower().split())
        scores = []
        for doc in documents:
            doc_words = set(doc.lower().split())
            if not query_words or not doc_words:
                scores.append(0.0)
                continue
            overlap = len(query_words & doc_words)
            jaccard = overlap / len(query_words | doc_words)
            # Add hash-based component for differentiation
            h = int(hashlib.md5(doc.encode()).hexdigest()[:8], 16)
            noise = (h % 100) / 10000.0
            scores.append(jaccard + noise)
        return scores

    def model_name(self) -> str:
        """Return the model name."""
        return "mock-reranker"


# ---------------------------------------------------------------------------
# CrossEncoder backend (local)
# ---------------------------------------------------------------------------

class CrossEncoderBackend(RerankerBackend):
    """Local cross-encoder via sentence-transformers."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        """Initialize the CrossEncoderBackend."""
        self._model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self) -> Any:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import CrossEncoder
                        self._model = CrossEncoder(self._model_name)
                    except ImportError:
                        log.error("sentence-transformers not installed")
                        self._model = "UNAVAILABLE"
        return self._model

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Score documents using the local cross-encoder model."""
        model = self._get_model()
        if model == "UNAVAILABLE":
            return MockRerankerBackend().score(query, documents)
        pairs = [(query, doc) for doc in documents]
        scores = model.predict(pairs)
        return [float(s) for s in scores]

    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name


# ---------------------------------------------------------------------------
# Cohere API backend
# ---------------------------------------------------------------------------

class CohereRerankerBackend(RerankerBackend):
    """Cohere Rerank API backend."""

    def __init__(self, api_key: str = "", model: str = "rerank-v3.5",
                 timeout: float = 30.0) -> None:
        """Initialize the CohereRerankerBackend."""
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Score documents using the Cohere Rerank API."""
        import urllib.error
        import urllib.request
        url = "https://api.cohere.ai/v1/rerank"
        body = json.dumps({
            "model": self._model,
            "query": query,
            "documents": documents,
            "top_n": len(documents),
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
            log.error("Cohere rerank failed: %s", e)
            return [0.0] * len(documents)

        # Cohere returns results sorted by relevance; reconstruct original order
        scores = [0.0] * len(documents)
        for r in data.get("results", []):
            idx = r.get("index", 0)
            if 0 <= idx < len(scores):
                scores[idx] = r.get("relevance_score", 0.0)
        return scores

    def model_name(self) -> str:
        """Return the model name."""
        return self._model


# ---------------------------------------------------------------------------
# Jina API backend
# ---------------------------------------------------------------------------

class JinaRerankerBackend(RerankerBackend):
    """Jina Reranker API backend."""

    def __init__(self, api_key: str = "", model: str = "jina-reranker-v2-base-multilingual",
                 timeout: float = 30.0) -> None:
        """Initialize the JinaRerankerBackend."""
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Score documents using the Jina Reranker API."""
        import urllib.error
        import urllib.request
        url = "https://api.jina.ai/v1/rerank"
        body = json.dumps({
            "model": self._model,
            "query": query,
            "documents": documents,
            "top_n": len(documents),
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
            log.error("Jina rerank failed: %s", e)
            return [0.0] * len(documents)

        scores = [0.0] * len(documents)
        for r in data.get("results", []):
            idx = r.get("index", 0)
            if 0 <= idx < len(scores):
                scores[idx] = r.get("relevance_score", 0.0)
        return scores

    def model_name(self) -> str:
        """Return the model name."""
        return self._model


# ---------------------------------------------------------------------------
# LiteLLM Gateway backend (rerank via LLM scoring)
# ---------------------------------------------------------------------------

class LiteLLMRerankerBackend(RerankerBackend):
    """Reranker via LiteLLM gateway using LLM-based relevance scoring.

    Uses the LiteLLM proxy to send a scoring prompt to any configured
    LLM model. Each document is scored by asking the LLM to rate its
    relevance to the query on a 0-10 scale.
    """

    def __init__(self, api_key: str = "", api_base: str = "",
                 model: str = "gpt-4o-mini",
                 timeout: float = 30.0) -> None:
        """Initialize the LiteLLM reranker backend."""
        self._api_key = api_key
        self._api_base = (api_base or "http://litellm:4000").rstrip("/")
        self._model = model
        self._timeout = timeout

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Score documents by LLM-based relevance assessment."""
        import urllib.error
        import urllib.request

        scores = []
        for doc in documents:
            prompt = (
                f"Rate the relevance of the following document to the query "
                f"on a scale of 0 to 10. Respond with ONLY a number.\n\n"
                f"Query: {query}\n\nDocument: {doc[:500]}\n\nScore:"
            )
            url = f"{self._api_base}/chat/completions"
            body = json.dumps({
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 5,
                "temperature": 0.0,
            }).encode()
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            req = urllib.request.Request(url, data=body, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    data = json.loads(resp.read().decode())
                content = data["choices"][0]["message"]["content"].strip()
                # Extract numeric score
                score_val = float("".join(c for c in content if c.isdigit() or c == ".") or "0")
                scores.append(min(score_val / 10.0, 1.0))  # normalize to 0-1
            except (urllib.error.URLError, json.JSONDecodeError,
                    OSError, ValueError, KeyError, IndexError) as e:
                log.warning("LiteLLM rerank scoring failed: %s", e)
                scores.append(0.0)
        return scores

    def model_name(self) -> str:
        """Return the model name."""
        return f"litellm/{self._model}"


# ---------------------------------------------------------------------------
# Ollama backend (rerank via local LLM scoring)
# ---------------------------------------------------------------------------

class OllamaRerankerBackend(RerankerBackend):
    """Reranker using Ollama local LLM for relevance scoring.

    Similar to the LiteLLM backend but connects directly to an
    Ollama instance for scoring.
    """

    def __init__(self, model: str = "llama3",
                 api_base: str = "",
                 timeout: float = 60.0) -> None:
        """Initialize the Ollama reranker backend."""
        from spiderfoot.config.constants import DEFAULT_OLLAMA_BASE_URL
        self._model = model
        self._api_base = (api_base or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        self._timeout = timeout

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Score documents using a local Ollama model."""
        import urllib.error
        import urllib.request

        scores = []
        for doc in documents:
            prompt = (
                f"Rate the relevance of the following document to the query "
                f"on a scale of 0 to 10. Respond with ONLY a number.\n\n"
                f"Query: {query}\n\nDocument: {doc[:500]}\n\nScore:"
            )
            # Use Ollama's OpenAI-compatible endpoint
            url = f"{self._api_base}/v1/chat/completions"
            body = json.dumps({
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 5,
                "temperature": 0.0,
            }).encode()
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(url, data=body, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    data = json.loads(resp.read().decode())
                content = data["choices"][0]["message"]["content"].strip()
                score_val = float("".join(c for c in content if c.isdigit() or c == ".") or "0")
                scores.append(min(score_val / 10.0, 1.0))
            except (urllib.error.URLError, json.JSONDecodeError,
                    OSError, ValueError, KeyError, IndexError) as e:
                log.warning("Ollama rerank scoring failed: %s", e)
                scores.append(0.0)
        return scores

    def model_name(self) -> str:
        """Return the model name."""
        return f"ollama/{self._model}"


# ---------------------------------------------------------------------------
# Main reranker service
# ---------------------------------------------------------------------------

class RerankerService:
    """High-level reranking service.

    Usage::

        svc = RerankerService()
        response = svc.rerank("find IP correlations", items)
    """

    def __init__(self, config: RerankerConfig | None = None) -> None:
        """Initialize the RerankerService."""
        self._config = config or RerankerConfig()
        self._backend = self._create_backend()

    def _create_backend(self) -> RerankerBackend:
        cfg = self._config
        if cfg.provider == RerankerProvider.MOCK:
            return MockRerankerBackend()
        elif cfg.provider == RerankerProvider.CROSS_ENCODER:
            return CrossEncoderBackend(cfg.model_name)
        elif cfg.provider == RerankerProvider.COHERE:
            return CohereRerankerBackend(cfg.api_key, cfg.model_name, cfg.timeout)
        elif cfg.provider == RerankerProvider.JINA:
            return JinaRerankerBackend(cfg.api_key, cfg.model_name, cfg.timeout)
        elif cfg.provider == RerankerProvider.LITELLM:
            return LiteLLMRerankerBackend(cfg.api_key, cfg.api_base,
                                          cfg.model_name, cfg.timeout)
        elif cfg.provider == RerankerProvider.OLLAMA:
            return OllamaRerankerBackend(cfg.model_name, cfg.api_base,
                                         cfg.timeout)
        else:
            return MockRerankerBackend()

    def rerank(self, query: str,
               items: list[RerankItem],
               top_k: int | None = None,
               score_threshold: float | None = None,
               ) -> RerankResponse:
        """Rerank items by cross-encoder relevance to query."""
        start = time.time()
        top_k = top_k or self._config.top_k
        threshold = score_threshold if score_threshold is not None else self._config.score_threshold

        if not items:
            return RerankResponse(query=query, model=self._backend.model_name())

        # Assign retrieval ranks
        for i, item in enumerate(items):
            item.retrieval_score = item.retrieval_score or 0.0

        documents = [item.text for item in items]

        # Batch scoring
        raw_scores: list[float] = []
        for batch_start in range(0, len(documents), self._config.batch_size):
            batch = documents[batch_start:batch_start + self._config.batch_size]
            raw_scores.extend(self._backend.score(query, batch))

        # Normalize
        normalized = normalize_scores(raw_scores, self._config.normalization)

        # Build results with ranks
        results: list[RerankResult] = []
        for i, (item, norm_score) in enumerate(zip(items, normalized)):
            results.append(RerankResult(
                id=item.id, text=item.text,
                retrieval_score=item.retrieval_score,
                rerank_score=norm_score,
                retrieval_rank=i + 1,  # original rank
                metadata=item.metadata,
            ))

        # Sort by rerank score
        results.sort(key=lambda r: r.rerank_score, reverse=True)

        # Assign rerank ranks
        for i, r in enumerate(results):
            r.rerank_rank = i + 1

        # Compute RRF combined scores
        ret_ranks = [r.retrieval_rank for r in results]
        rer_ranks = [r.rerank_rank for r in results]
        rrf_scores = reciprocal_rank_fusion(ret_ranks, rer_ranks, self._config.rrf_k)
        for r, rrf in zip(results, rrf_scores):
            r.combined_score = rrf

        # Re-sort by combined score
        results.sort(key=lambda r: r.combined_score, reverse=True)

        # Filter by threshold
        if threshold > 0:
            results = [r for r in results if r.rerank_score >= threshold]

        # Truncate to top_k
        results = results[:top_k]

        elapsed = (time.time() - start) * 1000
        return RerankResponse(
            query=query, results=results,
            model=self._backend.model_name(),
            elapsed_ms=elapsed,
            input_count=len(items),
        )

    # Stats
    def stats(self) -> dict[str, Any]:
        """Return reranker service statistics."""
        return {
            "provider": self._config.provider.value,
            "model": self._backend.model_name(),
            "top_k": self._config.top_k,
            "normalization": self._config.normalization.value,
        }
