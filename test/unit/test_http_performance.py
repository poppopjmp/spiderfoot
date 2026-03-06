"""
Tests for HTTP/network performance improvements (Phase 2, Cycles 54-56, 59).

Cycle 54: httpx connection pooling for internal service calls 
Cycle 55: httpx-based internal_fetch replacing requests for service calls
Cycle 56: HTTP response caching for idempotent requests
Cycle 59: Adaptive request backoff on 429 responses
"""
from __future__ import annotations

import hashlib
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# -----------------------------------------------------------------------
# Cycle 54 — httpx connection pooling
# -----------------------------------------------------------------------


class TestHttpxConnectionPooling(unittest.TestCase):
    """Cycle 54: httpx.Client with configurable connection limits."""

    def setUp(self):
        # Reset the module-level client
        from spiderfoot.sflib import network
        network.close_internal_http_client()

    def tearDown(self):
        from spiderfoot.sflib import network
        network.close_internal_http_client()

    def test_client_created_with_limits(self):
        """Client should be created with connection pool limits."""
        from spiderfoot.sflib.network import get_internal_http_client
        client = get_internal_http_client(
            max_connections=50,
            max_keepalive_connections=10,
        )
        self.assertIsNotNone(client)
        self.assertFalse(client.is_closed)

    def test_client_singleton(self):
        """get_internal_http_client should return the same instance."""
        from spiderfoot.sflib.network import get_internal_http_client
        c1 = get_internal_http_client()
        c2 = get_internal_http_client()
        self.assertIs(c1, c2)

    def test_close_and_recreate(self):
        """After close, a new client should be created."""
        from spiderfoot.sflib.network import (
            get_internal_http_client,
            close_internal_http_client,
        )
        c1 = get_internal_http_client()
        close_internal_http_client()
        c2 = get_internal_http_client()
        self.assertIsNot(c1, c2)

    def test_client_has_user_agent(self):
        """Client should have SpiderFoot-Internal user agent."""
        from spiderfoot.sflib.network import get_internal_http_client
        client = get_internal_http_client()
        self.assertIn("SpiderFoot-Internal", client.headers.get("user-agent", ""))

    def test_client_follows_redirects(self):
        """Client should follow redirects by default."""
        from spiderfoot.sflib.network import get_internal_http_client
        client = get_internal_http_client()
        self.assertTrue(client.follow_redirects)

    def test_double_close_safe(self):
        """Closing an already-closed client should not raise."""
        from spiderfoot.sflib.network import (
            get_internal_http_client,
            close_internal_http_client,
        )
        get_internal_http_client()
        close_internal_http_client()
        close_internal_http_client()  # should not raise

    def test_thread_safety(self):
        """Multiple threads requesting the client should get the same instance."""
        from spiderfoot.sflib.network import get_internal_http_client
        results = []

        def get_client():
            results.append(id(get_internal_http_client()))

        threads = [threading.Thread(target=get_client) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(set(results)), 1)


# -----------------------------------------------------------------------
# Cycle 55 — internal_fetch with httpx
# -----------------------------------------------------------------------


class TestInternalFetch(unittest.TestCase):
    """Cycle 55: internal_fetch() uses httpx for service calls."""

    def setUp(self):
        from spiderfoot.sflib import network
        network.close_internal_http_client()

    def tearDown(self):
        from spiderfoot.sflib import network
        network.close_internal_http_client()

    def test_empty_url_returns_empty_result(self):
        """Empty URL should return default result dict."""
        from spiderfoot.sflib.network import internal_fetch
        result = internal_fetch("")
        self.assertIsNone(result["code"])

    def test_result_dict_shape(self):
        """Result dict should have standard keys."""
        from spiderfoot.sflib.network import internal_fetch
        result = internal_fetch("")
        for key in ("code", "status", "content", "headers", "realurl"):
            self.assertIn(key, result)

    @patch("spiderfoot.sflib.network.get_internal_http_client")
    def test_get_request(self, mock_get_client):
        """GET request should work via httpx."""
        from spiderfoot.sflib.network import internal_fetch
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.reason_phrase = "OK"
        mock_resp.text = '{"status": "ok"}'
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.url = "http://internal:8080/health"

        mock_client = MagicMock()
        mock_client.request.return_value = mock_resp
        mock_get_client.return_value = mock_client

        result = internal_fetch("http://internal:8080/health")
        self.assertEqual(result["code"], "200")
        self.assertEqual(result["content"], '{"status": "ok"}')
        mock_client.request.assert_called_once()

    @patch("spiderfoot.sflib.network.get_internal_http_client")
    def test_post_with_json(self, mock_get_client):
        """POST with JSON body should pass json kwarg."""
        from spiderfoot.sflib.network import internal_fetch
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.reason_phrase = "Created"
        mock_resp.text = "{}"
        mock_resp.headers = {}
        mock_resp.url = "http://svc/create"

        mock_client = MagicMock()
        mock_client.request.return_value = mock_resp
        mock_get_client.return_value = mock_client

        result = internal_fetch(
            "http://svc/create",
            method="POST",
            json={"key": "value"},
        )
        self.assertEqual(result["code"], "201")
        call_kwargs = mock_client.request.call_args
        self.assertEqual(call_kwargs[1]["json"], {"key": "value"})

    @patch("spiderfoot.sflib.network.get_internal_http_client")
    def test_request_exception_handled(self, mock_get_client):
        """Network errors should be logged, not raised."""
        from spiderfoot.sflib.network import internal_fetch
        mock_client = MagicMock()
        mock_client.request.side_effect = ConnectionError("refused")
        mock_get_client.return_value = mock_client

        result = internal_fetch("http://down-service:8080/api")
        self.assertIsNone(result["code"])


