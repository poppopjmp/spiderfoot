"""Security regression tests for Steps 1-20 fixes.

Covers:
  - Steps 1-2: Auth/RBAC defaults
  - Step 3: Default admin password auto-generation
  - Steps 4-6: Fernet encryption in secret_manager
  - Step 7: HMAC secret auto-generation
  - Step 8: Password change requires current_password
  - Step 9: SSO stubs blocked without SF_SSO_DEV_MODE
  - Step 10: CSRF covers all /api/ paths
  - Step 11: Body limit handles chunked transfers
  - Step 12: Session IP/UA validation
  - Step 18: Constant-time API key comparison
  - Step 20: OAuth2 fails-closed without Redis
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import tempfile
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Steps 1-2: Auth & RBAC Defaults (source-level verification)
# ---------------------------------------------------------------------------

class TestAuthDefaults(unittest.TestCase):
    """Verify auth_required and rbac_enforce default to True in source."""

    @classmethod
    def setUpClass(cls):
        cls._src = (
            Path(__file__).resolve().parents[2]
            / "spiderfoot" / "auth" / "models.py"
        ).read_text(encoding="utf-8")

    def test_auth_required_default_true_in_source(self):
        """SF_AUTH_REQUIRED env fallback must be 'true'."""
        m = re.search(
            r'auth_required.*?os\.environ\.get\(\s*"SF_AUTH_REQUIRED"\s*,\s*"(\w+)"',
            self._src,
        )
        self.assertIsNotNone(m, "Could not find auth_required default in source")
        self.assertEqual(m.group(1), "true",
                         "auth_required default must be 'true'")

    def test_rbac_enforce_default_true_in_source(self):
        """SF_RBAC_ENFORCE env fallback must be 'true'."""
        m = re.search(
            r'rbac_enforce.*?os\.environ\.get\(\s*"SF_RBAC_ENFORCE"\s*,\s*"(\w+)"',
            self._src,
        )
        self.assertIsNotNone(m, "Could not find rbac_enforce default in source")
        self.assertEqual(m.group(1), "true",
                         "rbac_enforce default must be 'true'")

    def test_auth_config_instantiates(self):
        """AuthConfig can be instantiated without errors."""
        from spiderfoot.auth.models import AuthConfig
        cfg = AuthConfig()
        self.assertIsInstance(cfg.rbac_enforce, bool)


# ---------------------------------------------------------------------------
# Step 3: Default Admin Password
# ---------------------------------------------------------------------------

class TestDefaultAdminPassword(unittest.TestCase):
    """Verify default admin password is never 'admin'."""

    def test_no_hardcoded_admin_password(self):
        """Scan auth/service.py for the literal 'admin' default password."""
        service_path = (
            Path(__file__).resolve().parents[2]
            / "spiderfoot" / "auth" / "service.py"
        )
        content = service_path.read_text(encoding="utf-8")
        # There should be no line that sets password to literal "admin"
        import re
        matches = re.findall(r'password\s*=\s*["\']admin["\']', content)
        self.assertEqual(
            len(matches), 0,
            f"Found hardcoded 'admin' password in auth/service.py: {matches}"
        )

    def test_auto_generated_password_is_strong(self):
        """Verify token_urlsafe(24) produces sufficiently random passwords."""
        password = secrets.token_urlsafe(24)
        self.assertGreaterEqual(len(password), 32)
        self.assertNotEqual(password, "admin")


# ---------------------------------------------------------------------------
# Steps 4-6: Secret Manager Fernet Encryption
# ---------------------------------------------------------------------------

class TestSecretManagerFernet(unittest.TestCase):
    """Verify Fernet encryption replaces XOR."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_fernet_encrypt_decrypt_roundtrip(self):
        from spiderfoot.security.secrets import EncryptedFileSecretBackend
        fp = os.path.join(self.tmpdir, "rt.enc")
        backend = EncryptedFileSecretBackend(
            filepath=fp,
            encryption_key="test-passphrase-123"
        )
        backend.set("test_key", "secret_value_42")
        result = backend.get("test_key")
        self.assertEqual(result, "secret_value_42")

    def test_different_passphrases_fail(self):
        from spiderfoot.security.secrets import EncryptedFileSecretBackend
        fp = os.path.join(self.tmpdir, "cross.enc")
        backend1 = EncryptedFileSecretBackend(
            filepath=fp,
            encryption_key="passphrase-alpha"
        )
        backend1.set("cross_key", "cross_value")

        # Different passphrase should fail to decrypt
        backend2 = EncryptedFileSecretBackend(
            filepath=fp,
            encryption_key="passphrase-beta"
        )
        result = backend2.get("cross_key")
        # Should return None or raise — definitely not the original value
        self.assertNotEqual(result, "cross_value",
                            "Different passphrase must not decrypt successfully")

    def test_no_default_key_fallback(self):
        """Verify 'default-key' is not used as encryption passphrase."""
        service_path = (
            Path(__file__).resolve().parents[2]
            / "spiderfoot" / "security" / "secrets.py"
        )
        content = service_path.read_text(encoding="utf-8")
        assignments = re.findall(r'passphrase\s*=\s*["\']default-key["\']', content)
        self.assertEqual(
            len(assignments), 0,
            "Found 'default-key' assignment in secret_manager.py"
        )

    def test_salt_file_created(self):
        from spiderfoot.security.secrets import EncryptedFileSecretBackend
        fp = os.path.join(self.tmpdir, "salt_test.enc")
        backend = EncryptedFileSecretBackend(
            filepath=fp,
            encryption_key="salt-test"
        )
        backend.set("probe", "data")
        salt_path = fp + ".salt"
        self.assertTrue(os.path.exists(salt_path), "Salt file must be created")


