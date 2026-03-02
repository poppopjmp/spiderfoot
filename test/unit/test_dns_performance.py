"""
Tests for DNS performance improvements (Phase 2, Cycles 52-53, 57-58).

Cycle 52: Process-scoped DNS cache using cachetools.TTLCache
Cycle 53: DNS prefetching for discovered domains
Cycle 57: DNS wildcard detection caching
Cycle 58: Bulk DNS resolution
"""
from __future__ import annotations

import asyncio
import time
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

from spiderfoot.services.dns_service import DnsService, DnsServiceConfig


# -----------------------------------------------------------------------
# Cycle 52 — TTLCache DNS cache
# -----------------------------------------------------------------------


class TestDnsTTLCache(unittest.TestCase):
    """Cycle 52: DnsService uses cachetools.TTLCache for automatic expiry."""

    def test_cache_is_ttlcache_when_available(self):
        """Cache should be a TTLCache instance when cachetools is installed."""
        from cachetools import TTLCache

        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=60))
        self.assertIsInstance(svc._cache, TTLCache)

    def test_cache_maxsize_respected(self):
        """TTLCache should respect the configured maxsize."""
        svc = DnsService(DnsServiceConfig(
            cache_enabled=True, cache_ttl=300, cache_maxsize=10
        ))
        # Fill beyond maxsize
        for i in range(20):
            svc._cache_set(f"key_{i}", f"val_{i}")
        self.assertLessEqual(svc.cache_size(), 10)

    def test_cache_default_maxsize(self):
        """Default cache_maxsize should be 4096."""
        config = DnsServiceConfig()
        self.assertEqual(config.cache_maxsize, 4096)

    def test_cache_ttl_automatic_expiry(self):
        """Entries should automatically expire after TTL elapses."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=1))
        svc._cache_set("expiry_test", ["1.2.3.4"])
        # Immediately retrievable
        self.assertEqual(svc._cache_get("expiry_test"), ["1.2.3.4"])
        # After TTL
        time.sleep(1.1)
        self.assertIsNone(svc._cache_get("expiry_test"))

    def test_cache_hit_counter(self):
        """Cache hits should be tracked."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=60))
        svc._cache_set("hit_test", ["5.6.7.8"])
        self.assertEqual(svc._cache_hits, 0)
        svc._cache_get("hit_test")
        self.assertEqual(svc._cache_hits, 1)
        svc._cache_get("hit_test")
        self.assertEqual(svc._cache_hits, 2)

    def test_cache_miss_no_increment(self):
        """Cache misses should NOT increment the hit counter."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=60))
        svc._cache_get("nonexistent")
        self.assertEqual(svc._cache_hits, 0)

    def test_cache_disabled_no_store(self):
        """When cache_enabled=False, set/get should be no-ops."""
        svc = DnsService(DnsServiceConfig(cache_enabled=False))
        svc._cache_set("disabled_key", "value")
        self.assertIsNone(svc._cache_get("disabled_key"))

    def test_cache_clear(self):
        """cache_clear() should empty the TTLCache."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
        svc._cache_set("a", [1])
        svc._cache_set("b", [2])
        self.assertEqual(svc.cache_size(), 2)
        svc.cache_clear()
        self.assertEqual(svc.cache_size(), 0)

    def test_resolve_uses_cache(self):
        """Repeated resolve for same host should hit cache."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
        with patch("spiderfoot.services.dns_service.HAS_DNSPYTHON", False):
            svc_nolib = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
            with patch("socket.gethostbyname_ex", return_value=("h", [], ["1.1.1.1"])) as mock_dns:
                # First call
                result1 = svc_nolib.resolve_host("cached.example.com")
                self.assertEqual(result1, ["1.1.1.1"])
                self.assertEqual(mock_dns.call_count, 1)
                # Second call should use cache
                result2 = svc_nolib.resolve_host("cached.example.com")
                self.assertEqual(result2, ["1.1.1.1"])
                # Socket should NOT be called again
                self.assertEqual(mock_dns.call_count, 1)

    def test_stats_include_cache_info(self):
        """Stats dict should include cache metrics."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True))
        svc._cache_set("stat_key", [1])
        svc._cache_get("stat_key")
        stats = svc.stats()
        self.assertEqual(stats["cache_size"], 1)
        self.assertEqual(stats["cache_hits"], 1)
        self.assertTrue(stats["cache_enabled"])

    def test_fallback_dict_when_cachetools_missing(self):
        """When cachetools is not importable, fall back to plain dict."""
        with patch("spiderfoot.services.dns_service.HAS_CACHETOOLS", False):
            svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=60))
            self.assertNotIsInstance(svc._cache, type(None))
            # Should still work as a dict
            svc._cache_set("fallback_key", ["9.8.7.6"])
            self.assertEqual(svc._cache_get("fallback_key"), ["9.8.7.6"])


