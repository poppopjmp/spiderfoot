"""Backward-compatibility shim for embedding_service.py.

This module re-exports from services/embedding_service.py for backward compatibility.
"""

from __future__ import annotations

from .services.embedding_service import (
    EmbeddingProvider,
    EmbeddingConfig,
    EmbeddingResult,
    EmbeddingBackend,
    MockEmbeddingBackend,
    SentenceTransformerBackend,
    OpenAIEmbeddingBackend,
    HuggingFaceEmbeddingBackend,
    EmbeddingService,
    get_embedding_service,
)

__all__ = [
    "EmbeddingProvider",
    "EmbeddingConfig",
    "EmbeddingResult",
    "EmbeddingBackend",
    "MockEmbeddingBackend",
    "SentenceTransformerBackend",
    "OpenAIEmbeddingBackend",
    "HuggingFaceEmbeddingBackend",
    "EmbeddingService",
    "get_embedding_service",
]
