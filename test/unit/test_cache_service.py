"""
Tests for the CacheService.
"""

import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.cache_service import (
    CacheBackend,
    CacheConfig,
    CacheService,
    MemoryCache,
    FileCache,
    RedisCache,
    create_cache,
    create_cache_from_config,
)


class TestCacheConfig(unittest.TestCase):
    """Test CacheConfig."""
    
    def test_defaults(self):
        config = CacheConfig()
        self.assertEqual(config.backend, CacheBackend.MEMORY)
        self.assertEqual(config.ttl, 3600)
        self.assertEqual(config.key_prefix, "sf:")
    
    def test_from_sf_config(self):
        sf_opts = {
            "_cache_backend": "redis",
            "_cache_ttl": "7200",
            "_cache_redis_url": "redis://cache:6379/2",
        }
        config = CacheConfig.from_sf_config(sf_opts)
        self.assertEqual(config.backend, CacheBackend.REDIS)
        self.assertEqual(config.ttl, 7200)
        self.assertEqual(config.redis_url, "redis://cache:6379/2")
    
    def test_unknown_backend_defaults(self):
        config = CacheConfig.from_sf_config({"_cache_backend": "invalid"})
        self.assertEqual(config.backend, CacheBackend.FILE)


class TestMemoryCache(unittest.TestCase):
    """Test in-memory cache."""
    
    def setUp(self):
        self.cache = MemoryCache(CacheConfig(
            backend=CacheBackend.MEMORY,
            ttl=60,
            max_size=100,
        ))
    
    def test_put_and_get(self):
        self.cache.put("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")
    
    def test_get_missing_key(self):
        self.assertIsNone(self.cache.get("nonexistent"))
    
    def test_put_dict(self):
        data = {"name": "test", "count": 42}
        self.cache.put("dict_key", data)
        result = self.cache.get("dict_key")
        self.assertEqual(result, data)
    
    def test_put_list(self):
        data = [1, 2, 3, "four"]
        self.cache.put("list_key", data)
        result = self.cache.get("list_key")
        self.assertEqual(result, data)
    
    def test_delete(self):
        self.cache.put("key1", "value1")
        self.assertTrue(self.cache.delete("key1"))
        self.assertIsNone(self.cache.get("key1"))
    
    def test_delete_nonexistent(self):
        self.assertFalse(self.cache.delete("nonexistent"))
    
    def test_exists(self):
        self.cache.put("key1", "value1")
        self.assertTrue(self.cache.exists("key1"))
        self.assertFalse(self.cache.exists("nonexistent"))
    
    def test_clear(self):
        self.cache.put("key1", "val1")
        self.cache.put("key2", "val2")
        count = self.cache.clear()
        self.assertEqual(count, 2)
        self.assertEqual(self.cache.size(), 0)
    
    def test_size(self):
        self.assertEqual(self.cache.size(), 0)
        self.cache.put("key1", "val1")
        self.assertEqual(self.cache.size(), 1)
    
    def test_ttl_expiry(self):
        cache = MemoryCache(CacheConfig(ttl=0))
        cache.put("key1", "val1", ttl=0)  # No expiry
        self.assertEqual(cache.get("key1"), "val1")
        
        # With expiry
        cache2 = MemoryCache(CacheConfig(ttl=1))
        cache2._store["sf:key2"] = (time.time() - 10, "val2")  # Already expired
        self.assertIsNone(cache2.get("key2"))
    
    def test_eviction(self):
        cache = MemoryCache(CacheConfig(max_size=3, ttl=0))
        cache.put("key1", "val1")
        cache.put("key2", "val2")
        cache.put("key3", "val3")
        cache.put("key4", "val4")  # Should evict key1
        self.assertEqual(cache.size(), 3)
    
    def test_stats(self):
        self.cache.put("key1", "val1")
        self.cache.get("key1")  # hit
        self.cache.get("missing")  # miss
        
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["sets"], 1)
        self.assertEqual(stats["hit_rate"], 50.0)
    
    def test_hash_key(self):
        h1 = CacheService.hash_key("test string")
        h2 = CacheService.hash_key("test string")
        h3 = CacheService.hash_key("different string")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)


class TestFileCache(unittest.TestCase):
    """Test file-system cache."""
    
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cache = FileCache(CacheConfig(
            backend=CacheBackend.FILE,
            ttl=60,
            cache_dir=self.tmp_dir,
        ))
    
    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_put_and_get_string(self):
        self.cache.put("key1", "hello world")
        result = self.cache.get("key1")
        self.assertEqual(result, "hello world")
    
    def test_put_and_get_dict(self):
        data = {"name": "test", "count": 42}
        self.cache.put("dict_key", data)
        result = self.cache.get("dict_key")
        self.assertEqual(result, data)
    
    def test_get_missing(self):
        self.assertIsNone(self.cache.get("missing"))
    
    def test_delete(self):
        self.cache.put("key1", "val1")
        self.assertTrue(self.cache.delete("key1"))
        self.assertIsNone(self.cache.get("key1"))
    
    def test_exists(self):
        self.cache.put("key1", "val1")
        self.assertTrue(self.cache.exists("key1"))
        self.assertFalse(self.cache.exists("missing"))
    
    def test_clear(self):
        self.cache.put("key1", "val1")
        self.cache.put("key2", "val2")
        count = self.cache.clear()
        self.assertEqual(count, 2)
        self.assertEqual(self.cache.size(), 0)
    
    def test_size(self):
        self.assertEqual(self.cache.size(), 0)
        self.cache.put("key1", "val1")
        self.assertEqual(self.cache.size(), 1)


class TestFactory(unittest.TestCase):
    """Test cache factory."""
    
    def test_create_memory(self):
        cache = create_cache(CacheConfig(backend=CacheBackend.MEMORY))
        self.assertIsInstance(cache, MemoryCache)
    
    def test_create_file(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            cache = create_cache(CacheConfig(
                backend=CacheBackend.FILE,
                cache_dir=tmp_dir
            ))
            self.assertIsInstance(cache, FileCache)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    
    def test_create_redis(self):
        cache = create_cache(CacheConfig(backend=CacheBackend.REDIS))
        self.assertIsInstance(cache, RedisCache)
    
    def test_create_default(self):
        cache = create_cache()
        self.assertIsInstance(cache, MemoryCache)
    
    def test_create_from_config(self):
        cache = create_cache_from_config({"_cache_backend": "memory"})
        self.assertIsInstance(cache, MemoryCache)


if __name__ == "__main__":
    unittest.main()