# -----------------------------------------------------------------------
# Cycle 53 — DNS prefetching
# -----------------------------------------------------------------------


class TestDnsPrefetching(unittest.TestCase):
    """Cycle 53: Pre-resolve discovered domains into cache."""

    def test_prefetch_populates_cache(self):
        """prefetch() should resolve hostnames into the cache."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
        with patch.object(svc, "resolve", return_value=["1.2.3.4"]) as mock_resolve:
            svc.prefetch(["a.example.com", "b.example.com"])
            self.assertEqual(mock_resolve.call_count, 2)

    def test_prefetch_skips_already_cached(self):
        """prefetch() should skip hostnames already in cache."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
        # Pre-populate cache
        svc._cache_set("resolve:a.example.com:A", ["1.1.1.1"])
        with patch.object(svc, "resolve", return_value=["2.2.2.2"]) as mock_resolve:
            svc.prefetch(["a.example.com", "b.example.com"])
            # Only b.example.com should be resolved
            mock_resolve.assert_called_once_with("b.example.com", "A")

    def test_prefetch_skips_empty_hostnames(self):
        """prefetch() should skip empty strings and None."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
        with patch.object(svc, "resolve", return_value=[]) as mock_resolve:
            svc.prefetch(["", None, "valid.com"])
            mock_resolve.assert_called_once_with("valid.com", "A")

    def test_prefetch_empty_list(self):
        """prefetch() with empty list should do nothing."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
        with patch.object(svc, "resolve") as mock_resolve:
            svc.prefetch([])
            mock_resolve.assert_not_called()


# -----------------------------------------------------------------------
# Cycle 57 — DNS wildcard detection caching
# -----------------------------------------------------------------------


class TestDnsWildcardCache(unittest.TestCase):
    """Cycle 57: Wildcard detection results cached per-domain."""

    def test_wildcard_cached_on_first_call(self):
        """First check_wildcard should resolve and cache."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
        with patch.object(svc, "resolve_host", return_value=["1.2.3.4"]):
            result = svc.check_wildcard("example.com")
            self.assertTrue(result)
            # Verify it's cached
            cached = svc._cache_get("wildcard:example.com")
            self.assertTrue(cached)

    def test_wildcard_uses_cache_on_repeat(self):
        """Repeated check_wildcard should NOT re-resolve."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
        with patch.object(svc, "resolve_host", return_value=[]) as mock_resolve:
            svc.check_wildcard("no-wildcard.com")
            call_count_after_first = mock_resolve.call_count
            # Second call
            svc.check_wildcard("no-wildcard.com")
            # Should NOT have called resolve_host again
            self.assertEqual(mock_resolve.call_count, call_count_after_first)

    def test_wildcard_false_cached(self):
        """Non-wildcard domains should also cache as False."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
        with patch.object(svc, "resolve_host", return_value=[]):
            result = svc.check_wildcard("nowildcard.com")
            self.assertFalse(result)
            cached = svc._cache_get("wildcard:nowildcard.com")
            self.assertFalse(cached)

    def test_wildcard_different_domains_independent(self):
        """Different domains should have independent wildcard cache entries."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
        with patch.object(svc, "resolve_host", side_effect=[["1.2.3.4"], []]):
            self.assertTrue(svc.check_wildcard("has-wildcard.com"))
            self.assertFalse(svc.check_wildcard("no-wildcard.com"))


