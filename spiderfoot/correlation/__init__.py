# -*- coding: utf-8 -*-
"""SpiderFoot correlation package — all correlation engines consolidated."""

from __future__ import annotations

from .vector_collection_manager import (
    CollectionManagerConfig,
    VectorCollectionManager,
    get_collection_manager,
)

__all__ = [
    "event_enricher",
    "multidim",
    "result_aggregator",
    "rule_executor",
    "rule_loader",
    "vector",
    "vector_collection_manager",
    # Direct re-exports
    "CollectionManagerConfig",
    "VectorCollectionManager",
    "get_collection_manager",
]
