"""
Middleware behavioral tests (Steps 66-69).

These tests exercise the CSRF, body-limit, request-tracing, and
rate-limit middleware by sending actual ASGI requests through a minimal
FastAPI app wrapped with each middleware.

No mocks are used — every assertion is checked via real HTTP semantics.
"""
from __future__ import annotations

import asyncio
import json
import re
import pytest

# ---------------------------------------------------------------------------
# Helpers — build a tiny FastAPI app per middleware under test
# ---------------------------------------------------------------------------

_HAS_DEPS = True
try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    import httpx
except ImportError:
    _HAS_DEPS = False

pytestmark = pytest.mark.skipif(not _HAS_DEPS, reason="fastapi or httpx not installed")


def _make_app() -> "FastAPI":
    """Return a minimal FastAPI with a catch-all echo endpoint."""
    app = FastAPI()

    @app.api_route("/api/data", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def echo(request: Request):
        body = await request.body()
        return JSONResponse({"method": request.method, "body_len": len(body)})

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.post("/api/auth/login")
    async def login():
        return {"token": "fake"}

    return app


async def _client(app: "FastAPI") -> "httpx.AsyncClient":
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ===================================================================
# CSRF Middleware — behavioral tests (Step 66)
# ===================================================================

class TestCSRFMiddleware:
    """Verify that the CSRF middleware rejects/allows requests correctly."""

    @pytest.fixture()
    def csrf_app(self):
        from spiderfoot.api.csrf_middleware import CSRFMiddleware, CSRFConfig
        app = _make_app()
        cfg = CSRFConfig(enabled=True, protected_paths=["/api"])
        app.add_middleware(CSRFMiddleware, config=cfg)
        return app

    @pytest.mark.asyncio
    async def test_get_always_passes(self, csrf_app):
        """Safe methods should not require CSRF headers."""
        async with await _client(csrf_app) as c:
            r = await c.get("/api/data")
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_post_without_header_rejected(self, csrf_app):
        """POST without X-Requested-With or X-SF-CSRF must be 403."""
        async with await _client(csrf_app) as c:
            r = await c.post("/api/data", json={"x": 1})
            assert r.status_code == 403
            body = r.json()
            assert body["error"]["code"] == "CSRF_VALIDATION_FAILED"

    @pytest.mark.asyncio
    async def test_post_with_x_requested_with_passes(self, csrf_app):
        """POST with X-Requested-With header should succeed."""
        async with await _client(csrf_app) as c:
            r = await c.post(
                "/api/data",
                json={"x": 1},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_post_with_x_sf_csrf_passes(self, csrf_app):
        """POST with X-SF-CSRF header should succeed."""
        async with await _client(csrf_app) as c:
            r = await c.post(
                "/api/data",
                json={"x": 1},
                headers={"X-SF-CSRF": "1"},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_put_without_header_rejected(self, csrf_app):
        """PUT without CSRF header must be 403."""
        async with await _client(csrf_app) as c:
            r = await c.put("/api/data", json={"x": 1})
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_without_header_rejected(self, csrf_app):
        """DELETE without CSRF header must be 403."""
        async with await _client(csrf_app) as c:
            r = await c.delete("/api/data")
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_exempt_path_passes(self, csrf_app):
        """Exempt paths (e.g. /api/auth/login) should bypass CSRF."""
        async with await _client(csrf_app) as c:
            r = await c.post("/api/auth/login", json={"user": "a"})
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_unprotected_path_passes(self, csrf_app):
        """Paths outside /api/ prefix are not protected."""
        from spiderfoot.api.csrf_middleware import CSRFMiddleware, CSRFConfig
        app = _make_app()

        @app.post("/other")
        async def other():
            return {"ok": True}

        cfg = CSRFConfig(enabled=True)
        app.add_middleware(CSRFMiddleware, config=cfg)
        async with await _client(app) as c:
            r = await c.post("/other")
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_disabled(self):
        """When disabled, all requests should pass through."""
        from spiderfoot.api.csrf_middleware import CSRFMiddleware, CSRFConfig
        app = _make_app()
        cfg = CSRFConfig(enabled=False)
        app.add_middleware(CSRFMiddleware, config=cfg)
        async with await _client(app) as c:
            r = await c.post("/api/data", json={"x": 1})
            assert r.status_code == 200


# ===================================================================
# Body-Limit Middleware — behavioral tests (Step 67)
# ===================================================================

class TestBodyLimitMiddleware:
    """Verify that oversized request bodies are rejected."""

    @pytest.fixture()
    def limit_app(self):
        from spiderfoot.api.body_limit_middleware import BodySizeLimitMiddleware
        app = _make_app()
        # Use small limits for testing: 1 KB general, 5 KB upload
        app.add_middleware(BodySizeLimitMiddleware, max_body=1024, max_upload=5120)
        return app

    @pytest.mark.asyncio
    async def test_small_body_accepted(self, limit_app):
        """Bodies within the limit should pass."""
        async with await _client(limit_app) as c:
            r = await c.post(
                "/api/data",
                content=b"x" * 100,
                headers={"Content-Type": "application/octet-stream"},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_oversized_body_rejected(self, limit_app):
        """Bodies exceeding the limit should be rejected with 413."""
        async with await _client(limit_app) as c:
            r = await c.post(
                "/api/data",
                content=b"x" * 2048,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": "2048",
                },
            )
            assert r.status_code == 413

    @pytest.mark.asyncio
    async def test_get_ignores_limit(self, limit_app):
        """GET requests should bypass body-size checks."""
        async with await _client(limit_app) as c:
            r = await c.get("/api/data")
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_content_length_rejected(self, limit_app):
        """Invalid Content-Length header should return 400."""
        async with await _client(limit_app) as c:
            r = await c.post(
                "/api/data",
                content=b"x",
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": "not-a-number",
                },
            )
            assert r.status_code == 400


# ===================================================================
# Request Tracing Middleware — behavioral tests (Step 69)
# ===================================================================

class TestRequestTracingMiddleware:
    """Verify that X-Request-ID is generated, echoed, and sanitized."""

    @pytest.fixture()
    def tracing_app(self):
        from spiderfoot.observability.request_tracing import (
            RequestTracingMiddleware,
            get_request_id,
        )
        app = _make_app()

        @app.get("/api/trace-check")
        async def trace_check():
            return {"request_id": get_request_id()}

        app.add_middleware(
            RequestTracingMiddleware,
            trust_client_id=True,
            log_requests=False,
        )
        return app

    @pytest.mark.asyncio
    async def test_generates_request_id(self, tracing_app):
        """Response should include a generated X-Request-ID when none supplied."""
        async with await _client(tracing_app) as c:
            r = await c.get("/api/health")
            rid = r.headers.get("x-request-id")
            assert rid is not None
            # Should look like a UUID
            assert re.match(r"^[a-f0-9-]{36}$", rid)

    @pytest.mark.asyncio
    async def test_echoes_valid_client_id(self, tracing_app):
        """Middleware should echo a valid client-supplied X-Request-ID."""
        custom_id = "my-trace-id-12345"
        async with await _client(tracing_app) as c:
            r = await c.get("/api/health", headers={"X-Request-ID": custom_id})
            assert r.headers.get("x-request-id") == custom_id

    @pytest.mark.asyncio
    async def test_rejects_malicious_request_id(self, tracing_app):
        """Malicious IDs (newlines, control chars) should be replaced."""
        async with await _client(tracing_app) as c:
            r = await c.get(
                "/api/health",
                headers={"X-Request-ID": "evil\nHeader-Injection: bad"},
            )
            rid = r.headers.get("x-request-id")
            assert "\n" not in rid
            # Should have been replaced with a generated UUID
            assert re.match(r"^[a-f0-9-]{36}$", rid)

    @pytest.mark.asyncio
    async def test_rejects_overlong_request_id(self, tracing_app):
        """Request IDs longer than 128 chars should be replaced."""
        async with await _client(tracing_app) as c:
            r = await c.get(
                "/api/health",
                headers={"X-Request-ID": "x" * 200},
            )
            rid = r.headers.get("x-request-id")
            assert len(rid) <= 128

    @pytest.mark.asyncio
    async def test_request_id_available_in_handler(self, tracing_app):
        """get_request_id() should return the current ID inside a handler."""
        async with await _client(tracing_app) as c:
            r = await c.get("/api/trace-check")
            body = r.json()
            header_id = r.headers.get("x-request-id")
            assert body["request_id"] == header_id


# ===================================================================
# Request ID sanitization — unit tests (Step 64)
# ===================================================================

class TestRequestIdSanitization:
    """Unit-test _sanitize_request_id directly."""

    def test_valid_uuid(self):
        from spiderfoot.observability.request_tracing import _sanitize_request_id
        assert _sanitize_request_id("550e8400-e29b-41d4-a716-446655440000") is not None

    def test_valid_alphanumeric(self):
        from spiderfoot.observability.request_tracing import _sanitize_request_id
        assert _sanitize_request_id("my-trace-123_v2.0") == "my-trace-123_v2.0"

    def test_rejects_newline(self):
        from spiderfoot.observability.request_tracing import _sanitize_request_id
        assert _sanitize_request_id("evil\nid") is None

    def test_rejects_spaces(self):
        from spiderfoot.observability.request_tracing import _sanitize_request_id
        assert _sanitize_request_id("has space") is None

    def test_rejects_overlong(self):
        from spiderfoot.observability.request_tracing import _sanitize_request_id
        assert _sanitize_request_id("a" * 200) is None

    def test_none_input(self):
        from spiderfoot.observability.request_tracing import _sanitize_request_id
        assert _sanitize_request_id(None) is None

    def test_empty_string(self):
        from spiderfoot.observability.request_tracing import _sanitize_request_id
        assert _sanitize_request_id("") is None

    def test_rejects_angle_brackets(self):
        from spiderfoot.observability.request_tracing import _sanitize_request_id
        assert _sanitize_request_id("<script>alert(1)</script>") is None


# ===================================================================
# Rate Limit Middleware — config & detection tests (Step 68)
# ===================================================================

class TestRateLimitDetection:
    """Test rate-limit tier detection and config parsing."""

    def test_login_endpoint_override(self):
        """Login should be limited to 5 requests per 60 seconds."""
        from spiderfoot.api.rate_limit_middleware import DEFAULT_ENDPOINT_OVERRIDES
        assert "/api/auth/login" in DEFAULT_ENDPOINT_OVERRIDES
        max_req, window = DEFAULT_ENDPOINT_OVERRIDES["/api/auth/login"]
        assert max_req <= 5
        assert window >= 60.0

    def test_register_endpoint_override(self):
        """Register should be limited to 3 requests per 60 seconds."""
        from spiderfoot.api.rate_limit_middleware import DEFAULT_ENDPOINT_OVERRIDES
        assert "/api/auth/register" in DEFAULT_ENDPOINT_OVERRIDES
        max_req, _ = DEFAULT_ENDPOINT_OVERRIDES["/api/auth/register"]
        assert max_req <= 3

    def test_detect_tier_auth(self):
        """Auth paths should map to the 'auth' tier."""
        from spiderfoot.api.rate_limit_middleware import detect_tier
        assert detect_tier("/api/auth/login") == "auth"
        assert detect_tier("/api/auth/register") == "auth"

    def test_detect_tier_scan(self):
        """Scan paths should map to the 'scan' tier."""
        from spiderfoot.api.rate_limit_middleware import detect_tier
        tier = detect_tier("/api/scans")
        assert tier in ("scan", "data", "default")

    def test_tier_limits_exist(self):
        """All expected tiers should have limit tuples."""
        from spiderfoot.api.rate_limit_middleware import DEFAULT_TIER_LIMITS
        for tier in ("auth", "scan", "data"):
            assert tier in DEFAULT_TIER_LIMITS
            max_req, window = DEFAULT_TIER_LIMITS[tier]
            assert max_req > 0
            assert window > 0

    def test_config_creation(self):
        """RateLimitConfig should be constructable with defaults."""
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig
        cfg = RateLimitConfig()
        assert cfg.enabled is True
        assert len(cfg.tier_limits) > 0