class TestNetworkWildcardCache(unittest.TestCase):
    """Cycle 57: Standalone checkDnsWildcard also caches."""

    def setUp(self):
        # Clear the module-level cache before each test
        from spiderfoot.sflib import network
        network._wildcard_cache.clear()

    def test_wildcard_cache_populated(self):
        """checkDnsWildcard should cache its result."""
        from spiderfoot.sflib.network import checkDnsWildcard, _wildcard_cache
        with patch("spiderfoot.sflib.network.resolveHost", return_value=["1.2.3.4"]):
            result = checkDnsWildcard("cached-domain.com")
            self.assertTrue(result)
            self.assertIn("cached-domain.com", _wildcard_cache)

    def test_wildcard_cache_avoids_repeat_query(self):
        """Repeated calls should use cached result."""
        from spiderfoot.sflib.network import checkDnsWildcard
        with patch("spiderfoot.sflib.network.resolveHost", return_value=[]) as mock_resolve:
            checkDnsWildcard("repeat-domain.com")
            first_count = mock_resolve.call_count
            checkDnsWildcard("repeat-domain.com")
            self.assertEqual(mock_resolve.call_count, first_count)

    def test_wildcard_empty_target(self):
        """Empty target should return False without caching."""
        from spiderfoot.sflib.network import checkDnsWildcard
        self.assertFalse(checkDnsWildcard(""))


# -----------------------------------------------------------------------
# Cycle 58 — Bulk DNS resolution
# -----------------------------------------------------------------------


class TestBulkDnsResolution(unittest.TestCase):
    """Cycle 58: Resolve multiple hostnames in batches."""

    def test_bulk_resolve_basic(self):
        """bulk_resolve should return a dict of hostname→IPs."""
        svc = DnsService(DnsServiceConfig(cache_enabled=False))
        with patch.object(svc, "resolve", return_value=["1.1.1.1"]):
            results = svc.bulk_resolve(["a.com", "b.com", "c.com"])
            self.assertEqual(len(results), 3)
            for host in ["a.com", "b.com", "c.com"]:
                self.assertEqual(results[host], ["1.1.1.1"])

    def test_bulk_resolve_empty_list(self):
        """Empty hostnames list should return empty dict."""
        svc = DnsService(DnsServiceConfig(cache_enabled=False))
        results = svc.bulk_resolve([])
        self.assertEqual(results, {})

    def test_bulk_resolve_skips_empty_strings(self):
        """Empty/None hostnames should be skipped."""
        svc = DnsService(DnsServiceConfig(cache_enabled=False))
        with patch.object(svc, "resolve", return_value=["1.1.1.1"]):
            results = svc.bulk_resolve(["a.com", "", None, "b.com"])
            self.assertEqual(len(results), 2)
            self.assertIn("a.com", results)
            self.assertIn("b.com", results)

    def test_bulk_resolve_uses_cache(self):
        """Bulk resolve should benefit from cache hits."""
        svc = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
        svc._cache_set("resolve:a.com:A", ["1.1.1.1"])
        with patch("spiderfoot.services.dns_service.HAS_DNSPYTHON", False):
            svc2 = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=300))
            svc2._cache_set("resolve:a.com:A", ["1.1.1.1"])
            with patch("socket.gethostbyname_ex", return_value=("h", [], ["2.2.2.2"])) as mock_sock:
                results = svc2.bulk_resolve(["a.com", "b.com"])
                # a.com from cache, b.com from socket
                self.assertEqual(results["a.com"], ["1.1.1.1"])
                self.assertEqual(results["b.com"], ["2.2.2.2"])
                # Socket should only be called for b.com
                self.assertEqual(mock_sock.call_count, 1)

    def test_bulk_resolve_aaaa(self):
        """bulk_resolve with AAAA record type should work."""
        svc = DnsService(DnsServiceConfig(cache_enabled=False))
        with patch.object(svc, "resolve", return_value=["::1"]):
            results = svc.bulk_resolve(["v6.example.com"], rdtype="AAAA")
            self.assertEqual(results["v6.example.com"], ["::1"])


