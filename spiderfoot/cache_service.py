"""
CacheService — Standalone caching service.

Extracted from the SpiderFoot god object to provide a pluggable
caching layer with support for file-based, Redis, and in-memory backends.
"""

import hashlib
import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from spiderfoot.constants import DEFAULT_TTL_ONE_HOUR

log = logging.getLogger("spiderfoot.cache_service")


class CacheBackend(str, Enum):
    """Supported cache backends."""
    MEMORY = "memory"      # In-process dict (default, dev)
    FILE = "file"          # File-system cache (legacy SpiderFoot default)
    REDIS = "redis"        # Redis (distributed deployments)


@dataclass 
class CacheConfig:
    """Configuration for the cache service.
    
    Attributes:
        backend: Cache backend type
        ttl: Default TTL in seconds (0 = no expiry) 
        max_size: Max items (memory backend) or max bytes (file backend)
        cache_dir: Directory for file-based cache
        redis_url: Redis connection URL
        key_prefix: Prefix for all cache keys
    """
    backend: CacheBackend = CacheBackend.MEMORY
    ttl: int = DEFAULT_TTL_ONE_HOUR  # 1 hour default
    max_size: int = 10000
    cache_dir: str = ""
    redis_url: str = "redis://localhost:6379/1"
    key_prefix: str = "sf:"
    
    @classmethod
    def from_sf_config(cls, opts: Dict[str, Any]) -> "CacheConfig":
        """Create config from SpiderFoot options dict."""
        backend_str = opts.get("_cache_backend", "file")
        try:
            backend = CacheBackend(backend_str.lower())
        except ValueError:
            backend = CacheBackend.FILE
        
        return cls(
            backend=backend,
            ttl=int(opts.get("_cache_ttl", 3600)),
            max_size=int(opts.get("_cache_maxsize", 10000)),
            cache_dir=opts.get("_cache_dir", ""),
            redis_url=opts.get("_cache_redis_url", "redis://localhost:6379/1"),
        )


class CacheService(ABC):
    """Abstract cache service interface."""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.log = logging.getLogger(f"spiderfoot.cache.{self.config.backend.value}")
        self._hits = 0
        self._misses = 0
        self._sets = 0
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        ...
    
    @abstractmethod
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store a value in the cache.
        
        Args:
            key: Cache key
            value: Value to store
            ttl: TTL in seconds (None = use default)
            
        Returns:
            True if stored successfully
        """
        ...
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted
        """
        ...
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists
        """
        ...
    
    @abstractmethod
    def clear(self) -> int:
        """Clear all cached entries.
        
        Returns:
            Number of entries cleared
        """
        ...
    
    @abstractmethod
    def size(self) -> int:
        """Get the number of cached entries."""
        ...
    
    def _make_key(self, key: str) -> str:
        """Apply key prefix."""
        return f"{self.config.key_prefix}{key}"
    
    @staticmethod
    def hash_key(data: str) -> str:
        """Create a hash of a string for use as a cache key.
        
        Args:
            data: String to hash
            
        Returns:
            SHA-224 hex digest
        """
        return hashlib.sha224(data.encode("utf-8", errors="replace")).hexdigest()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "backend": self.config.backend.value,
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "hit_rate": (self._hits / total * 100) if total > 0 else 0.0,
            "size": self.size(),
        }


class MemoryCache(CacheService):
    """In-memory cache using a thread-safe dict.
    
    Simple LRU-like eviction when max_size is reached.
    Best for single-process deployments and testing.
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        super().__init__(config)
        self._store: Dict[str, tuple] = {}  # key -> (expire_time, value)
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        full_key = self._make_key(key)
        with self._lock:
            entry = self._store.get(full_key)
            if entry is None:
                self._misses += 1
                return None
            
            expire_time, value = entry
            if expire_time > 0 and time.time() > expire_time:
                del self._store[full_key]
                self._misses += 1
                return None
            
            self._hits += 1
            return value
    
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        full_key = self._make_key(key)
        _ttl = ttl if ttl is not None else self.config.ttl
        expire_time = time.time() + _ttl if _ttl > 0 else 0
        
        with self._lock:
            # Evict oldest entries if at capacity
            if len(self._store) >= self.config.max_size and full_key not in self._store:
                self._evict(1)
            
            self._store[full_key] = (expire_time, value)
            self._sets += 1
        
        return True
    
    def delete(self, key: str) -> bool:
        full_key = self._make_key(key)
        with self._lock:
            return self._store.pop(full_key, None) is not None
    
    def exists(self, key: str) -> bool:
        return self.get(key) is not None
    
    def clear(self) -> int:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count
    
    def size(self) -> int:
        with self._lock:
            return len(self._store)
    
    def _evict(self, count: int = 1):
        """Remove oldest entries."""
        if not self._store:
            return
        
        # Remove expired entries first
        now = time.time()
        expired_keys = [
            k for k, (exp, _) in self._store.items()
            if exp > 0 and now > exp
        ]
        for k in expired_keys[:count]:
            del self._store[k]
            count -= 1
        
        # If still need to evict, remove oldest
        if count > 0:
            keys = list(self._store.keys())[:count]
            for k in keys:
                del self._store[k]