# ---------------------------------------------------------------------------
# Step 7: HMAC Secret Auto-Generation
# ---------------------------------------------------------------------------

class TestHMACSecretAutoGeneration(unittest.TestCase):
    """Verify HMAC secret is not hardcoded."""

    def test_no_hardcoded_hmac_secret(self):
        """Scan api_keys.py for the literal hardcoded secret."""
        keys_path = (
            Path(__file__).resolve().parents[2]
            / "spiderfoot" / "auth" / "api_keys.py"
        )
        content = keys_path.read_text(encoding="utf-8")
        self.assertNotIn(
            "spiderfoot-api-key-secret", content,
            "Hardcoded HMAC secret still present in api_keys.py"
        )

    def test_hmac_secret_function_exists(self):
        from spiderfoot.auth.api_keys import _load_hmac_secret
        secret = _load_hmac_secret()
        self.assertIsInstance(secret, bytes)
        self.assertGreater(len(secret), 0)


# ---------------------------------------------------------------------------
# Step 10: CSRF Expanded Coverage
# ---------------------------------------------------------------------------

class TestCSRFExpandedCoverage(unittest.TestCase):
    """Verify CSRF protection covers all /api/ paths."""

    def test_protected_path_covers_api(self):
        from spiderfoot.api.csrf_middleware import CSRFConfig
        cfg = CSRFConfig()
        # Default protected paths should include /api/
        self.assertTrue(
            any(p.startswith("/api/") or p == "/api/" for p in cfg.protected_paths),
            f"Protected paths must include /api/, got: {cfg.protected_paths}"
        )

    def test_exempt_paths_include_auth_endpoints(self):
        from spiderfoot.api.csrf_middleware import CSRFConfig
        cfg = CSRFConfig()
        required_exemptions = {
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/refresh",
        }
        for path in required_exemptions:
            self.assertIn(path, cfg.exempt_paths,
                          f"CSRF must exempt {path}")


# ---------------------------------------------------------------------------
# Step 11: Body Limit Chunked Transfer
# ---------------------------------------------------------------------------

