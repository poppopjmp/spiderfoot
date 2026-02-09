"""
Tests for API Rate Limiting Middleware (Cycle 24).

Covers:
- RateLimitConfig defaults and from_dict
- Client identity extraction (IP, forwarded, API key)
- Tier detection from route paths
- RateLimitStats recording and serialization
- RateLimitMiddleware allow/deny/429 response
- Response header injection (X-RateLimit-*)
- Exempt path handling
- install_rate_limiting helper
- Module-level state management
"""

import time
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


# ===========================================================================
# RateLimitConfig
# ===========================================================================

class TestRateLimitConfig:
    """RateLimitConfig dataclass tests."""

    def test_defaults(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig
        cfg = RateLimitConfig()
        assert cfg.enabled is True
        assert cfg.trust_forwarded is True
        assert cfg.include_headers is True
        assert cfg.log_rejections is True
        assert "default" in cfg.tier_limits
        assert "scan" in cfg.tier_limits

    def test_custom_values(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig
        cfg = RateLimitConfig(enabled=False, trust_forwarded=False)
        assert cfg.enabled is False
        assert cfg.trust_forwarded is False

    def test_from_dict_defaults(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig
        cfg = RateLimitConfig.from_dict({})
        assert cfg.enabled is True

    def test_from_dict_disabled(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig
        cfg = RateLimitConfig.from_dict({"__ratelimit_enabled": False})
        assert cfg.enabled is False

    def test_from_dict_options(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig
        cfg = RateLimitConfig.from_dict({
            "__ratelimit_trust_forwarded": False,
            "__ratelimit_headers": False,
            "__ratelimit_log_rejections": False,
        })
        assert cfg.trust_forwarded is False
        assert cfg.include_headers is False
        assert cfg.log_rejections is False

    def test_exempt_paths_default(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig
        cfg = RateLimitConfig()
        assert "/api/health" in cfg.exempt_paths
        assert "/api/docs" in cfg.exempt_paths


# ===========================================================================
# Client Identity Extraction
# ===========================================================================

class TestClientIdentity:
    """extract_client_identity tests."""

    def test_api_key(self):
        from spiderfoot.api.rate_limit_middleware import extract_client_identity
        result = extract_client_identity(
            {"client": ("192.168.1.1", 12345)},
            {"authorization": "Bearer abcdefghijklmnop"},
        )
        assert result == "apikey:abcdefgh"

    def test_forwarded_ip(self):
        from spiderfoot.api.rate_limit_middleware import extract_client_identity
        result = extract_client_identity(
            {"client": ("192.168.1.1", 12345)},
            {"x-forwarded-for": "10.0.0.1, 172.16.0.1"},
        )
        assert result == "ip:10.0.0.1"

    def test_forwarded_ip_not_trusted(self):
        from spiderfoot.api.rate_limit_middleware import extract_client_identity
        result = extract_client_identity(
            {"client": ("192.168.1.1", 12345)},
            {"x-forwarded-for": "10.0.0.1"},
            trust_forwarded=False,
        )
        assert result == "ip:192.168.1.1"

    def test_direct_ip(self):
        from spiderfoot.api.rate_limit_middleware import extract_client_identity
        result = extract_client_identity(
            {"client": ("10.20.30.40", 9999)},
            {},
        )
        assert result == "ip:10.20.30.40"

    def test_no_client_info(self):
        from spiderfoot.api.rate_limit_middleware import extract_client_identity
        result = extract_client_identity({}, {})
        assert result == "ip:unknown"

    def test_bearer_empty_token(self):
        from spiderfoot.api.rate_limit_middleware import extract_client_identity
        result = extract_client_identity(
            {"client": ("1.2.3.4", 80)},
            {"authorization": "Bearer   "},
        )
        # Empty token falls through to IP
        assert result == "ip:1.2.3.4"

    def test_non_bearer_auth(self):
        from spiderfoot.api.rate_limit_middleware import extract_client_identity
        result = extract_client_identity(
            {"client": ("1.2.3.4", 80)},
            {"authorization": "Basic dXNlcjpwYXNz"},
        )
        assert result == "ip:1.2.3.4"


# ===========================================================================
# Tier Detection
# ===========================================================================

class TestTierDetection:
    """detect_tier tests."""

    def test_scan_path(self):
        from spiderfoot.api.rate_limit_middleware import detect_tier
        assert detect_tier("/api/scans") == "scan"
        assert detect_tier("/api/scans/123") == "scan"

    def test_scan_singular(self):
        from spiderfoot.api.rate_limit_middleware import detect_tier
        assert detect_tier("/api/scan/start") == "scan"

    def test_data_path(self):
        from spiderfoot.api.rate_limit_middleware import detect_tier
        assert detect_tier("/api/data/events") == "data"

    def test_config_path(self):
        from spiderfoot.api.rate_limit_middleware import detect_tier
        assert detect_tier("/api/config") == "config"

    def test_reports_path(self):
        from spiderfoot.api.rate_limit_middleware import detect_tier
        assert detect_tier("/api/reports/gen") == "reports"

    def test_health_path(self):
        from spiderfoot.api.rate_limit_middleware import detect_tier
        assert detect_tier("/api/health/live") == "health"

    def test_visualization_maps_to_data(self):
        from spiderfoot.api.rate_limit_middleware import detect_tier
        assert detect_tier("/api/visualization/graph") == "data"

    def test_unknown_path(self):
        from spiderfoot.api.rate_limit_middleware import detect_tier
        assert detect_tier("/unknown/path") == "default"

    def test_websocket_path(self):
        from spiderfoot.api.rate_limit_middleware import detect_tier
        assert detect_tier("/ws/events") == "default"


# ===========================================================================
# RateLimitStats
# ===========================================================================

class TestRateLimitStats:
    """RateLimitStats recording and serialization tests."""

    def test_initial_state(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitStats
        stats = RateLimitStats()
        assert stats.total_requests == 0
        assert stats.total_allowed == 0
        assert stats.total_rejected == 0
        assert stats.rejection_rate == 0.0

    def test_record_allowed(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitStats
        stats = RateLimitStats()
        stats.record_allowed()
        stats.record_allowed()
        assert stats.total_requests == 2
        assert stats.total_allowed == 2
        assert stats.total_rejected == 0

    def test_record_rejected(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitStats
        stats = RateLimitStats()
        stats.record_rejected("scan", "ip:1.2.3.4")
        assert stats.total_requests == 1
        assert stats.total_rejected == 1
        assert stats.rejections_by_tier["scan"] == 1
        assert stats.rejections_by_client["ip:1.2.3.4"] == 1

    def test_rejection_rate(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitStats
        stats = RateLimitStats()
        stats.record_allowed()
        stats.record_rejected("scan", "ip:1.2.3.4")
        assert stats.rejection_rate == 0.5

    def test_to_dict(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitStats
        stats = RateLimitStats()
        stats.record_allowed()
        stats.record_rejected("scan", "ip:1.2.3.4")
        d = stats.to_dict()
        assert d["total_requests"] == 2
        assert d["total_allowed"] == 1
        assert d["total_rejected"] == 1
        assert "rejection_rate" in d
        assert "uptime_seconds" in d
        assert "top_offenders" in d

    def test_uptime(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitStats
        stats = RateLimitStats()
        assert stats.uptime >= 0

    def test_client_tracking_bounded(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitStats
        stats = RateLimitStats()
        for i in range(150):
            stats.record_rejected("tier", f"ip:10.0.0.{i}")
        # Should cap at 100 unique clients
        assert len(stats.rejections_by_client) <= 100

    def test_top_offenders_sorted(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitStats
        stats = RateLimitStats()
        stats.record_rejected("scan", "ip:a")
        stats.record_rejected("scan", "ip:b")
        stats.record_rejected("scan", "ip:b")
        stats.record_rejected("scan", "ip:b")
        d = stats.to_dict()
        offenders = list(d["top_offenders"].items())
        assert offenders[0] == ("ip:b", 3)


# ===========================================================================
# Module-level state
# ===========================================================================

class TestModuleState:
    """Module-level state management."""

    def test_get_stats_initial(self):
        from spiderfoot.api.rate_limit_middleware import (
            get_rate_limit_stats,
            reset_rate_limit_state,
        )
        reset_rate_limit_state()
        stats = get_rate_limit_stats()
        assert stats["total_requests"] == 0

    def test_reset_clears_state(self):
        from spiderfoot.api.rate_limit_middleware import (
            _stats,
            reset_rate_limit_state,
            get_rate_limit_stats,
        )
        _stats.record_allowed()
        _stats.record_allowed()
        reset_rate_limit_state()
        stats = get_rate_limit_stats()
        assert stats["total_requests"] == 0


# ===========================================================================
# RateLimitMiddleware (unit tests via ASGI simulation)
# ===========================================================================

class TestRateLimitMiddleware:
    """Middleware behavior tests using RateLimiterService directly."""

    def setup_method(self):
        from spiderfoot.api.rate_limit_middleware import reset_rate_limit_state
        reset_rate_limit_state()

    def teardown_method(self):
        from spiderfoot.api.rate_limit_middleware import reset_rate_limit_state
        reset_rate_limit_state()

    def test_middleware_allows_request(self):
        """Requests under the limit are allowed."""
        from spiderfoot.api.rate_limit_middleware import (
            RateLimitConfig,
            RateLimitMiddleware,
        )
        import asyncio

        async def inner_app(scope, receive, send):
            from starlette.responses import Response
            resp = Response("OK", status_code=200)
            await resp(scope, receive, send)

        config = RateLimitConfig(tier_limits={"default": (100, 60.0), "scan": (100, 60.0)})
        mw = RateLimitMiddleware(inner_app, rate_config=config)

        # Simulate a request
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        app = Starlette(routes=[Route("/api/test", lambda r: PlainTextResponse("ok"))])
        app.add_middleware(RateLimitMiddleware, rate_config=config)
        client = TestClient(app)
        resp = client.get("/api/test")
        assert resp.status_code == 200

    def test_middleware_adds_headers(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig, RateLimitMiddleware
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        config = RateLimitConfig(
            tier_limits={"default": (100, 60.0)},
            include_headers=True,
        )
        app = Starlette(routes=[Route("/api/test", lambda r: PlainTextResponse("ok"))])
        app.add_middleware(RateLimitMiddleware, rate_config=config)
        client = TestClient(app)
        resp = client.get("/api/test")
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers

    def test_middleware_429_on_limit(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig, RateLimitMiddleware
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        # Very tight limit: 2 requests per 60s
        config = RateLimitConfig(
            tier_limits={"default": (2, 60.0)},
            log_rejections=False,
        )
        app = Starlette(routes=[Route("/api/test", lambda r: PlainTextResponse("ok"))])
        app.add_middleware(RateLimitMiddleware, rate_config=config)
        client = TestClient(app)

        # First two should pass
        assert client.get("/api/test").status_code == 200
        assert client.get("/api/test").status_code == 200
        # Third should be 429
        resp = client.get("/api/test")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        body = resp.json()
        assert "Too Many Requests" in body["error"]

    def test_middleware_exempt_path(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig, RateLimitMiddleware
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        config = RateLimitConfig(
            tier_limits={"default": (1, 60.0)},
            exempt_paths={"/api/health"},
        )
        app = Starlette(routes=[
            Route("/api/health", lambda r: PlainTextResponse("ok")),
            Route("/api/test", lambda r: PlainTextResponse("ok")),
        ])
        app.add_middleware(RateLimitMiddleware, rate_config=config)
        client = TestClient(app)

        # Health is exempt — unlimited
        for _ in range(5):
            assert client.get("/api/health").status_code == 200

        # Test route is limited
        assert client.get("/api/test").status_code == 200
        assert client.get("/api/test").status_code == 429

    def test_middleware_disabled(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig, RateLimitMiddleware
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        config = RateLimitConfig(
            enabled=False,
            tier_limits={"default": (1, 60.0)},
        )
        app = Starlette(routes=[Route("/api/test", lambda r: PlainTextResponse("ok"))])
        app.add_middleware(RateLimitMiddleware, rate_config=config)
        client = TestClient(app)

        # Should all pass since disabled
        for _ in range(10):
            assert client.get("/api/test").status_code == 200

    def test_middleware_no_headers_when_disabled(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig, RateLimitMiddleware
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        config = RateLimitConfig(
            tier_limits={"default": (100, 60.0)},
            include_headers=False,
        )
        app = Starlette(routes=[Route("/api/test", lambda r: PlainTextResponse("ok"))])
        app.add_middleware(RateLimitMiddleware, rate_config=config)
        client = TestClient(app)
        resp = client.get("/api/test")
        assert "X-RateLimit-Limit" not in resp.headers

    def test_429_response_contains_retry_after(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig, RateLimitMiddleware
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        config = RateLimitConfig(
            tier_limits={"default": (1, 60.0)},
            log_rejections=False,
        )
        app = Starlette(routes=[Route("/api/test", lambda r: PlainTextResponse("ok"))])
        app.add_middleware(RateLimitMiddleware, rate_config=config)
        client = TestClient(app)

        client.get("/api/test")  # consume the one allowed
        resp = client.get("/api/test")  # should be 429
        assert resp.status_code == 429
        retry = int(resp.headers["Retry-After"])
        assert retry >= 1

    def test_stats_updated_on_rejection(self):
        from spiderfoot.api.rate_limit_middleware import (
            RateLimitConfig,
            RateLimitMiddleware,
            get_rate_limit_stats,
        )
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        config = RateLimitConfig(
            tier_limits={"default": (1, 60.0)},
            log_rejections=False,
        )
        app = Starlette(routes=[Route("/api/test", lambda r: PlainTextResponse("ok"))])
        app.add_middleware(RateLimitMiddleware, rate_config=config)
        client = TestClient(app)

        client.get("/api/test")
        client.get("/api/test")  # rejected

        stats = get_rate_limit_stats()
        assert stats["total_allowed"] >= 1
        assert stats["total_rejected"] >= 1


# ===========================================================================
# install_rate_limiting helper
# ===========================================================================

class TestInstallRateLimiting:
    """install_rate_limiting function tests."""

    def setup_method(self):
        from spiderfoot.api.rate_limit_middleware import reset_rate_limit_state
        reset_rate_limit_state()

    def teardown_method(self):
        from spiderfoot.api.rate_limit_middleware import reset_rate_limit_state
        reset_rate_limit_state()

    def test_install_returns_true(self):
        from spiderfoot.api.rate_limit_middleware import install_rate_limiting
        from starlette.applications import Starlette
        app = Starlette()
        assert install_rate_limiting(app) is True

    def test_install_with_config(self):
        from spiderfoot.api.rate_limit_middleware import install_rate_limiting
        from starlette.applications import Starlette
        app = Starlette()
        assert install_rate_limiting(app, {"__ratelimit_enabled": False}) is True

    def test_install_without_starlette(self):
        from spiderfoot.api import rate_limit_middleware as rlm
        original = rlm.HAS_STARLETTE
        try:
            rlm.HAS_STARLETTE = False
            from starlette.applications import Starlette
            app = Starlette()
            assert rlm.install_rate_limiting(app) is False
        finally:
            rlm.HAS_STARLETTE = original


# ===========================================================================
# Integration: Different client identities get separate limits
# ===========================================================================

class TestPerClientLimits:
    """Different clients get independent rate limit buckets."""

    def setup_method(self):
        from spiderfoot.api.rate_limit_middleware import reset_rate_limit_state
        reset_rate_limit_state()

    def teardown_method(self):
        from spiderfoot.api.rate_limit_middleware import reset_rate_limit_state
        reset_rate_limit_state()

    def test_different_api_keys_independent(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig, RateLimitMiddleware
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        config = RateLimitConfig(
            tier_limits={"default": (2, 60.0)},
            log_rejections=False,
        )
        app = Starlette(routes=[Route("/api/test", lambda r: PlainTextResponse("ok"))])
        app.add_middleware(RateLimitMiddleware, rate_config=config)
        client = TestClient(app)

        # Client A exhausts their limit
        client.get("/api/test", headers={"Authorization": "Bearer clientAAAAAAAA"})
        client.get("/api/test", headers={"Authorization": "Bearer clientAAAAAAAA"})
        resp_a = client.get("/api/test", headers={"Authorization": "Bearer clientAAAAAAAA"})
        assert resp_a.status_code == 429

        # Client B should still have quota
        resp_b = client.get("/api/test", headers={"Authorization": "Bearer clientBBBBBBBB"})
        assert resp_b.status_code == 200

    def test_different_ips_independent(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig, RateLimitMiddleware
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        config = RateLimitConfig(
            tier_limits={"default": (1, 60.0)},
            log_rejections=False,
        )
        app = Starlette(routes=[Route("/api/test", lambda r: PlainTextResponse("ok"))])
        app.add_middleware(RateLimitMiddleware, rate_config=config)
        client = TestClient(app)

        # First IP exhausts limit
        client.get("/api/test", headers={"X-Forwarded-For": "10.0.0.1"})
        resp1 = client.get("/api/test", headers={"X-Forwarded-For": "10.0.0.1"})
        assert resp1.status_code == 429

        # Second IP should work
        resp2 = client.get("/api/test", headers={"X-Forwarded-For": "10.0.0.2"})
        assert resp2.status_code == 200
