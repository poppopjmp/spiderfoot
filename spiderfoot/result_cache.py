"""Result caching layer for SpiderFoot scan results and module outputs.

Provides configurable TTL-based caching with eviction policies, size limits,
and statistics tracking. Supports both in-memory and serializable caches.
"""

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EvictionPolicy(Enum):
    """Cache eviction strategies."""
    LRU = "lru"       # Least Recently Used
    LFU = "lfu"       # Least Frequently Used
    FIFO = "fifo"     # First In First Out
    TTL = "ttl"       # Expire by TTL only


@dataclass
class CacheEntry:
    """A single cached value with metadata."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl_seconds: float = 300.0  # 5 minutes default

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    def touch(self):
        """Record an access."""
        self.last_accessed = time.time()
        self.access_count += 1

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "ttl_seconds": self.ttl_seconds,
            "expired": self.is_expired,
        }


@dataclass
class CacheStats:
    """Tracks cache performance metrics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    sets: int = 0

    @property
    def total_requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    def reset(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0
        self.sets = 0

    def to_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "sets": self.sets,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 4),
        }


class ResultCache:
    """Thread-safe TTL-based result cache with eviction support.

    Args:
        max_size: Maximum number of entries. 0 = unlimited.
        default_ttl: Default TTL in seconds for new entries.
        eviction_policy: Strategy for removing entries when cache is full.
    """

    _SENTINEL = object()

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,
        eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.eviction_policy = eviction_policy
        self._entries: dict[str, CacheEntry] = {}
        self._insertion_order: list[str] = []  # for FIFO
        self._lock = threading.RLock()
        self._stats = CacheStats()

    @property
    def stats(self) -> CacheStats:
        return self._stats

    def _make_key(self, *args, **kwargs) -> str:
        """Generate a deterministic cache key from arguments."""
        raw = json.dumps({"args": list(args), "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a cached value by key. Returns default if missing or expired."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._stats.misses += 1
                return default
            if entry.is_expired:
                self._remove(key)
                self._stats.expirations += 1
                self._stats.misses += 1
                return default
            entry.touch()
            self._stats.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Store a value in cache. Evicts if at capacity."""
        with self._lock:
            effective_ttl = ttl if ttl is not None else self.default_ttl

            # If key already exists, update in place
            if key in self._entries:
                self._entries[key] = CacheEntry(
                    key=key, value=value, ttl_seconds=effective_ttl
                )
                self._stats.sets += 1
                return

            # Evict if needed
            if self.max_size > 0 and len(self._entries) >= self.max_size:
                self._evict()

            self._entries[key] = CacheEntry(
                key=key, value=value, ttl_seconds=effective_ttl
            )
            self._insertion_order.append(key)
            self._stats.sets += 1

    def delete(self, key: str) -> bool:
        """Remove a specific key. Returns True if key existed."""
        with self._lock:
            return self._remove(key)

    def has(self, key: str) -> bool:
        """Check if key exists and is not expired (without recording a hit)."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                self._remove(key)
                self._stats.expirations += 1
                return False
            return True

    def clear(self):
        """Remove all entries."""
        with self._lock:
            self._entries.clear()
            self._insertion_order.clear()

    def size(self) -> int:
        """Current number of entries (including expired, until next access)."""
        return len(self._entries)

    def keys(self) -> list[str]:
        """Return list of non-expired keys."""
        with self._lock:
            return [k for k, v in self._entries.items() if not v.is_expired]

    def purge_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with self._lock:
            expired_keys = [k for k, v in self._entries.items() if v.is_expired]
            for k in expired_keys:
                self._remove(k)
                self._stats.expirations += 1
            return len(expired_keys)

    def get_or_set(self, key: str, factory, ttl: Optional[float] = None) -> Any:
        """Get value if cached, otherwise call factory() to compute and cache it."""
        val = self.get(key, default=self._SENTINEL)
        if val is not self._SENTINEL:
            return val
        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    def _remove(self, key: str) -> bool:
        if key in self._entries:
            del self._entries[key]
            if key in self._insertion_order:
                self._insertion_order.remove(key)
            return True
        return False

    def _evict(self):
        """Evict one entry based on the eviction policy."""
        if not self._entries:
            return

        victim_key = None

        if self.eviction_policy == EvictionPolicy.LRU:
            victim_key = min(self._entries, key=lambda k: self._entries[k].last_accessed)
        elif self.eviction_policy == EvictionPolicy.LFU:
            victim_key = min(self._entries, key=lambda k: self._entries[k].access_count)
        elif self.eviction_policy == EvictionPolicy.FIFO:
            # Use insertion order
            while self._insertion_order:
                candidate = self._insertion_order[0]
                if candidate in self._entries:
                    victim_key = candidate
                    break
                self._insertion_order.pop(0)
        elif self.eviction_policy == EvictionPolicy.TTL:
            # Evict most-expired (or oldest if none expired)
            expired = [k for k, v in self._entries.items() if v.is_expired]
            if expired:
                victim_key = expired[0]
            else:
                victim_key = min(self._entries, key=lambda k: self._entries[k].created_at)

        if victim_key:
            self._remove(victim_key)
            self._stats.evictions += 1

    def to_dict(self) -> dict:
        """Serialize cache state."""
        with self._lock:
            return {
                "max_size": self.max_size,
                "default_ttl": self.default_ttl,
                "eviction_policy": self.eviction_policy.value,
                "current_size": len(self._entries),
                "stats": self._stats.to_dict(),
                "entries": {k: v.to_dict() for k, v in self._entries.items()},
            }


class ScanResultCache:
    """Specialized cache for scan results, keyed by scan ID + module.

    Wraps ResultCache with scan-specific key generation and namespacing.
    """

    def __init__(self, max_size: int = 5000, default_ttl: float = 600.0):
        self._cache = ResultCache(
            max_size=max_size,
            default_ttl=default_ttl,
            eviction_policy=EvictionPolicy.LRU,
        )

    def _key(self, scan_id: str, module: str, suffix: str = "") -> str:
        parts = [scan_id, module]
        if suffix:
            parts.append(suffix)
        return ":".join(parts)

    def store_result(self, scan_id: str, module: str, result: Any, ttl: Optional[float] = None):
        """Cache a module result for a scan."""
        key = self._key(scan_id, module)
        self._cache.set(key, result, ttl=ttl)

    def get_result(self, scan_id: str, module: str) -> Any:
        """Retrieve cached module result. Returns None if missing."""
        key = self._key(scan_id, module)
        return self._cache.get(key)

    def has_result(self, scan_id: str, module: str) -> bool:
        key = self._key(scan_id, module)
        return self._cache.has(key)

    def invalidate_scan(self, scan_id: str):
        """Remove all cached results for a scan."""
        prefix = scan_id + ":"
        keys = [k for k in self._cache.keys() if k.startswith(prefix)]
        for k in keys:
            self._cache.delete(k)

    def invalidate_module(self, module: str):
        """Remove all cached results for a module across all scans."""
        suffix = ":" + module
        keys = [k for k in self._cache.keys() if k.endswith(suffix)]
        for k in keys:
            self._cache.delete(k)

    @property
    def stats(self) -> CacheStats:
        return self._cache.stats

    def clear(self):
        self._cache.clear()

    def size(self) -> int:
        return self._cache.size()

    def to_dict(self) -> dict:
        return {
            "type": "ScanResultCache",
            **self._cache.to_dict(),
        }
