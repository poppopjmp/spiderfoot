"""
Tests for Cycle 50 — OWASP Security Regression Suite

Maps to the OWASP Top 10 (2021) and verifies that SpiderFoot's security
controls remain intact.  Each test class targets one OWASP category.

A01: Broken Access Control — API key auth enforced, RBAC roles
A02: Cryptographic Failures — HMAC key storage, no plaintext secrets
A03: Injection — Input validation blocks shell metacharacters
A04: Insecure Design — Scan target type validation
A05: Security Misconfiguration — Security headers, CSRF defaults
A06: Vulnerable Components — (covered by dependency scanning, not unit tests)
A07: Auth Failures — Key rotation, expiration, revocation
A08: Data Integrity — Error handler strips internals
A09: Logging — Security events logged properly
A10: SSRF — Webhook URL validation blocks private IPs
"""

from __future__ import annotations

import os
import re
import time
import pytest
from unittest.mock import patch

from spiderfoot.core.validation import ValidationUtils
from spiderfoot.api.error_handlers import (
    _unhandled_exception_handler,
    _build_error_response,
)
from spiderfoot.auth.api_keys import APIKeyRecord, _hash_key, KEY_PREFIX
from spiderfoot.api.csrf_middleware import CSRFConfig, _CSRF_HEADERS, _SAFE_METHODS


# ---------------------------------------------------------------------------
# Fake Request helper
# ---------------------------------------------------------------------------

class _FakeState:
    request_id = "owasp-test-001"

class _FakeRequest:
    method = "GET"
    url = type("U", (), {"path": "/test"})()
    state = _FakeState()
    headers = {}


# ═══════════════════════════════════════════════════════════════════════════
# A01 — Broken Access Control
# ═══════════════════════════════════════════════════════════════════════════

class TestA01BrokenAccessControl:
    """Verify that RBAC roles and API key scopes restrict access."""

    def test_api_key_record_disabled_cannot_auth(self):
        """Disabled keys must not be considered valid."""
        r = APIKeyRecord(key_id="k1", key_hash="h1", name="t", enabled=False)
        assert not r.is_valid()

    def test_api_key_record_expired_cannot_auth(self):
        """Expired keys must not be considered valid."""
        r = APIKeyRecord(
            key_id="k1", key_hash="h1", name="t",
            expires_at=time.time() - 3600,
        )
        assert not r.is_valid()

    def test_valid_key_with_future_expiry(self):
        r = APIKeyRecord(
            key_id="k1", key_hash="h1", name="t",
            expires_at=time.time() + 86400,
        )
        assert r.is_valid()

    def test_key_hash_never_in_default_dict(self):
        """to_dict() without include_hash=True must not leak the hash."""
        r = APIKeyRecord(key_id="k1", key_hash="secret_hash", name="t")
        d = r.to_dict()
        assert "key_hash" not in d
        assert "secret_hash" not in str(d)


# ═══════════════════════════════════════════════════════════════════════════
# A02 — Cryptographic Failures
# ═══════════════════════════════════════════════════════════════════════════

class TestA02CryptographicFailures:
    """Verify keys are stored as HMAC hashes, not plaintext."""

    def test_hash_is_not_plaintext(self):
        key = "sfk_abc123def456"
        h = _hash_key(key)
        assert h != key
        assert len(h) == 64  # SHA-256 hex digest

    def test_hash_is_deterministic(self):
        assert _hash_key("test") == _hash_key("test")

    def test_different_keys_produce_different_hashes(self):
        assert _hash_key("key_a") != _hash_key("key_b")


# ═══════════════════════════════════════════════════════════════════════════
# A03 — Injection
# ═══════════════════════════════════════════════════════════════════════════

class TestA03Injection:
    """Verify input validation blocks common injection vectors."""

    @pytest.mark.parametrize("payload", [
        "'; DROP TABLE scans; --",
        "<script>alert('XSS')</script>",
        "{{7*7}}",               # SSTI
        "${jndi:ldap://evil}",   # Log4Shell-style
        "`id`",                  # Command injection
        "| cat /etc/passwd",     # Pipe injection
    ])
    def test_shell_metachar_blocked_in_targets(self, payload):
        with pytest.raises(ValueError):
            ValidationUtils.validate_target_value(payload, "IP_ADDRESS")

    def test_null_byte_injection_blocked(self):
        with pytest.raises(ValueError, match="null bytes"):
            ValidationUtils.validate_target_value("test\x00inject", "INTERNET_NAME")

    def test_path_traversal_in_username_blocked(self):
        with pytest.raises(ValueError, match="path separators"):
            ValidationUtils.validate_target_value("../../etc/passwd", "USERNAME")


# ═══════════════════════════════════════════════════════════════════════════
# A04 — Insecure Design
# ═══════════════════════════════════════════════════════════════════════════

class TestA04InsecureDesign:
    """Verify type-safe target validation prevents misuse."""

    def test_ipv6_rejected_as_ipv4(self):
        with pytest.raises(ValueError, match="IPv6"):
            ValidationUtils.validate_target_value("::1", "IP_ADDRESS")

    def test_ipv4_rejected_as_ipv6(self):
        with pytest.raises(ValueError, match="not an IPv6"):
            ValidationUtils.validate_target_value("1.2.3.4", "IPV6_ADDRESS")

    def test_invalid_target_type_rejected(self):
        with pytest.raises(ValueError, match="Invalid target type"):
            ValidationUtils.validate_target_type("ARBITRARY_TYPE")

    def test_all_11_types_accepted(self):
        assert len(ValidationUtils._VALID_TARGET_TYPES) == 11


# ═══════════════════════════════════════════════════════════════════════════
# A05 — Security Misconfiguration
# ═══════════════════════════════════════════════════════════════════════════

