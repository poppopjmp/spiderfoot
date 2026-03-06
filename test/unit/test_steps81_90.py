"""Tests for Steps 81-90 security hardening features.

Covers:
- Step 83: Log scrubbing (SensitiveDataFilter)
- Step 84: Session absolute lifetime enforcement
- Step 85: Rate limit IP hardening
- Step 86: SSRF input validation
- Step 87: CSP nonce support + X-XSS-Protection removal
- Step 89: URL query parameter scrubbing
"""
import logging
import re
import time
import unittest


class TestLogScrubbing(unittest.TestCase):
    """Step 83: SensitiveDataFilter redacts secrets from log messages."""

    @classmethod
    def setUpClass(cls):
        from spiderfoot.observability.logging_config import SensitiveDataFilter
        cls.f = SensitiveDataFilter()

    def test_jwt_redacted(self):
        # JWT as standalone (not preceded by token= pattern)
        msg = "Found eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U in response"
        result = self.f.scrub(msg)
        self.assertIn("***JWT_REDACTED***", result)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", result)

    def test_bearer_token_redacted(self):
        msg = "Authorization: Bearer sk-1234567890abcdefghij"
        result = self.f.scrub(msg)
        self.assertIn("***REDACTED***", result)
        self.assertNotIn("1234567890abcdefghij", result)

    def test_password_redacted(self):
        msg = 'user=admin password=MyS3cret'
        result = self.f.scrub(msg)
        self.assertIn("***REDACTED***", result)
        self.assertNotIn("MyS3cret", result)
        # Non-sensitive params preserved
        self.assertIn("user=admin", result)

    def test_api_key_prefix_redacted(self):
        msg = "Using sf_key_abcd1234567890xyz"
        result = self.f.scrub(msg)
        self.assertIn("***REDACTED***", result)
        self.assertNotIn("1234567890xyz", result)

    def test_safe_text_unchanged(self):
        msg = "Processing scan for example.com"
        result = self.f.scrub(msg)
        self.assertEqual(msg, result)

    def test_filter_modifies_log_record(self):
        """Filter should modify record.msg in-place."""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Bearer abcd1234567890",
            args=(), exc_info=None,
        )
        self.f.filter(record)
        self.assertIn("***REDACTED***", record.msg)

    def test_filter_scrubs_args_tuple(self):
        """Filter should scrub string args in tuple form."""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="User %s logged in with password=%s",
            args=("admin", "password=secret123"),
            exc_info=None,
        )
        self.f.filter(record)
        self.assertIn("***REDACTED***", record.args[1])

    def test_generic_secret_key_value(self):
        msg = "secret=verysecretvalue123 token=tok_abc_xyz_123"
        result = self.f.scrub(msg)
        self.assertNotIn("verysecretvalue123", result)
        self.assertNotIn("tok_abc_xyz_123", result)


class TestSessionAbsoluteLifetime(unittest.TestCase):
    """Step 84: SessionManager enforces absolute lifetime."""

    def test_default_max_lifetime(self):
        from spiderfoot.security.session_security import SessionManager
        s = SessionManager()
        self.assertEqual(s._max_lifetime, 86400)  # 24 hours default

    def test_configurable_max_lifetime(self):
        from spiderfoot.security.session_security import SessionManager
        s = SessionManager({"security.session_max_lifetime": 7200})
        self.assertEqual(s._max_lifetime, 7200)

    def test_created_at_stored(self):
        from spiderfoot.security.session_security import SessionManager
        s = SessionManager()
        s.validate_session("test-sess", "1.2.3.4", "Chrome")
        info = s._sessions["test-sess"]
        self.assertIn("created_at", info)
        self.assertIsInstance(info["created_at"], float)

    def test_absolute_lifetime_expired(self):
        """Sessions past max_lifetime should be rejected."""
        from spiderfoot.security.session_security import SessionManager
        s = SessionManager({"security.session_max_lifetime": 1})  # 1 second
        s.validate_session("expire-sess", "1.2.3.4", "Chrome")
        # Manually backdate created_at
        s._sessions["expire-sess"]["created_at"] = time.monotonic() - 2
        result = s.validate_session("expire-sess", "1.2.3.4", "Chrome")
        self.assertFalse(result)
        self.assertNotIn("expire-sess", s._sessions)

    def test_revoke_session(self):
        from spiderfoot.security.session_security import SessionManager
        s = SessionManager()
        s.validate_session("revoke-me", "1.2.3.4", "Chrome")
        self.assertTrue(s.revoke_session("revoke-me"))
        self.assertFalse(s.revoke_session("revoke-me"))  # already revoked

    def test_cleanup_expired(self):
        from spiderfoot.security.session_security import SessionManager
        s = SessionManager({"security.session_timeout": 1})
        s.validate_session("old-sess", "1.2.3.4", "Chrome")
        s._sessions["old-sess"]["last_active"] = time.monotonic() - 10
        purged = s.cleanup_expired()
        self.assertEqual(purged, 1)
        self.assertEqual(s.active_count, 0)

    def test_active_count(self):
        from spiderfoot.security.session_security import SessionManager
        s = SessionManager()
        self.assertEqual(s.active_count, 0)
        s.validate_session("s1", "1.2.3.4", "Chrome")
        s.validate_session("s2", "1.2.3.5", "Firefox")
        self.assertEqual(s.active_count, 2)


