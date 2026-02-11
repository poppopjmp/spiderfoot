"""Backward-compatibility shim for cache_service.py.

This module re-exports from services/cache_service.py for backward compatibility.
"""

from __future__ import annotations

from .services.cache_service import (
    CacheBackend,
    CacheConfig,
    CacheService,
    MemoryCache,
    FileCache,
    RedisCache,
    create_cache,
    create_cache_from_config,
)

__all__ = [
    "CacheBackend",
    "CacheConfig",
    "CacheService",
    "MemoryCache",
    "FileCache",
    "RedisCache",
    "create_cache",
    "create_cache_from_config",
]