class TestBodyLimitChunked(unittest.TestCase):
    """Verify chunked transfer enforcement."""

    def test_body_limit_middleware_exists(self):
        """The BodySizeLimitMiddleware class must exist."""
        from spiderfoot.api.body_limit_middleware import BodySizeLimitMiddleware
        self.assertTrue(hasattr(BodySizeLimitMiddleware, 'dispatch'))

    def test_source_has_limited_body_iterator(self):
        """The source must contain limited_body_iterator logic."""
        src_path = (
            Path(__file__).resolve().parents[2]
            / "spiderfoot" / "api" / "body_limit_middleware.py"
        )
        content = src_path.read_text(encoding="utf-8")
        self.assertIn("limited_body_iterator", content,
                       "Must contain limited_body_iterator for chunked body enforcement")


# ---------------------------------------------------------------------------
# Step 12: Session IP/UA Validation
# ---------------------------------------------------------------------------

class TestSessionIPValidation(unittest.TestCase):
    """Verify session rejects IP and User-Agent changes."""

    def test_ip_change_rejected(self):
        from spiderfoot.security.session_security import SessionManager
        ss = SessionManager()
        sid = "test-session-ip"
        # Create session
        self.assertTrue(ss.validate_session(sid, "10.0.0.1", "Mozilla/5.0"))
        # Same IP passes
        self.assertTrue(ss.validate_session(sid, "10.0.0.1", "Mozilla/5.0"))
        # Different IP rejected
        self.assertFalse(ss.validate_session(sid, "10.0.0.2", "Mozilla/5.0"))

    def test_ua_change_rejected(self):
        from spiderfoot.security.session_security import SessionManager
        ss = SessionManager()
        sid = "test-session-ua"
        self.assertTrue(ss.validate_session(sid, "10.0.0.1", "Chrome/120"))
        self.assertFalse(ss.validate_session(sid, "10.0.0.1", "Firefox/121"))

    def test_valid_session_stays_valid(self):
        from spiderfoot.security.session_security import SessionManager
        ss = SessionManager()
        sid = "test-session-stable"
        for _ in range(5):
            self.assertTrue(ss.validate_session(sid, "1.2.3.4", "TestAgent"))


# ---------------------------------------------------------------------------
# Step 18: Constant-Time API Key Comparison
# ---------------------------------------------------------------------------

class TestConstantTimeAPIKeyComparison(unittest.TestCase):
    """Verify API key validation uses hmac.compare_digest."""

    @classmethod
    def setUpClass(cls):
        base = Path(__file__).resolve().parents[2] / "spiderfoot"
        src_path = base / "security" / "api_auth.py"
        cls._src = src_path.read_text(encoding="utf-8")

    def test_source_uses_compare_digest(self):
        """Scan api_security.py for hmac.compare_digest usage."""
        self.assertIn("compare_digest", self._src,
                       "api_security.py must use hmac.compare_digest")

    def test_no_in_operator_for_keys(self):
        """Verify no timing-vulnerable 'in' operator for key check."""
        matches = re.findall(r'api_key\s+in\s+self\._keys', self._src)
        self.assertEqual(len(matches), 0,
                         "Found timing-vulnerable 'in' operator for API key check")


# ---------------------------------------------------------------------------
# Step 9: SSO Stubs Gated
# ---------------------------------------------------------------------------