class TestRateLimitIPHardening(unittest.TestCase):
    """Step 85: Rate limit X-Forwarded-For default and IP validation."""

    def test_trust_forwarded_default_false(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig
        config = RateLimitConfig()
        self.assertFalse(config.trust_forwarded)

    def test_from_dict_trust_forwarded_default_false(self):
        from spiderfoot.api.rate_limit_middleware import RateLimitConfig
        config = RateLimitConfig.from_dict({})
        self.assertFalse(config.trust_forwarded)

    def test_extract_identity_ignores_forwarded_by_default(self):
        from spiderfoot.api.rate_limit_middleware import extract_client_identity
        scope = {"client": ("192.168.1.1", 12345)}
        headers = {"x-forwarded-for": "10.0.0.1, 192.168.1.1"}
        identity = extract_client_identity(scope, headers, trust_forwarded=False)
        self.assertEqual(identity, "ip:192.168.1.1")

    def test_extract_identity_uses_forwarded_when_trusted(self):
        from spiderfoot.api.rate_limit_middleware import extract_client_identity
        scope = {"client": ("192.168.1.1", 12345)}
        headers = {"x-forwarded-for": "10.0.0.1, 192.168.1.1"}
        identity = extract_client_identity(scope, headers, trust_forwarded=True)
        self.assertEqual(identity, "ip:10.0.0.1")

    def test_extract_identity_rejects_invalid_forwarded_ip(self):
        from spiderfoot.api.rate_limit_middleware import extract_client_identity
        scope = {"client": ("192.168.1.1", 12345)}
        headers = {"x-forwarded-for": "<script>alert(1)</script>"}
        identity = extract_client_identity(scope, headers, trust_forwarded=True)
        # Should fall through to direct connection IP
        self.assertEqual(identity, "ip:192.168.1.1")

    def test_api_key_uses_sha256_hash(self):
        """API key identity should use SHA256 hash, not raw prefix."""
        from spiderfoot.api.rate_limit_middleware import extract_client_identity
        import hashlib
        scope = {"client": ("1.2.3.4", 12345)}
        token = "my-secret-api-key-12345"
        headers = {"authorization": f"Bearer {token}"}
        identity = extract_client_identity(scope, headers)
        expected_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
        self.assertEqual(identity, f"apikey:{expected_hash}")

    def test_ip_validation_function(self):
        from spiderfoot.api.rate_limit_middleware import _validate_ip
        self.assertTrue(_validate_ip("192.168.1.1"))
        self.assertTrue(_validate_ip("::1"))
        self.assertTrue(_validate_ip("10.0.0.1"))
        self.assertFalse(_validate_ip("not-an-ip"))
        self.assertFalse(_validate_ip("<script>"))
        self.assertFalse(_validate_ip(""))


class TestSSRFProtection(unittest.TestCase):
    """Step 86: Input validation SSRF protections."""

    @classmethod
    def setUpClass(cls):
        from spiderfoot.security.input_validation import InputValidator
        cls.v = InputValidator()

    def test_blocks_aws_metadata(self):
        ok, reason = self.v.validate_url_target("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(ok)
        self.assertIn("metadata", reason)

    def test_blocks_gcp_metadata(self):
        ok, reason = self.v.validate_url_target("http://metadata.google.internal/computeMetadata/v1/")
        self.assertFalse(ok)

    def test_blocks_localhost(self):
        ok, _ = self.v.validate_url_target("http://localhost:8080")
        self.assertFalse(ok)

    def test_blocks_private_ip(self):
        ok, reason = self.v.validate_url_target("http://10.0.0.1/admin")
        self.assertFalse(ok)
        self.assertIn("private", reason)

    def test_blocks_loopback(self):
        ok, _ = self.v.validate_url_target("http://127.0.0.1")
        self.assertFalse(ok)

    def test_blocks_file_scheme(self):
        ok, reason = self.v.validate_url_target("file:///etc/passwd")
        self.assertFalse(ok)
        self.assertIn("scheme", reason)

    def test_blocks_ftp_scheme(self):
        ok, _ = self.v.validate_url_target("ftp://files.example.com")
        self.assertFalse(ok)

    def test_blocks_redis_port(self):
        ok, reason = self.v.validate_url_target("http://db.company.com:6379")
        self.assertFalse(ok)
        self.assertIn("port", reason)

    def test_blocks_embedded_credentials(self):
        ok, reason = self.v.validate_url_target("http://admin:password@example.com")
        self.assertFalse(ok)
        self.assertIn("credentials", reason)

    def test_allows_safe_url(self):
        ok, reason = self.v.validate_url_target("https://example.com")
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_allows_http_url(self):
        ok, _ = self.v.validate_url_target("http://scan-target.example.org/path")
        self.assertTrue(ok)

    def test_rejects_empty(self):
        ok, _ = self.v.validate_url_target("")
        self.assertFalse(ok)

    def test_is_private_ip(self):
        self.assertTrue(self.v.is_private_ip("10.0.0.1"))
        self.assertTrue(self.v.is_private_ip("192.168.1.1"))
        self.assertTrue(self.v.is_private_ip("172.16.0.1"))
        self.assertTrue(self.v.is_private_ip("127.0.0.1"))
        self.assertFalse(self.v.is_private_ip("8.8.8.8"))
        self.assertFalse(self.v.is_private_ip("not-an-ip"))


class TestCSPNonceAndHeaders(unittest.TestCase):
    """Step 87 + 90: CSP nonce support and X-XSS-Protection removal."""

    def test_generate_nonce(self):
        from spiderfoot.security.input_validation import SecurityHeaders
        nonce = SecurityHeaders.generate_nonce()
        self.assertIsInstance(nonce, str)
        self.assertGreater(len(nonce), 10)

    def test_nonce_is_unique(self):
        from spiderfoot.security.input_validation import SecurityHeaders
        nonces = {SecurityHeaders.generate_nonce() for _ in range(100)}
        self.assertEqual(len(nonces), 100)

    def test_csp_includes_nonce_when_provided(self):
        from spiderfoot.security.input_validation import SecurityHeaders
        nonce = "test-nonce-abc123"
        headers = SecurityHeaders.get_headers(nonce=nonce)
        csp = headers["Content-Security-Policy"]
        self.assertIn(f"'nonce-{nonce}'", csp)

    def test_csp_without_nonce(self):
        from spiderfoot.security.input_validation import SecurityHeaders
        headers = SecurityHeaders.get_headers()
        csp = headers["Content-Security-Policy"]
        self.assertNotIn("nonce-", csp)
        self.assertIn("'self'", csp)

    def test_no_x_xss_protection(self):
        """X-XSS-Protection is deprecated and should not be present."""
        from spiderfoot.security.input_validation import SecurityHeaders
        headers = SecurityHeaders.get_headers()
        self.assertNotIn("X-XSS-Protection", headers)

    def test_frame_ancestors_none(self):
        from spiderfoot.security.input_validation import SecurityHeaders
        headers = SecurityHeaders.get_headers()
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_base_uri_self(self):
        from spiderfoot.security.input_validation import SecurityHeaders
        headers = SecurityHeaders.get_headers()
        self.assertIn("base-uri 'self'", headers["Content-Security-Policy"])

    def test_form_action_self(self):
        from spiderfoot.security.input_validation import SecurityHeaders
        headers = SecurityHeaders.get_headers()
        self.assertIn("form-action 'self'", headers["Content-Security-Policy"])


class TestURLScrubbing(unittest.TestCase):
    """Step 89: API key scrubbing from URL query parameters."""

    def test_api_key_scrubbed(self):
        from spiderfoot.observability.request_tracing import scrub_url
        result = scrub_url("/api/scan?api_key=secret123&target=example.com")
        self.assertIn("api_key=***", result)
        self.assertNotIn("secret123", result)
        self.assertIn("target=example.com", result)

    def test_multiple_sensitive_params(self):
        from spiderfoot.observability.request_tracing import scrub_url
        result = scrub_url("/api?token=tok123&password=pw&name=test")
        self.assertIn("token=***", result)
        self.assertIn("password=***", result)
        self.assertIn("name=test", result)

    def test_no_params_unchanged(self):
        from spiderfoot.observability.request_tracing import scrub_url
        url = "/api/scan/results"
        self.assertEqual(scrub_url(url), url)

    def test_safe_params_preserved(self):
        from spiderfoot.observability.request_tracing import scrub_url
        url = "/api/scan?target=example.com&format=json"
        self.assertEqual(scrub_url(url), url)

    def test_access_token_scrubbed(self):
        from spiderfoot.observability.request_tracing import scrub_url
        result = scrub_url("/callback?access_token=abc123def456")
        self.assertIn("access_token=***", result)
        self.assertNotIn("abc123def456", result)

    def test_sensitive_params_list(self):
        from spiderfoot.observability.request_tracing import _SENSITIVE_PARAMS
        required = {"api_key", "token", "password", "secret", "access_token"}
        self.assertTrue(required.issubset(_SENSITIVE_PARAMS))


if __name__ == "__main__":
    unittest.main()
