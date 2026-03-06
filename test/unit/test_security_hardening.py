"""Tests for security hardening — Cycles 42-50.

Covers:
    - Cycle 42: MinIO TLS defaults in Docker compose files
    - Cycle 43: read_only filesystem on security-sensitive containers
    - Cycle 46: CSRF protection on GraphQL endpoint
    - Cycle 47: Auth rate-limit tier mapping
"""
from __future__ import annotations

import asyncio
import os
import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Cycle 42 & 43: Docker Compose hardening
# ---------------------------------------------------------------------------


class TestDockerMinIOTLS(unittest.TestCase):
    """Verify SF_MINIO_SECURE defaults to 'true' in all compose files."""

    COMPOSE_DIR = Path(__file__).resolve().parents[2] / "docker" / "compose"

    def _read(self, name: str) -> str:
        return (self.COMPOSE_DIR / name).read_text(encoding="utf-8")

    def test_core_api_minio_secure(self):
        content = self._read("core.yml")
        matches = re.findall(r'SF_MINIO_SECURE:\s*"([^"]*)"', content)
        for m in matches:
            self.assertIn("true", m.lower(),
                          f"SF_MINIO_SECURE should default to true, got: {m}")

    def test_scan_worker_minio_secure(self):
        content = self._read("scan.yml")
        matches = re.findall(r'SF_MINIO_SECURE:\s*"([^"]*)"', content)
        for m in matches:
            self.assertIn("true", m.lower(),
                          f"SF_MINIO_SECURE should default to true, got: {m}")


class TestDockerReadOnly(unittest.TestCase):
    """Verify security-sensitive containers have read_only: true."""

    COMPOSE_DIR = Path(__file__).resolve().parents[2] / "docker" / "compose"

    def _read(self, name: str) -> str:
        return (self.COMPOSE_DIR / name).read_text(encoding="utf-8")

    def _service_has_read_only(self, content: str, service_name: str) -> bool:
        """Check if a service block contains 'read_only: true'."""
        # Find the service block and check for read_only
        pattern = rf'^\s+{re.escape(service_name)}:\s*$'
        match = re.search(pattern, content, re.MULTILINE)
        if not match:
            return False
        # Get text from service definition to next top-level service
        start = match.start()
        rest = content[start:]
        lines = rest.split('\n')
        for line in lines[1:]:
            # Stop at next service definition (non-indented key)
            if line and not line.startswith(' ') and not line.startswith('#'):
                break
            if 'read_only: true' in line:
                return True
        return False

    def test_postgres_read_only(self):
        content = self._read("core.yml")
        self.assertTrue(self._service_has_read_only(content, "postgres"),
                        "postgres container must have read_only: true")

    def test_minio_read_only(self):
        content = self._read("storage.yml")
        self.assertTrue(self._service_has_read_only(content, "minio"),
                        "minio container must have read_only: true")

    def test_grafana_read_only(self):
        content = self._read("monitor.yml")
        self.assertTrue(self._service_has_read_only(content, "grafana"),
                        "grafana container must have read_only: true")

    def test_keycloak_read_only(self):
        content = self._read("sso.yml")
        self.assertTrue(self._service_has_read_only(content, "keycloak"),
                        "keycloak container must have read_only: true")


# ---------------------------------------------------------------------------
# Cycle 46: CSRF protection
# ---------------------------------------------------------------------------