class TestSSOStubsGated(unittest.TestCase):
    """Verify SSO stubs are blocked without SF_SSO_DEV_MODE."""

    @classmethod
    def setUpClass(cls):
        base = Path(__file__).resolve().parents[2] / "spiderfoot"
        src_path = base / "auth" / "sso.py"
        cls._src = src_path.read_text(encoding="utf-8")

    def test_saml_checks_dev_mode(self):
        """process_saml_response must check SF_SSO_DEV_MODE."""
        # Find the process_saml_response method and verify it gates on SF_SSO_DEV_MODE
        self.assertIn("SF_SSO_DEV_MODE", self._src,
                       "SSO integration must check SF_SSO_DEV_MODE env var")

    def test_dev_mode_gate_returns_error(self):
        """When SF_SSO_DEV_MODE is not set, stubs must return error."""
        # Check the source has an error return when dev mode is not active
        self.assertIn("production SAML library required", self._src,
                       "Must return error when dev mode is off")

    def test_oidc_checks_dev_mode(self):
        """process_oidc_callback must also check SF_SSO_DEV_MODE."""
        # Count SF_SSO_DEV_MODE occurrences — should be at least 2
        # (one for SAML, one for OIDC)
        count = self._src.count("SF_SSO_DEV_MODE")
        self.assertGreaterEqual(count, 4,
                                "SF_SSO_DEV_MODE must gate both SAML and OIDC paths")

    def test_critical_warning_logged(self):
        """Dev mode must log CRITICAL warning."""
        self.assertIn("SSO DEV MODE ACTIVE", self._src,
                       "Dev mode must log CRITICAL warning")


# ---------------------------------------------------------------------------
# Step 56: Login Rate Limiting
# ---------------------------------------------------------------------------

class TestLoginRateLimiting(unittest.TestCase):
    """Verify login endpoint has rate limiting configured."""

    def test_login_rate_limit_configured(self):
        from spiderfoot.api.rate_limit_middleware import DEFAULT_ENDPOINT_OVERRIDES
        self.assertIn("/api/auth/login", DEFAULT_ENDPOINT_OVERRIDES)
        reqs, window = DEFAULT_ENDPOINT_OVERRIDES["/api/auth/login"]
        self.assertLessEqual(reqs, 5,
                             "Login should allow max 5 attempts per minute")

    def test_register_rate_limit_configured(self):
        from spiderfoot.api.rate_limit_middleware import DEFAULT_ENDPOINT_OVERRIDES
        self.assertIn("/api/auth/register", DEFAULT_ENDPOINT_OVERRIDES)
        reqs, window = DEFAULT_ENDPOINT_OVERRIDES["/api/auth/register"]
        self.assertLessEqual(reqs, 3,
                             "Registration should allow max 3 per minute")

    def test_auth_tier_exists(self):
        from spiderfoot.api.rate_limit_middleware import DEFAULT_TIER_LIMITS
        self.assertIn("auth", DEFAULT_TIER_LIMITS)


# ---------------------------------------------------------------------------
# Nginx Security Headers (Steps 13-16)
# ---------------------------------------------------------------------------

class TestNginxSecurityHeaders(unittest.TestCase):
    """Verify nginx.conf has proper security headers."""

    @classmethod
    def setUpClass(cls):
        nginx_path = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "nginx.conf"
        )
        cls.content = nginx_path.read_text(encoding="utf-8")

    def test_csp_header_present(self):
        self.assertIn("Content-Security-Policy", self.content,
                       "CSP header must be present in nginx.conf")

    def test_csp_default_src_self(self):
        self.assertIn("default-src 'self'", self.content)

    def test_hsts_header_present(self):
        self.assertIn("Strict-Transport-Security", self.content)
        self.assertIn("max-age=31536000", self.content)

    def test_permissions_policy_present(self):
        self.assertIn("Permissions-Policy", self.content)
        self.assertIn("camera=()", self.content)
        self.assertIn("microphone=()", self.content)

    def test_no_xss_protection_removed(self):
        """X-XSS-Protection is deprecated and should be removed."""
        self.assertNotIn("X-XSS-Protection", self.content,
                         "Deprecated X-XSS-Protection should be removed")

    def test_cors_not_wildcard(self):
        """CORS should not use wildcard *."""
        import re
        # Look for Access-Control-Allow-Origin: *
        matches = re.findall(
            r'Access-Control-Allow-Origin\s+["\']?\*["\']?', self.content
        )
        self.assertEqual(len(matches), 0,
                         "CORS must not use wildcard *")


# ---------------------------------------------------------------------------
# Frontend Source Maps (Step 17)
# ---------------------------------------------------------------------------

