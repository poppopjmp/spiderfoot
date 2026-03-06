"""Tests for stealth engine integration with fetchUrl — Steps 21-25.

Validates that when a StealthEngine instance is passed to fetchUrl(),
it applies jitter, stealth headers, proxy rotation, and increments the
request counter before the outbound HTTP call.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.sflib.network import fetchUrl, closeSession


class TestFetchUrlStealthIntegration(unittest.TestCase):
    """fetchUrl(stealth_engine=...) wires through all stealth hooks."""

    def tearDown(self):
        closeSession()

    def _make_mock_engine(
        self,
        *,
        headers: dict | None = None,
        proxy: dict | None = None,
    ) -> MagicMock:
        """Build a mock StealthEngine with sensible defaults."""
        engine = MagicMock()
        engine.apply_jitter.return_value = 0.0
        engine.prepare_headers.return_value = headers or {
            "User-Agent": "StealthUA/1.0",
            "Accept-Language": "en-US",
        }
        engine.get_proxy.return_value = proxy
        engine.increment_request_counter.return_value = 1
        return engine

    # ── Without stealth ───────────────────────────────────────────────

    def test_fetchUrl_without_stealth_skips_hooks(self):
        """When stealth_engine is None, no stealth calls happen."""
        with patch("spiderfoot.sflib.network.getSession") as mock_gs:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.reason = "OK"
            mock_resp.content = b"hello"
            mock_resp.headers = {}
            mock_resp.url = "https://example.com"
            mock_gs.return_value.get.return_value = mock_resp

            result = fetchUrl("https://example.com", stealth_engine=None)

        self.assertEqual(result["code"], "200")
        # No stealth calls should have been made — nothing to assert
        # on except that the result is normal.

    # ── With stealth ──────────────────────────────────────────────────

    @patch("spiderfoot.sflib.network.getSession")
    def test_stealth_apply_jitter_called(self, mock_gs):
        """apply_jitter() is called before the request."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.reason = "OK"
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.url = "https://example.com"
        mock_gs.return_value.get.return_value = mock_resp

        engine = self._make_mock_engine()
        fetchUrl("https://example.com", stealth_engine=engine)

        engine.apply_jitter.assert_called_once()

    @patch("spiderfoot.sflib.network.getSession")
    def test_stealth_prepare_headers_called_with_url(self, mock_gs):
        """prepare_headers() receives the target URL."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.reason = "OK"
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.url = "https://target.test"
        mock_gs.return_value.get.return_value = mock_resp

        engine = self._make_mock_engine()
        fetchUrl("https://target.test", stealth_engine=engine)

        engine.prepare_headers.assert_called_once()
        call_kwargs = engine.prepare_headers.call_args
        self.assertEqual(call_kwargs.kwargs["target_url"], "https://target.test")

    @patch("spiderfoot.sflib.network.getSession")
    def test_stealth_headers_used_in_request(self, mock_gs):
        """Stealth-generated headers are forwarded to the session."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.reason = "OK"
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.url = "https://example.com"
        mock_gs.return_value.get.return_value = mock_resp

        stealth_headers = {"User-Agent": "Stealth/2.0", "X-Custom": "abc"}
        engine = self._make_mock_engine(headers=stealth_headers)
        fetchUrl("https://example.com", stealth_engine=engine)

        # The session.get() should have been called with the stealth headers
        call_kwargs = mock_gs.return_value.get.call_args
        self.assertEqual(call_kwargs.kwargs.get("headers"), stealth_headers)

    @patch("spiderfoot.sflib.network.getSession")
    def test_stealth_extra_headers_forwarded(self, mock_gs):
        """Caller-supplied headers are passed as extra_headers to the engine."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.reason = "OK"
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.url = "https://example.com"
        mock_gs.return_value.get.return_value = mock_resp

        caller_headers = {"Authorization": "Bearer tok123"}
        engine = self._make_mock_engine()
        fetchUrl("https://example.com", headers=caller_headers, stealth_engine=engine)

        call_kwargs = engine.prepare_headers.call_args
        self.assertEqual(call_kwargs.kwargs["extra_headers"], caller_headers)

    @patch("spiderfoot.sflib.network.getSession")
    def test_stealth_proxy_forwarded(self, mock_gs):
        """Proxy dict from the engine is forwarded to session.get()."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.reason = "OK"
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.url = "https://example.com"
        mock_gs.return_value.get.return_value = mock_resp

        proxy = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}
        engine = self._make_mock_engine(proxy=proxy)
        fetchUrl("https://example.com", stealth_engine=engine)

        call_kwargs = mock_gs.return_value.get.call_args
        self.assertEqual(call_kwargs.kwargs.get("proxies"), proxy)

    @patch("spiderfoot.sflib.network.getSession")
    def test_stealth_no_proxy_when_none(self, mock_gs):
        """When engine.get_proxy() returns None, no proxies kwarg is set."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.reason = "OK"
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.url = "https://example.com"
        mock_gs.return_value.get.return_value = mock_resp

        engine = self._make_mock_engine(proxy=None)
        fetchUrl("https://example.com", stealth_engine=engine)

        call_kwargs = mock_gs.return_value.get.call_args
        self.assertNotIn("proxies", call_kwargs.kwargs)

    @patch("spiderfoot.sflib.network.getSession")
    def test_stealth_request_counter_incremented(self, mock_gs):
        """increment_request_counter() is called once per request."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.reason = "OK"
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.url = "https://example.com"
        mock_gs.return_value.get.return_value = mock_resp

        engine = self._make_mock_engine()
        fetchUrl("https://example.com", stealth_engine=engine)

        engine.increment_request_counter.assert_called_once()

    @patch("spiderfoot.sflib.network.getSession")
    def test_stealth_engine_failure_does_not_break_fetch(self, mock_gs):
        """If the stealth engine throws, fetchUrl still completes."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.reason = "OK"
        mock_resp.content = b"ok"
        mock_resp.headers = {}
        mock_resp.url = "https://example.com"
        mock_gs.return_value.get.return_value = mock_resp

        engine = MagicMock()
        engine.apply_jitter.side_effect = RuntimeError("jitter boom")

        result = fetchUrl("https://example.com", stealth_engine=engine)

        self.assertEqual(result["code"], "200")
        self.assertEqual(result["content"], "ok")

    @patch("spiderfoot.sflib.network.getSession")
    def test_stealth_works_with_post(self, mock_gs):
        """Stealth hooks fire for POST requests too."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.reason = "Created"
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.url = "https://example.com/api"
        mock_gs.return_value.post.return_value = mock_resp

        engine = self._make_mock_engine()
        result = fetchUrl(
            "https://example.com/api",
            postData="key=val",
            stealth_engine=engine,
        )

        engine.apply_jitter.assert_called_once()
        engine.prepare_headers.assert_called_once()
        self.assertEqual(result["code"], "201")

    @patch("spiderfoot.sflib.network.getSession")
    def test_stealth_works_with_head(self, mock_gs):
        """Stealth hooks fire for HEAD requests too."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.reason = "OK"
        mock_resp.content = b""
        mock_resp.headers = {"Content-Length": "12345"}
        mock_resp.url = "https://example.com"
        mock_gs.return_value.head.return_value = mock_resp

        engine = self._make_mock_engine()
        result = fetchUrl(
            "https://example.com",
            headOnly=True,
            stealth_engine=engine,
        )

        engine.apply_jitter.assert_called_once()
        self.assertEqual(result["code"], "200")


class TestSpiderFootFetchUrlStealth(unittest.TestCase):
    """SpiderFoot.fetchUrl() stealth integration tests.

    - Explicit stealth_engine → forwarded directly to network.fetchUrl()
    - Config-based stealth → uses StealthFetchMiddleware from stealth_integration
    """

    @patch("spiderfoot.sflib.core.fetchUrl")
    def test_core_fetchurl_passes_stealth_engine(self, mock_network_fetch):
        """SpiderFoot().fetchUrl(stealth_engine=e) forwards to network.fetchUrl()."""
        from spiderfoot.sflib.core import SpiderFoot

        mock_network_fetch.return_value = {"code": "200"}
        sf = SpiderFoot.__new__(SpiderFoot)

        engine = MagicMock()
        sf.fetchUrl("https://example.com", stealth_engine=engine)

        call_kwargs = mock_network_fetch.call_args
        self.assertIs(call_kwargs.kwargs.get("stealth_engine"), engine)

    @patch("spiderfoot.sflib.core.fetchUrl")
    def test_auto_stealth_middleware_from_config(self, mock_network_fetch):
        """When opts._stealth_level is set, a StealthFetchMiddleware is created."""
        from spiderfoot.sflib.core import SpiderFoot

        mock_network_fetch.return_value = {
            "code": "200",
            "status": "OK",
            "content": "ok",
            "headers": {},
            "realurl": "https://example.com",
        }
        sf = SpiderFoot.__new__(SpiderFoot)
        sf.opts = {"_stealth_level": "low"}

        sf.fetchUrl("https://example.com")

        # The middleware should have been created and cached
        self.assertIsNotNone(
            getattr(sf, '_stealth_middleware', None),
            "StealthFetchMiddleware should be auto-created from config",
        )
        self.assertIsNotNone(
            getattr(sf, '_stealth_context', None),
            "StealthScanContext should be auto-created from config",
        )

    @patch("spiderfoot.sflib.core.fetchUrl")
    def test_auto_stealth_middleware_cached(self, mock_network_fetch):
        """The auto-created StealthFetchMiddleware is cached across calls."""
        from spiderfoot.sflib.core import SpiderFoot

        mock_network_fetch.return_value = {
            "code": "200",
            "status": "OK",
            "content": "",
            "headers": {},
            "realurl": "https://a.com",
        }
        sf = SpiderFoot.__new__(SpiderFoot)
        sf.opts = {"_stealth_level": "medium"}

        sf.fetchUrl("https://a.com")
        middleware1 = getattr(sf, '_stealth_middleware', None)
        sf.fetchUrl("https://b.com")
        middleware2 = getattr(sf, '_stealth_middleware', None)

        self.assertIs(middleware1, middleware2, "Middleware should be cached and reused")

    @patch("spiderfoot.sflib.core.fetchUrl")
    def test_no_stealth_when_level_none(self, mock_network_fetch):
        """When _stealth_level is 'none', no middleware is created."""
        from spiderfoot.sflib.core import SpiderFoot

        mock_network_fetch.return_value = {"code": "200"}
        sf = SpiderFoot.__new__(SpiderFoot)
        sf.opts = {"_stealth_level": "none"}

        sf.fetchUrl("https://example.com")

        self.assertIsNone(
            getattr(sf, '_stealth_middleware', None),
            "No middleware should be created for level 'none'",
        )

    @patch("spiderfoot.sflib.core.fetchUrl")
    def test_no_stealth_without_config(self, mock_network_fetch):
        """When opts has no _stealth_level, no middleware is created."""
        from spiderfoot.sflib.core import SpiderFoot

        mock_network_fetch.return_value = {"code": "200"}
        sf = SpiderFoot.__new__(SpiderFoot)
        sf.opts = {}

        sf.fetchUrl("https://example.com")

        self.assertIsNone(getattr(sf, '_stealth_middleware', None))

    def test_stealth_context_property(self):
        """stealth_context property returns None when no context exists."""
        from spiderfoot.sflib.core import SpiderFoot

        sf = SpiderFoot.__new__(SpiderFoot)
        self.assertIsNone(sf.stealth_context)

    @patch("spiderfoot.sflib.core.fetchUrl")
    def test_stealth_context_property_after_fetch(self, mock_network_fetch):
        """stealth_context property returns the context after a stealth fetch."""
        from spiderfoot.sflib.core import SpiderFoot

        mock_network_fetch.return_value = {
            "code": "200", "status": "OK", "content": "",
            "headers": {}, "realurl": "https://x.com",
        }
        sf = SpiderFoot.__new__(SpiderFoot)
        sf.opts = {"_stealth_level": "high"}

        sf.fetchUrl("https://x.com")

        self.assertIsNotNone(sf.stealth_context)


class TestStealthIntegrationWiring(unittest.TestCase):
    """Tests for stealth_integration.py wiring into core/scan pipeline."""

    def test_create_stealth_context_from_level(self):
        """create_stealth_context(stealth_level=...) returns a context."""
        from spiderfoot.recon.stealth_integration import create_stealth_context

        ctx = create_stealth_context(stealth_level="medium")
        self.assertIsNotNone(ctx)
        self.assertTrue(ctx.is_active)

    def test_create_stealth_context_from_sf_options(self):
        """create_stealth_context(sf_options=...) extracts _stealth_level."""
        from spiderfoot.recon.stealth_integration import create_stealth_context

        ctx = create_stealth_context(sf_options={"_stealth_level": "high"})
        self.assertIsNotNone(ctx)
        self.assertTrue(ctx.is_active)

    def test_context_registry_roundtrip(self):
        """register_scan_context / get_scan_context / unregister work correctly."""
        from spiderfoot.recon.stealth_integration import (
            create_stealth_context,
            register_scan_context,
            get_scan_context,
            unregister_scan_context,
        )

        ctx = create_stealth_context(stealth_level="low")
        scan_id = "test-scan-registry-001"

        # Register
        register_scan_context(scan_id, ctx)
        self.assertIs(get_scan_context(scan_id), ctx)

        # Unregister
        unregister_scan_context(scan_id)
        self.assertIsNone(get_scan_context(scan_id))

    def test_get_all_scan_stats(self):
        """get_all_scan_stats returns stats for registered contexts."""
        from spiderfoot.recon.stealth_integration import (
            create_stealth_context,
            register_scan_context,
            get_all_scan_stats,
            unregister_scan_context,
        )

        ctx = create_stealth_context(stealth_level="medium")
        scan_id = "test-scan-stats-001"
        register_scan_context(scan_id, ctx)

        try:
            stats = get_all_scan_stats()
            self.assertIn(scan_id, stats)
            self.assertIsInstance(stats[scan_id], dict)
        finally:
            unregister_scan_context(scan_id)

    def test_stealthy_fetch_with_context(self):
        """stealthy_fetch with a context applies middleware."""
        from spiderfoot.recon.stealth_integration import (
            create_stealth_context,
            stealthy_fetch,
        )

        ctx = create_stealth_context(stealth_level="low")

        with patch("spiderfoot.sflib.network.getSession") as mock_gs:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.reason = "OK"
            mock_resp.content = b"stealth content"
            mock_resp.headers = {}
            mock_resp.url = "https://example.com"
            mock_gs.return_value.get.return_value = mock_resp

            from spiderfoot.sflib.network import fetchUrl as raw_fetch
            result = stealthy_fetch(
                "https://example.com",
                context=ctx,
                _original_fetch=raw_fetch,
            )

            self.assertIsNotNone(result)
            self.assertEqual(result.get("code"), "200")

    def test_stealthy_fetch_via_scan_id(self):
        """stealthy_fetch can look up context by scan_id."""
        from spiderfoot.recon.stealth_integration import (
            create_stealth_context,
            register_scan_context,
            stealthy_fetch,
            unregister_scan_context,
        )

        ctx = create_stealth_context(stealth_level="low")
        scan_id = "test-scan-fetch-001"
        register_scan_context(scan_id, ctx)

        try:
            with patch("spiderfoot.sflib.network.getSession") as mock_gs:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.reason = "OK"
                mock_resp.content = b"ok"
                mock_resp.headers = {}
                mock_resp.url = "https://example.com"
                mock_gs.return_value.get.return_value = mock_resp

                from spiderfoot.sflib.network import fetchUrl as raw_fetch
                result = stealthy_fetch(
                    "https://example.com",
                    scan_id=scan_id,
                    _original_fetch=raw_fetch,
                )
                self.assertEqual(result.get("code"), "200")
        finally:
            unregister_scan_context(scan_id)

    def test_stealthy_fetch_no_context_fallback(self):
        """stealthy_fetch without context/scan_id falls through to plain fetch."""
        from spiderfoot.recon.stealth_integration import stealthy_fetch

        with patch("spiderfoot.sflib.network.getSession") as mock_gs:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.reason = "OK"
            mock_resp.content = b"plain"
            mock_resp.headers = {}
            mock_resp.url = "https://example.com"
            mock_gs.return_value.get.return_value = mock_resp

            from spiderfoot.sflib.network import fetchUrl as raw_fetch
            result = stealthy_fetch(
                "https://example.com",
                _original_fetch=raw_fetch,
            )
            self.assertEqual(result.get("code"), "200")

    def test_middleware_fetch_count_increments(self):
        """StealthFetchMiddleware tracks fetch count."""
        from spiderfoot.recon.stealth_integration import (
            create_stealth_context,
            StealthFetchMiddleware,
        )

        ctx = create_stealth_context(stealth_level="low")
        mw = StealthFetchMiddleware(ctx)

        self.assertEqual(mw.fetch_count, 0)

        with patch("spiderfoot.sflib.network.getSession") as mock_gs:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.reason = "OK"
            mock_resp.content = b""
            mock_resp.headers = {}
            mock_resp.url = "https://example.com"
            mock_gs.return_value.get.return_value = mock_resp

            from spiderfoot.sflib.network import fetchUrl as raw_fetch
            mw.fetch("https://example.com", _original_fetch=raw_fetch)

        self.assertEqual(mw.fetch_count, 1)


if __name__ == "__main__":
    unittest.main()