class TestCSRFMiddleware(unittest.TestCase):
    """Verify CSRF middleware logic."""

    def setUp(self):
        from spiderfoot.api.csrf_middleware import CSRFMiddleware, CSRFConfig
        self.CSRFMiddleware = CSRFMiddleware
        self.CSRFConfig = CSRFConfig

    def test_config_from_env_enabled_by_default(self):
        cfg = self.CSRFConfig.from_env()
        self.assertTrue(cfg.enabled)
        self.assertIn("/api/graphql", cfg.protected_paths)

    def test_config_from_env_disabled(self):
        os.environ["SF_CSRF_ENABLED"] = "false"
        try:
            cfg = self.CSRFConfig.from_env()
            self.assertFalse(cfg.enabled)
        finally:
            del os.environ["SF_CSRF_ENABLED"]

    def test_config_allowed_origins_from_env(self):
        os.environ["SF_CSRF_ALLOWED_ORIGINS"] = "https://a.com, https://b.com"
        try:
            cfg = self.CSRFConfig.from_env()
            self.assertEqual(cfg.allowed_origins, ["https://a.com", "https://b.com"])
        finally:
            del os.environ["SF_CSRF_ALLOWED_ORIGINS"]

    def test_safe_methods_pass(self):
        """GET requests to protected paths should pass without custom header."""
        from spiderfoot.api.csrf_middleware import _SAFE_METHODS
        self.assertIn("GET", _SAFE_METHODS)
        self.assertIn("HEAD", _SAFE_METHODS)
        self.assertIn("OPTIONS", _SAFE_METHODS)

    def test_csrf_headers_defined(self):
        from spiderfoot.api.csrf_middleware import _CSRF_HEADERS
        self.assertIn("x-requested-with", _CSRF_HEADERS)
        self.assertIn("x-sf-csrf", _CSRF_HEADERS)

    def test_has_csrf_header_positive(self):
        """Request with X-Requested-With should satisfy CSRF check."""
        request = MagicMock()
        request.headers = {"x-requested-with": "XMLHttpRequest"}
        self.assertTrue(self.CSRFMiddleware._has_csrf_header(request))

    def test_has_csrf_header_negative(self):
        """Request without custom headers should fail CSRF check."""
        request = MagicMock()
        request.headers = {"content-type": "application/json"}
        self.assertFalse(self.CSRFMiddleware._has_csrf_header(request))

    def test_ws_origin_validation_same_origin(self):
        """WebSocket from same origin should pass."""
        cfg = self.CSRFConfig(enabled=True, allowed_origins=[])
        mw = self.CSRFMiddleware.__new__(self.CSRFMiddleware)
        mw.config = cfg
        request = MagicMock()
        request.headers = {"origin": "https://localhost", "host": "localhost"}
        self.assertTrue(mw._validate_ws_origin(request))

    def test_ws_origin_validation_cross_origin_rejected(self):
        """WebSocket from different origin should be rejected."""
        cfg = self.CSRFConfig(enabled=True, allowed_origins=[])
        mw = self.CSRFMiddleware.__new__(self.CSRFMiddleware)
        mw.config = cfg
        request = MagicMock()
        request.headers = {"origin": "https://evil.com", "host": "localhost"}
        self.assertFalse(mw._validate_ws_origin(request))

    def test_ws_origin_validation_allowed_list(self):
        """WebSocket with origin in allowed list should pass."""
        cfg = self.CSRFConfig(
            enabled=True,
            allowed_origins=["https://app.example.com"],
        )
        mw = self.CSRFMiddleware.__new__(self.CSRFMiddleware)
        mw.config = cfg
        request = MagicMock()
        request.headers = {"origin": "https://app.example.com", "host": "localhost"}
        self.assertTrue(mw._validate_ws_origin(request))


# ---------------------------------------------------------------------------
# Cycle 47: Auth rate-limit tier mapping
# ---------------------------------------------------------------------------


class TestAuthRateLimitTier(unittest.TestCase):
    """Verify /api/auth maps to the 'auth' rate-limit tier."""

    def test_auth_in_route_tier_map(self):
        from spiderfoot.api.rate_limit_middleware import ROUTE_TIER_MAP
        self.assertIn("/api/auth", ROUTE_TIER_MAP)
        self.assertEqual(ROUTE_TIER_MAP["/api/auth"], "auth")

    def test_auth_tier_limit(self):
        from spiderfoot.api.rate_limit_middleware import DEFAULT_TIER_LIMITS
        self.assertIn("auth", DEFAULT_TIER_LIMITS)
        requests, window = DEFAULT_TIER_LIMITS["auth"]
        self.assertLessEqual(requests, 10, "Auth tier should allow ≤10 req/min")

    def test_login_endpoint_override(self):
        from spiderfoot.api.rate_limit_middleware import DEFAULT_ENDPOINT_OVERRIDES
        self.assertIn("/api/auth/login", DEFAULT_ENDPOINT_OVERRIDES)
        requests, window = DEFAULT_ENDPOINT_OVERRIDES["/api/auth/login"]
        self.assertLessEqual(requests, 5, "Login should allow ≤5 req/min")

    def test_register_endpoint_override(self):
        from spiderfoot.api.rate_limit_middleware import DEFAULT_ENDPOINT_OVERRIDES
        self.assertIn("/api/auth/register", DEFAULT_ENDPOINT_OVERRIDES)

    def test_config_uses_endpoint_overrides_by_default(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig
        cfg = RateLimitConfig()
        self.assertIn("/api/auth/login", cfg.endpoint_overrides)


if __name__ == "__main__":
    unittest.main()