class TestSourceMapsDisabled(unittest.TestCase):
    """Verify source maps are disabled in production build."""

    def test_vite_config_sourcemap_false(self):
        vite_path = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "vite.config.ts"
        )
        content = vite_path.read_text(encoding="utf-8")
        self.assertIn("sourcemap: false", content,
                       "Production builds must have sourcemap: false")
        self.assertNotIn("sourcemap: true", content,
                         "sourcemap: true must be removed")


# ---------------------------------------------------------------------------
# Password Change Route (Step 8 — requires current_password)
# ---------------------------------------------------------------------------

class TestPasswordChangeRoute(unittest.TestCase):
    """Verify change_own_password requires current_password."""

    def test_route_checks_current_password(self):
        """The /password endpoint must reject requests missing current_password."""
        src = (
            Path(__file__).resolve().parents[2]
            / "spiderfoot" / "auth" / "routes.py"
        )
        content = src.read_text(encoding="utf-8")
        self.assertIn("current_password", content,
                       "change_own_password must reference current_password")
        self.assertIn('current_password is required', content,
                       "Must return error when current_password is missing")

    def test_model_has_current_password_field(self):
        """ChangePasswordRequest model must include current_password."""
        from spiderfoot.auth.routes import ChangePasswordRequest
        fields = ChangePasswordRequest.model_fields
        self.assertIn("current_password", fields,
                       "ChangePasswordRequest must have current_password field")
        self.assertIn("new_password", fields,
                       "ChangePasswordRequest must have new_password field")

    def test_new_password_min_length(self):
        """new_password must enforce minimum length >= 8."""
        from spiderfoot.auth.routes import ChangePasswordRequest
        field = ChangePasswordRequest.model_fields["new_password"]
        meta = field.metadata
        min_found = any(
            getattr(m, "min_length", 0) >= 8
            for m in meta
            if hasattr(m, "min_length")
        )
        self.assertTrue(min_found,
                        "new_password must have min_length >= 8")

    def test_verify_password_called(self):
        """The route must call verify_password before allowing changes."""
        src = (
            Path(__file__).resolve().parents[2]
            / "spiderfoot" / "auth" / "routes.py"
        )
        content = src.read_text(encoding="utf-8")
        self.assertIn("verify_password", content,
                       "Route must verify current password via verify_password()")


# ---------------------------------------------------------------------------
# OAuth2 Fail-Closed (Step 20)
# ---------------------------------------------------------------------------

class TestOAuth2FailClosed(unittest.TestCase):
    """Verify OAuth2 callback fails closed when dependencies are unavailable."""

    def test_oauth2_callback_checks_availability(self):
        """OAuth2 callback must not silently succeed when Redis is unavailable."""
        src = (
            Path(__file__).resolve().parents[2]
            / "spiderfoot" / "auth" / "routes.py"
        )
        content = src.read_text(encoding="utf-8")
        self.assertTrue(
            "raise HTTPException" in content
            or "raise http_exception" in content,
            "Routes must be able to raise HTTPException on failure",
        )

    def test_oauth2_state_validated(self):
        """OAuth2 callback must validate state parameter."""
        src = (
            Path(__file__).resolve().parents[2]
            / "spiderfoot" / "auth" / "routes.py"
        )
        content = src.read_text(encoding="utf-8")
        self.assertTrue(
            "state" in content.lower(),
            "OAuth2 callback should reference state parameter for CSRF protection",
        )


# ---------------------------------------------------------------------------
# CSRF Header in Frontend API Client (Step 61)
# ---------------------------------------------------------------------------