# -----------------------------------------------------------------------
# Cycle 58 — Async bulk DNS resolution
# -----------------------------------------------------------------------


class TestAsyncBulkDnsResolution(unittest.TestCase):
    """Cycle 58: async_bulk_resolve uses asyncio.gather for parallel resolution."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_async_bulk_resolve_basic(self):
        """async_bulk_resolve should return hostname→IPs dict."""
        from spiderfoot.sflib.async_network import async_bulk_resolve
        with patch(
            "spiderfoot.sflib.async_network.async_resolve_host",
            new_callable=AsyncMock,
            return_value=["1.2.3.4"],
        ):
            results = self._run(async_bulk_resolve(["x.com", "y.com"]))
            self.assertEqual(len(results), 2)
            self.assertEqual(results["x.com"], ["1.2.3.4"])

    def test_async_bulk_resolve_empty(self):
        """Empty list should return empty dict."""
        from spiderfoot.sflib.async_network import async_bulk_resolve
        results = self._run(async_bulk_resolve([]))
        self.assertEqual(results, {})

    def test_async_bulk_resolve_handles_exceptions(self):
        """If a single resolution fails, it should return [] for that host."""
        from spiderfoot.sflib.async_network import async_bulk_resolve

        async def flaky_resolve(host):
            if host == "fail.com":
                raise OSError("DNS failure")
            return ["1.1.1.1"]

        with patch(
            "spiderfoot.sflib.async_network.async_resolve_host",
            side_effect=flaky_resolve,
        ):
            results = self._run(async_bulk_resolve(["ok.com", "fail.com"]))
            self.assertEqual(results["ok.com"], ["1.1.1.1"])
            self.assertEqual(results["fail.com"], [])

    def test_async_bulk_resolve_batching(self):
        """With batch_size=2, 5 hosts should be processed in 3 batches."""
        from spiderfoot.sflib.async_network import async_bulk_resolve

        call_count = 0

        async def counting_resolve(host):
            nonlocal call_count
            call_count += 1
            return ["1.1.1.1"]

        with patch(
            "spiderfoot.sflib.async_network.async_resolve_host",
            side_effect=counting_resolve,
        ):
            hosts = [f"host{i}.com" for i in range(5)]
            results = self._run(async_bulk_resolve(hosts, batch_size=2))
            self.assertEqual(len(results), 5)
            self.assertEqual(call_count, 5)

    def test_async_bulk_resolve_aaaa(self):
        """AAAA record type should use async_resolve_host6."""
        from spiderfoot.sflib.async_network import async_bulk_resolve
        with patch(
            "spiderfoot.sflib.async_network.async_resolve_host6",
            new_callable=AsyncMock,
            return_value=["::1"],
        ):
            results = self._run(async_bulk_resolve(["v6.com"], rdtype="AAAA"))
            self.assertEqual(results["v6.com"], ["::1"])


class TestAsyncPrefetch(unittest.TestCase):
    """Cycle 53: async_prefetch calls async_bulk_resolve."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_async_prefetch_calls_bulk(self):
        """async_prefetch should delegate to async_bulk_resolve."""
        from spiderfoot.sflib.async_network import async_prefetch
        with patch(
            "spiderfoot.sflib.async_network.async_bulk_resolve",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_bulk:
            self._run(async_prefetch(["a.com", "b.com"]))
            mock_bulk.assert_called_once_with(
                ["a.com", "b.com"], rdtype="A", batch_size=50
            )


if __name__ == "__main__":
    unittest.main()
