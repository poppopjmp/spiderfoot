"""Tests for spiderfoot.result_cache."""

import time
import pytest
from spiderfoot.result_cache import (
    EvictionPolicy,
    CacheEntry,
    CacheStats,
    ResultCache,
    ScanResultCache,
)


class TestCacheEntry:
    def test_defaults(self):
        e = CacheEntry(key="k", value="v")
        assert e.key == "k"
        assert e.value == "v"
        assert e.access_count == 0
        assert e.ttl_seconds == 300.0
        assert not e.is_expired

    def test_touch(self):
        e = CacheEntry(key="k", value="v")
        old_accessed = e.last_accessed
        time.sleep(0.01)
        e.touch()
        assert e.access_count == 1
        assert e.last_accessed >= old_accessed

    def test_expired(self):
        e = CacheEntry(key="k", value="v", ttl_seconds=0.01)
        time.sleep(0.02)
        assert e.is_expired

    def test_to_dict(self):
        e = CacheEntry(key="k", value="v")
        d = e.to_dict()
        assert d["key"] == "k"
        assert "created_at" in d
        assert "expired" in d
        assert d["access_count"] == 0


class TestCacheStats:
    def test_defaults(self):
        s = CacheStats()
        assert s.hits == 0
        assert s.misses == 0
        assert s.total_requests == 0
        assert s.hit_rate == 0.0

    def test_hit_rate(self):
        s = CacheStats(hits=3, misses=1)
        assert s.hit_rate == 0.75

    def test_reset(self):
        s = CacheStats(hits=5, misses=2, evictions=1)
        s.reset()
        assert s.hits == 0
        assert s.misses == 0
        assert s.evictions == 0

    def test_to_dict(self):
        s = CacheStats(hits=10, misses=5)
        d = s.to_dict()
        assert d["hits"] == 10
        assert d["hit_rate"] == 0.6667


class TestResultCache:
    def test_set_and_get(self):
        c = ResultCache()
        c.set("a", 42)
        assert c.get("a") == 42

    def test_get_missing(self):
        c = ResultCache()
        assert c.get("missing") is None
        assert c.get("missing", "default") == "default"

    def test_delete(self):
        c = ResultCache()
        c.set("a", 1)
        assert c.delete("a") is True
        assert c.get("a") is None
        assert c.delete("a") is False

    def test_has(self):
        c = ResultCache()
        c.set("a", 1)
        assert c.has("a")
        assert not c.has("b")

    def test_clear(self):
        c = ResultCache()
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.size() == 0

    def test_ttl_expiry(self):
        c = ResultCache(default_ttl=0.01)
        c.set("a", 1)
        time.sleep(0.02)
        assert c.get("a") is None
        assert c.stats.expirations >= 1

    def test_custom_ttl(self):
        c = ResultCache(default_ttl=300)
        c.set("short", 1, ttl=0.01)
        time.sleep(0.02)
        assert c.get("short") is None

    def test_lru_eviction(self):
        c = ResultCache(max_size=2, eviction_policy=EvictionPolicy.LRU)
        c.set("a", 1)
        time.sleep(0.01)
        c.set("b", 2)
        c.get("a")  # access a, making b the LRU
        c.set("c", 3)  # should evict b
        assert c.get("a") == 1
        assert c.get("b") is None
        assert c.get("c") == 3

    def test_fifo_eviction(self):
        c = ResultCache(max_size=2, eviction_policy=EvictionPolicy.FIFO)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)  # should evict a (first in)
        assert c.get("a") is None
        assert c.get("b") == 2
        assert c.get("c") == 3

    def test_lfu_eviction(self):
        c = ResultCache(max_size=2, eviction_policy=EvictionPolicy.LFU)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")  # a has 1 access, b has 0
        c.set("c", 3)  # should evict b (least frequently used)
        assert c.get("a") == 1
        assert c.get("b") is None
        assert c.get("c") == 3

    def test_stats_tracking(self):
        c = ResultCache()
        c.set("a", 1)
        c.get("a")
        c.get("missing")
        assert c.stats.sets == 1
        assert c.stats.hits == 1
        assert c.stats.misses == 1

    def test_keys(self):
        c = ResultCache()
        c.set("a", 1)
        c.set("b", 2)
        assert sorted(c.keys()) == ["a", "b"]

    def test_purge_expired(self):
        c = ResultCache(default_ttl=0.01)
        c.set("a", 1)
        c.set("b", 2)
        time.sleep(0.02)
        c.set("c", 3, ttl=300)  # this one stays
        removed = c.purge_expired()
        assert removed == 2
        assert c.size() == 1

    def test_get_or_set(self):
        c = ResultCache()
        calls = []

        def factory():
            calls.append(1)
            return 42

        assert c.get_or_set("k", factory) == 42
        assert c.get_or_set("k", factory) == 42  # cached, factory not called again
        assert len(calls) == 1

    def test_make_key(self):
        c = ResultCache()
        k1 = c._make_key("scan1", "module1")
        k2 = c._make_key("scan1", "module1")
        k3 = c._make_key("scan1", "module2")
        assert k1 == k2
        assert k1 != k3

    def test_update_existing(self):
        c = ResultCache()
        c.set("a", 1)
        c.set("a", 2)
        assert c.get("a") == 2
        assert c.stats.sets == 2

    def test_to_dict(self):
        c = ResultCache(max_size=100, default_ttl=60)
        c.set("a", 1)
        d = c.to_dict()
        assert d["max_size"] == 100
        assert d["default_ttl"] == 60
        assert d["current_size"] == 1
        assert "stats" in d
        assert "entries" in d

    def test_eviction_stats(self):
        c = ResultCache(max_size=1)
        c.set("a", 1)
        c.set("b", 2)
        assert c.stats.evictions == 1