# -----------------------------------------------------------------------
# Cycle 56 — HTTP response caching
# -----------------------------------------------------------------------


class TestHttpResponseCache(unittest.TestCase):
    """Cycle 56: Scan-scoped HTTP response cache with TTL."""

    def test_cache_miss(self):
        """Uncached URL should return None."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60)
        self.assertIsNone(cache.get("https://example.com/uncached"))

    def test_cache_hit(self):
        """Cached response should be retrievable."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60)
        resp = {"code": "200", "content": "test"}
        cache.put("https://example.com/data", resp)
        cached = cache.get("https://example.com/data")
        self.assertEqual(cached, resp)

    def test_cache_different_urls(self):
        """Different URLs should have independent cache entries."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60)
        cache.put("https://a.com", {"code": "200", "content": "a"})
        cache.put("https://b.com", {"code": "200", "content": "b"})
        self.assertEqual(cache.get("https://a.com")["content"], "a")
        self.assertEqual(cache.get("https://b.com")["content"], "b")

    def test_cache_ttl_expiry(self):
        """Entries should expire after TTL."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=1)
        cache.put("https://expiry.com", {"code": "200", "content": "x"})
        self.assertIsNotNone(cache.get("https://expiry.com"))
        time.sleep(1.1)
        self.assertIsNone(cache.get("https://expiry.com"))

    def test_cache_maxsize(self):
        """Cache should not exceed maxsize."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=300, maxsize=5)
        for i in range(10):
            cache.put(f"https://host{i}.com", {"code": "200", "content": str(i)})
        self.assertLessEqual(cache.size, 5)

    def test_no_cache_errors(self):
        """4xx/5xx responses should NOT be cached."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60)
        cache.put("https://err.com/404", {"code": "404", "content": "nf"})
        self.assertIsNone(cache.get("https://err.com/404"))

        cache.put("https://err.com/500", {"code": "500", "content": "err"})
        self.assertIsNone(cache.get("https://err.com/500"))

    def test_cache_200_ok(self):
        """2xx responses should be cached."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60)
        cache.put("https://ok.com", {"code": "200", "content": "good"})
        self.assertIsNotNone(cache.get("https://ok.com"))

    def test_invalidate(self):
        """invalidate() should remove a specific entry."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60)
        cache.put("https://inv.com", {"code": "200", "content": "x"})
        cache.invalidate("https://inv.com")
        self.assertIsNone(cache.get("https://inv.com"))

    def test_clear(self):
        """clear() should empty all entries."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60)
        cache.put("https://c1.com", {"code": "200", "content": "1"})
        cache.put("https://c2.com", {"code": "200", "content": "2"})
        self.assertEqual(cache.size, 2)
        cache.clear()
        self.assertEqual(cache.size, 0)

    def test_stats(self):
        """stats() should return hit/miss metrics."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60, maxsize=100)
        cache.put("https://stats.com", {"code": "200", "content": "s"})
        cache.get("https://stats.com")  # hit
        cache.get("https://miss.com")   # miss
        stats = cache.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 0.5, places=1)
        self.assertEqual(stats["size"], 1)

    def test_method_differentiation(self):
        """GET and HEAD for same URL should be separate cache entries."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60)
        cache.put("https://m.com", {"code": "200", "content": "get"}, method="GET")
        cache.put("https://m.com", {"code": "200", "content": "head"}, method="HEAD")
        self.assertEqual(cache.get("https://m.com", method="GET")["content"], "get")
        self.assertEqual(cache.get("https://m.com", method="HEAD")["content"], "head")

    def test_extra_key_differentiation(self):
        """Extra key material should differentiate entries."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60)
        cache.put("https://api.com", {"code": "200", "content": "v1"}, extra="key=abc")
        cache.put("https://api.com", {"code": "200", "content": "v2"}, extra="key=xyz")
        self.assertEqual(
            cache.get("https://api.com", extra="key=abc")["content"], "v1"
        )
        self.assertEqual(
            cache.get("https://api.com", extra="key=xyz")["content"], "v2"
        )

    def test_thread_safety(self):
        """Cache should be safe for concurrent access."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60, maxsize=1000)
        errors = []

        def writer(start):
            try:
                for i in range(100):
                    cache.put(
                        f"https://thread{start + i}.com",
                        {"code": "200", "content": str(start + i)},
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i * 100,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertGreater(cache.size, 0)

    def test_empty_response_not_cached(self):
        """None/empty response should not be stored."""
        from spiderfoot.result_cache import HttpResponseCache
        cache = HttpResponseCache(ttl=60)
        cache.put("https://empty.com", None)
        self.assertIsNone(cache.get("https://empty.com"))
        cache.put("https://empty2.com", {})
        self.assertIsNone(cache.get("https://empty2.com"))


# -----------------------------------------------------------------------
# Cycle 59 — Adaptive request backoff
# -----------------------------------------------------------------------


class TestAdaptiveBackoff(unittest.TestCase):
    """Cycle 59: Exponential backoff on 429 responses."""

    def test_no_delay_initially(self):
        """Unknown hosts should have zero delay."""
        from spiderfoot.retry import AdaptiveBackoff
        ab = AdaptiveBackoff()
        self.assertEqual(ab.get_delay("api.example.com"), 0.0)

    def test_first_429_sets_delay(self):
        """First 429 should set initial delay."""
        from spiderfoot.retry import AdaptiveBackoff
        ab = AdaptiveBackoff()
        delay = ab.record_response("api.example.com", 429)
        self.assertGreater(delay, 0.0)

    def test_exponential_increase(self):
        """Consecutive 429s should increase delay exponentially."""
        from spiderfoot.retry import AdaptiveBackoff, AdaptiveBackoffConfig
        config = AdaptiveBackoffConfig(initial_delay=1.0, backoff_factor=2.0)
        ab = AdaptiveBackoff(config)

        d1 = ab.record_response("host.com", 429)
        d2 = ab.record_response("host.com", 429)
        d3 = ab.record_response("host.com", 429)

        self.assertAlmostEqual(d1, 1.0, places=1)
        self.assertAlmostEqual(d2, 2.0, places=1)
        self.assertAlmostEqual(d3, 4.0, places=1)

    def test_max_delay_cap(self):
        """Delay should never exceed max_delay."""
        from spiderfoot.retry import AdaptiveBackoff, AdaptiveBackoffConfig
        config = AdaptiveBackoffConfig(
            initial_delay=1.0, max_delay=5.0, backoff_factor=10.0
        )
        ab = AdaptiveBackoff(config)
        for _ in range(10):
            delay = ab.record_response("maxed.com", 429)
        self.assertLessEqual(delay, 5.0)

    def test_success_halves_delay(self):
        """A successful response should halve the current delay."""
        from spiderfoot.retry import AdaptiveBackoff, AdaptiveBackoffConfig
        config = AdaptiveBackoffConfig(initial_delay=4.0, backoff_factor=1.0)
        ab = AdaptiveBackoff(config)
        ab.record_response("half.com", 429)  # delay = 4.0
        d = ab.record_response("half.com", 200)  # delay = 2.0
        self.assertAlmostEqual(d, 2.0, places=1)

    def test_success_eventually_clears(self):
        """Enough successes should clear backoff state entirely."""
        from spiderfoot.retry import AdaptiveBackoff, AdaptiveBackoffConfig
        config = AdaptiveBackoffConfig(initial_delay=1.0, backoff_factor=1.0)
        ab = AdaptiveBackoff(config)
        ab.record_response("clear.com", 429)
        # Multiple successes to clear
        for _ in range(10):
            ab.record_response("clear.com", 200)
        self.assertEqual(ab.get_delay("clear.com"), 0.0)

    def test_retry_after_header_honoured(self):
        """Retry-After header value should be used as delay."""
        from spiderfoot.retry import AdaptiveBackoff
        ab = AdaptiveBackoff()
        delay = ab.record_response("ra.com", 429, retry_after="30")
        self.assertAlmostEqual(delay, 30.0, places=1)

    def test_retry_after_capped_by_max(self):
        """Retry-After larger than max_delay should be capped."""
        from spiderfoot.retry import AdaptiveBackoff, AdaptiveBackoffConfig
        config = AdaptiveBackoffConfig(max_delay=10.0)
        ab = AdaptiveBackoff(config)
        delay = ab.record_response("big-ra.com", 429, retry_after="999")
        self.assertLessEqual(delay, 10.0)

    def test_503_also_triggers_backoff(self):
        """503 Service Unavailable should also trigger backoff."""
        from spiderfoot.retry import AdaptiveBackoff
        ab = AdaptiveBackoff()
        delay = ab.record_response("svc.com", 503)
        self.assertGreater(delay, 0.0)

    def test_200_on_unknown_host(self):
        """200 on an untracked host should return 0.0."""
        from spiderfoot.retry import AdaptiveBackoff
        ab = AdaptiveBackoff()
        delay = ab.record_response("fresh.com", 200)
        self.assertEqual(delay, 0.0)

    def test_clear_host(self):
        """clear() should remove backoff state for a host."""
        from spiderfoot.retry import AdaptiveBackoff
        ab = AdaptiveBackoff()
        ab.record_response("target.com", 429)
        ab.clear("target.com")
        self.assertEqual(ab.get_delay("target.com"), 0.0)

    def test_clear_all(self):
        """clear() without host should clear everything."""
        from spiderfoot.retry import AdaptiveBackoff
        ab = AdaptiveBackoff()
        ab.record_response("a.com", 429)
        ab.record_response("b.com", 429)
        ab.clear()
        self.assertEqual(ab.get_delay("a.com"), 0.0)
        self.assertEqual(ab.get_delay("b.com"), 0.0)

    def test_per_host_independence(self):
        """Backoff state should be independent per host."""
        from spiderfoot.retry import AdaptiveBackoff
        ab = AdaptiveBackoff()
        ab.record_response("slow.com", 429)
        ab.record_response("slow.com", 429)
        # fast.com should have no delay
        self.assertEqual(ab.get_delay("fast.com"), 0.0)
        self.assertGreater(ab.get_delay("slow.com"), 0.0)

    def test_stats(self):
        """stats() should report tracked hosts and counts."""
        from spiderfoot.retry import AdaptiveBackoff
        ab = AdaptiveBackoff()
        ab.record_response("tracked.com", 429)
        ab.record_response("tracked.com", 429)
        stats = ab.stats()
        self.assertEqual(stats["tracked_hosts"], 1)
        self.assertEqual(stats["hosts"]["tracked.com"]["total_429s"], 2)
        self.assertEqual(stats["hosts"]["tracked.com"]["consecutive_429s"], 2)

    def test_thread_safety(self):
        """Concurrent record_response calls should not crash."""
        from spiderfoot.retry import AdaptiveBackoff
        ab = AdaptiveBackoff()
        errors = []

        def hammer():
            try:
                for i in range(50):
                    ab.record_response("concurrent.com", 429 if i % 3 == 0 else 200)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)

    def test_non_rate_limit_code_ignored(self):
        """Non-429/503 error codes should not trigger backoff."""
        from spiderfoot.retry import AdaptiveBackoff
        ab = AdaptiveBackoff()
        ab.record_response("err.com", 500)
        self.assertEqual(ab.get_delay("err.com"), 0.0)

    def test_config_defaults(self):
        """Default config should have sensible values."""
        from spiderfoot.retry import AdaptiveBackoffConfig
        config = AdaptiveBackoffConfig()
        self.assertEqual(config.initial_delay, 1.0)
        self.assertEqual(config.max_delay, 120.0)
        self.assertEqual(config.backoff_factor, 2.0)
        self.assertIn(429, config.rate_limit_codes)
        self.assertIn(503, config.rate_limit_codes)


if __name__ == "__main__":
    unittest.main()