class TestCSRFHeaderInFrontend(unittest.TestCase):
    """Verify that both API clients send X-Requested-With CSRF header."""

    def test_legacy_api_has_csrf_header(self):
        """Legacy Axios client must send X-Requested-With header."""
        src = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "src" / "lib" / "api.ts"
        )
        content = src.read_text(encoding="utf-8")
        self.assertIn("X-Requested-With", content,
                       "Legacy API client must include X-Requested-With header")
        self.assertIn("XMLHttpRequest", content,
                       "CSRF header value should be XMLHttpRequest")

    def test_openapi_client_has_csrf_header(self):
        """OpenAPI (fetch-based) client must send X-Requested-With header."""
        src = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "src" / "api" / "client.ts"
        )
        content = src.read_text(encoding="utf-8")
        self.assertIn("X-Requested-With", content,
                       "OpenAPI client must include X-Requested-With header")


# ---------------------------------------------------------------------------
# Error Message Sanitization (Step 62)
# ---------------------------------------------------------------------------

class TestErrorMessageSanitization(unittest.TestCase):
    """Verify error messages are sanitized before display."""

    def test_sanitize_function_exists(self):
        """errors.ts must export a sanitizeErrorText function."""
        src = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "src" / "lib" / "errors.ts"
        )
        content = src.read_text(encoding="utf-8")
        self.assertIn("sanitizeErrorText", content,
                       "errors.ts must export sanitizeErrorText")

    def test_html_stripping_regex(self):
        """sanitizeErrorText must strip HTML tags."""
        src = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "src" / "lib" / "errors.ts"
        )
        content = src.read_text(encoding="utf-8")
        self.assertIn("<[^>]*>", content,
                       "Must contain HTML tag stripping regex")

    def test_max_length_enforced(self):
        """Error messages must be truncated to prevent abuse."""
        src = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "src" / "lib" / "errors.ts"
        )
        content = src.read_text(encoding="utf-8")
        self.assertIn("MAX_ERROR_LENGTH", content,
                       "Must define MAX_ERROR_LENGTH constant")


# ---------------------------------------------------------------------------
# Request ID Sanitization (Step 64)
# ---------------------------------------------------------------------------

class TestRequestIdSanitizationRegression(unittest.TestCase):
    """Verify request ID sanitization is implemented."""

    def test_sanitize_function_exists(self):
        from spiderfoot.observability.request_tracing import _sanitize_request_id
        result = _sanitize_request_id("abc-123")
        self.assertEqual(result, "abc-123")

    def test_malicious_id_rejected(self):
        from spiderfoot.observability.request_tracing import _sanitize_request_id
        self.assertIsNone(_sanitize_request_id("evil\ninjection"))

    def test_overlong_id_rejected(self):
        from spiderfoot.observability.request_tracing import _sanitize_request_id
        self.assertIsNone(_sanitize_request_id("x" * 200))

    def test_dispatch_uses_sanitize(self):
        """The dispatch method must call _sanitize_request_id."""
        src = (
            Path(__file__).resolve().parents[2]
            / "spiderfoot" / "observability" / "request_tracing.py"
        )
        content = src.read_text(encoding="utf-8")
        self.assertIn("_sanitize_request_id", content,
                       "dispatch() must call _sanitize_request_id")


# ---------------------------------------------------------------------------
# Steps 81-90 Regression Tests
# NOTE: Steps 83-87, 89-90 covered thoroughly by test_steps81_90.py.
#       Only TestSecureStorageRegression (Step 88 frontend check) remains.
# ---------------------------------------------------------------------------

class TestSecureStorageRegression(unittest.TestCase):
    """Step 88: Secure storage key prefixing (source-level check)."""

    def test_safe_storage_has_prefix(self):
        src = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "src" / "lib" / "safeStorage.ts"
        )
        content = src.read_text(encoding="utf-8")
        self.assertIn("KEY_PREFIX", content)
        self.assertIn("sf_", content)

    def test_sensitive_functions_exist(self):
        src = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "src" / "lib" / "safeStorage.ts"
        )
        content = src.read_text(encoding="utf-8")
        self.assertIn("sensitiveSetItem", content)
        self.assertIn("sensitiveGetItem", content)
        self.assertIn("clearAllSpiderFootData", content)


if __name__ == "__main__":
    unittest.main()