class TestScanResultCache:
    def test_store_and_get(self):
        sc = ScanResultCache()
        sc.store_result("scan1", "sfp_dns", {"records": ["A"]})
        result = sc.get_result("scan1", "sfp_dns")
        assert result == {"records": ["A"]}

    def test_get_missing(self):
        sc = ScanResultCache()
        assert sc.get_result("scan1", "sfp_dns") is None

    def test_has_result(self):
        sc = ScanResultCache()
        sc.store_result("scan1", "sfp_dns", "val")
        assert sc.has_result("scan1", "sfp_dns")
        assert not sc.has_result("scan1", "sfp_other")

    def test_invalidate_scan(self):
        sc = ScanResultCache()
        sc.store_result("scan1", "sfp_a", 1)
        sc.store_result("scan1", "sfp_b", 2)
        sc.store_result("scan2", "sfp_a", 3)
        sc.invalidate_scan("scan1")
        assert sc.get_result("scan1", "sfp_a") is None
        assert sc.get_result("scan1", "sfp_b") is None
        assert sc.get_result("scan2", "sfp_a") == 3

    def test_invalidate_module(self):
        sc = ScanResultCache()
        sc.store_result("scan1", "sfp_dns", 1)
        sc.store_result("scan2", "sfp_dns", 2)
        sc.store_result("scan1", "sfp_other", 3)
        sc.invalidate_module("sfp_dns")
        assert sc.get_result("scan1", "sfp_dns") is None
        assert sc.get_result("scan2", "sfp_dns") is None
        assert sc.get_result("scan1", "sfp_other") == 3

    def test_clear(self):
        sc = ScanResultCache()
        sc.store_result("s1", "m1", 1)
        sc.clear()
        assert sc.size() == 0

    def test_stats(self):
        sc = ScanResultCache()
        sc.store_result("s1", "m1", 1)
        sc.get_result("s1", "m1")
        sc.get_result("s1", "missing")
        assert sc.stats.hits == 1
        assert sc.stats.misses == 1

    def test_to_dict(self):
        sc = ScanResultCache()
        d = sc.to_dict()
        assert d["type"] == "ScanResultCache"
        assert "stats" in d
