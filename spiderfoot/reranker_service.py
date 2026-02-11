"""Backward-compatibility shim for reranker_service.py.

This module re-exports from services/reranker_service.py for backward compatibility.
"""

from __future__ import annotations

from .services.reranker_service import (
    RerankerProvider,
    ScoreNormalization,
    RerankerConfig,
    RerankItem,
    RerankResult,
    RerankResponse,
    RerankerBackend,
    MockRerankerBackend,
    CrossEncoderBackend,
    CohereRerankerBackend,
    JinaRerankerBackend,
    RerankerService,
    normalize_scores,
    reciprocal_rank_fusion,
)

__all__ = [
    "RerankerProvider",
    "ScoreNormalization",
    "RerankerConfig",
    "RerankItem",
    "RerankResult",
    "RerankResponse",
    "RerankerBackend",
    "MockRerankerBackend",
    "CrossEncoderBackend",
    "CohereRerankerBackend",
    "JinaRerankerBackend",
    "RerankerService",
    "normalize_scores",
    "reciprocal_rank_fusion",
]