class TestA05SecurityMisconfiguration:
    """Verify secure defaults for CSRF, headers, etc."""

    def test_csrf_enabled_by_default(self):
        cfg = CSRFConfig()
        assert cfg.enabled is True

    def test_csrf_safe_methods_are_readony(self):
        """Safe methods should only include GET, HEAD, OPTIONS, TRACE."""
        assert _SAFE_METHODS == frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
        # POST/PUT/PATCH/DELETE must NOT be safe
        for m in ("POST", "PUT", "PATCH", "DELETE"):
            assert m not in _SAFE_METHODS

    def test_csrf_headers_defined(self):
        """At least one custom header should be accepted."""
        assert len(_CSRF_HEADERS) > 0
        assert "x-requested-with" in _CSRF_HEADERS

    def test_csrf_config_from_env(self):
        """SF_CSRF_ENABLED=false should disable CSRF."""
        with patch.dict(os.environ, {"SF_CSRF_ENABLED": "false"}):
            cfg = CSRFConfig.from_env()
            assert cfg.enabled is False

    def test_csrf_config_from_env_default(self):
        with patch.dict(os.environ, {}, clear=False):
            # Remove the env var if present
            os.environ.pop("SF_CSRF_ENABLED", None)
            cfg = CSRFConfig.from_env()
            assert cfg.enabled is True


# ═══════════════════════════════════════════════════════════════════════════
# A07 — Identification and Authentication Failures
# ═══════════════════════════════════════════════════════════════════════════

class TestA07AuthFailures:
    """Verify key expiration, sufficiently random secrets."""

    def test_key_prefix_consistent(self):
        assert KEY_PREFIX == "sfk_"

    def test_expired_key_is_invalid(self):
        r = APIKeyRecord(
            key_id="k1", key_hash="h1", name="t",
            expires_at=1.0,  # epoch + 1 second — long expired
        )
        assert r.is_expired()
        assert not r.is_valid()

    def test_never_expiring_key(self):
        r = APIKeyRecord(
            key_id="k1", key_hash="h1", name="t",
            expires_at=0,  # 0 = never expires
        )
        assert not r.is_expired()


# ═══════════════════════════════════════════════════════════════════════════
# A08 — Software and Data Integrity Failures
# ═══════════════════════════════════════════════════════════════════════════

class TestA08DataIntegrity:
    """Verify error responses don't expose internal data."""

    @pytest.mark.asyncio
    async def test_unhandled_exception_strips_internals(self):
        exc = RuntimeError("psycopg2.OperationalError: FATAL: password authentication failed for user 'admin'")
        resp = await _unhandled_exception_handler(_FakeRequest(), exc)
        body = resp.body.decode()
        assert "psycopg2" not in body
        assert "password" not in body
        assert "admin" not in body
        assert "Internal server error" in body

    def test_error_envelope_has_request_id(self):
        resp = _build_error_response(500, "test", _FakeRequest())
        body = resp.body.decode()
        assert "owasp-test-001" in body

    def test_no_api_source_leaks_exception(self):
        """Regression: scan all API router files for str(e) in responses."""
        api_base = os.path.join(
            os.path.dirname(__file__), "..", "..", "spiderfoot", "api",
        )
        api_base = os.path.normpath(api_base)

        leak_pattern = re.compile(r"""detail\s*=\s*f['"].*\{e\}""")
        violations = []

        for root, _, files in os.walk(os.path.join(api_base, "routers")):
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, 1):
                        if line.strip().startswith(("log.", "_log.", "logger.")):
                            continue
                        if line.strip().startswith("#"):
                            continue
                        if leak_pattern.search(line):
                            violations.append(f"{f}:{lineno}")

        assert not violations, f"Exception leaks found: {violations}"


# ═══════════════════════════════════════════════════════════════════════════
# A09 — Security Logging and Monitoring Failures
# ═══════════════════════════════════════════════════════════════════════════

class TestA09SecurityLogging:
    """Verify security events produce log output (not silent failures)."""

    @pytest.mark.asyncio
    async def test_unhandled_exception_is_logged(self, caplog):
        """The global exception handler must log the error."""
        import logging
        with caplog.at_level(logging.ERROR):
            await _unhandled_exception_handler(
                _FakeRequest(),
                RuntimeError("something bad"),
            )
        assert any("Unhandled exception" in r.message for r in caplog.records)


# ═══════════════════════════════════════════════════════════════════════════
# A10 — Server-Side Request Forgery (SSRF)
# ═══════════════════════════════════════════════════════════════════════════

class TestA10SSRF:
    """Verify SSRF protection on webhook/callback URLs."""

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/admin",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/admin",
    ])
    def test_private_ips_blocked(self, url):
        with pytest.raises(ValueError):
            ValidationUtils.validate_url_no_ssrf(url)

    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",
        "gopher://evil.com/payload",
        "ftp://internal/data",
    ])
    def test_dangerous_schemes_blocked(self, url):
        with pytest.raises(ValueError, match="not allowed"):
            ValidationUtils.validate_url_no_ssrf(url)

    def test_embedded_credentials_blocked(self):
        with pytest.raises(ValueError, match="credentials"):
            ValidationUtils.validate_url_no_ssrf("https://admin:pass@hook.example.com")

    def test_dns_rebinding_to_private_blocked(self):
        fake_results = [(2, 1, 6, '', ('10.0.0.5', 0))]
        with patch("socket.getaddrinfo", return_value=fake_results):
            with pytest.raises(ValueError, match="private IP"):
                ValidationUtils.validate_url_no_ssrf("https://rebind.attacker.com/hook")

    def test_valid_public_webhook_passes(self):
        result = ValidationUtils.validate_url_no_ssrf("https://hooks.slack.com/services/T00/B00/xxx")
        assert "hooks.slack.com" in result