class FileCache(CacheService):
    """File-system based cache.
    
    Compatible with the legacy SpiderFoot cachePut/cacheGet pattern.
    Each cache entry is stored as a separate file with SHA-224 hashed name.
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        super().__init__(config)
        self._cache_dir = self.config.cache_dir or os.path.join(
            os.path.expanduser("~"), ".spiderfoot", "cache"
        )
        os.makedirs(self._cache_dir, exist_ok=True)
    
    def _file_path(self, key: str) -> str:
        """Get file path for a cache key."""
        hashed = self.hash_key(self._make_key(key))
        return os.path.join(self._cache_dir, hashed)
    
    def get(self, key: str) -> Optional[Any]:
        path = self._file_path(key)
        
        if not os.path.isfile(path):
            self._misses += 1
            return None
        
        # Check TTL based on file modification time
        if self.config.ttl > 0:
            age = time.time() - os.path.getmtime(path)
            if age > self.config.ttl:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                self._misses += 1
                return None
        
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            # Try JSON deserialization
            try:
                value = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                value = content
            
            self._hits += 1
            return value
        except OSError as e:
            self.log.debug("Cache read error for %s: %s", key, e)
            self._misses += 1
            return None
    
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        path = self._file_path(key)
        
        try:
            # Serialize value
            if isinstance(value, str):
                content = value
            else:
                content = json.dumps(value)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            
            self._sets += 1
            return True
        except (OSError, TypeError, ValueError) as e:
            self.log.error("Cache write error for %s: %s", key, e)
            return False
    
    def delete(self, key: str) -> bool:
        path = self._file_path(key)
        try:
            os.unlink(path)
            return True
        except FileNotFoundError:
            return False
        except OSError as e:
            self.log.error("Cache delete error for %s: %s", key, e)
            return False
    
    def exists(self, key: str) -> bool:
        path = self._file_path(key)
        if not os.path.isfile(path):
            return False
        if self.config.ttl > 0:
            age = time.time() - os.path.getmtime(path)
            if age > self.config.ttl:
                return False
        return True
    
    def clear(self) -> int:
        count = 0
        try:
            for fname in os.listdir(self._cache_dir):
                fpath = os.path.join(self._cache_dir, fname)
                if os.path.isfile(fpath):
                    os.unlink(fpath)
                    count += 1
        except OSError as e:
            self.log.error("Cache clear error: %s", e)
        return count
    
    def size(self) -> int:
        try:
            return len([
                f for f in os.listdir(self._cache_dir)
                if os.path.isfile(os.path.join(self._cache_dir, f))
            ])
        except OSError:
            return 0


class RedisCache(CacheService):
    """Redis-backed distributed cache.
    
    Requires the 'redis' package. Suitable for multi-process
    and distributed deployments.
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        super().__init__(config)
        self._client = None
    
    def _ensure_client(self):
        """Lazily connect to Redis."""
        if self._client is not None:
            return
        
        try:
            import redis
            self._client = redis.Redis.from_url(
                self.config.redis_url,
                decode_responses=True,
            )
            self._client.ping()
            self.log.info("Connected to Redis cache: %s", self.config.redis_url)
        except Exception as e:
            self.log.error("Redis connection failed: %s", e)
            raise
    
    def get(self, key: str) -> Optional[Any]:
        self._ensure_client()
        full_key = self._make_key(key)
        
        try:
            value = self._client.get(full_key)
            if value is None:
                self._misses += 1
                return None
            
            # Try JSON deserialization
            try:
                result = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                result = value
            
            self._hits += 1
            return result
        except Exception as e:
            self.log.error("Redis get error for %s: %s", key, e)
            self._misses += 1
            return None
    
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        self._ensure_client()
        full_key = self._make_key(key)
        _ttl = ttl if ttl is not None else self.config.ttl
        
        try:
            if isinstance(value, str):
                serialized = value
            else:
                serialized = json.dumps(value)
            
            if _ttl > 0:
                self._client.setex(full_key, _ttl, serialized)
            else:
                self._client.set(full_key, serialized)
            
            self._sets += 1
            return True
        except Exception as e:
            self.log.error("Redis set error for %s: %s", key, e)
            return False
    
    def delete(self, key: str) -> bool:
        self._ensure_client()
        full_key = self._make_key(key)
        
        try:
            return self._client.delete(full_key) > 0
        except Exception as e:
            self.log.error("Redis delete error for %s: %s", key, e)
            return False
    
    def exists(self, key: str) -> bool:
        self._ensure_client()
        full_key = self._make_key(key)
        
        try:
            return self._client.exists(full_key) > 0
        except Exception as e:
            self.log.error("Redis exists error for %s: %s", key, e)
            return False
    
    def clear(self) -> int:
        self._ensure_client()
        pattern = f"{self.config.key_prefix}*"
        
        try:
            keys = list(self._client.scan_iter(match=pattern))
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            self.log.error("Redis clear error: %s", e)
            return 0
    
    def size(self) -> int:
        self._ensure_client()
        pattern = f"{self.config.key_prefix}*"
        
        try:
            count = 0
            for _ in self._client.scan_iter(match=pattern):
                count += 1
            return count
        except Exception as e:
            self.log.error("Redis size error: %s", e)
            return 0


def create_cache(config: Optional[CacheConfig] = None) -> CacheService:
    """Factory function to create a cache service.
    
    Args:
        config: Cache configuration
        
    Returns:
        Configured CacheService instance
    """
    if config is None:
        config = CacheConfig()
    
    if config.backend == CacheBackend.MEMORY:
        return MemoryCache(config)
    elif config.backend == CacheBackend.FILE:
        return FileCache(config)
    elif config.backend == CacheBackend.REDIS:
        return RedisCache(config)
    else:
        raise ValueError(f"Unknown cache backend: {config.backend}")


def create_cache_from_config(sf_config: Dict[str, Any]) -> CacheService:
    """Create cache from SpiderFoot configuration dict."""
    config = CacheConfig.from_sf_config(sf_config)
    return create_cache(config)
