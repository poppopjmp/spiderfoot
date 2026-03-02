"""
Tests for Cycle 48 — SSRF-safe Webhook URL Validation

Validates that ValidationUtils.validate_url_no_ssrf() properly blocks:
- Private / loopback / link-local IP addresses
- Non-HTTP(S) schemes (file://, gopher://, etc.)
- Cloud metadata endpoints (169.254.169.254)
- URLs with embedded credentials
- IPv6 loopback and ULA addresses
"""

from __future__ import annotations

import pytest
from unittest.mock import patch
from spiderfoot.core.validation import ValidationUtils


# ---------------------------------------------------------------------------
# Valid URLs
# ---------------------------------------------------------------------------

class TestValidWebhookURLs:
    """URLs that should pass validation."""

    @pytest.mark.parametrize("url", [
        "https://hooks.slack.com/services/T00/B00/xxx",
        "https://discord.com/api/webhooks/123/abc",
        "https://example.com/webhook",
        "http://example.com/callback",
        "https://api.pagerduty.com/v2/enqueue",
    ])
    def test_valid_public_urls(self, url):
        result = ValidationUtils.validate_url_no_ssrf(url)
        assert result == url

    def test_strips_whitespace(self):
        result = ValidationUtils.validate_url_no_ssrf("  https://example.com/hook  ")
        assert result == "https://example.com/hook"


# ---------------------------------------------------------------------------
# Blocked schemes
# ---------------------------------------------------------------------------

class TestBlockedSchemes:
    """Non-HTTP(S) schemes must be rejected."""

    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",
        "gopher://evil.com/payload",
        "ftp://files.example.com/data",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "dict://attacker.com:80/",
    ])
    def test_rejects_dangerous_schemes(self, url):
        with pytest.raises(ValueError, match="not allowed"):
            ValidationUtils.validate_url_no_ssrf(url)


# ---------------------------------------------------------------------------
# Private / Loopback IPs
# ---------------------------------------------------------------------------

class TestBlocksPrivateIPs:
    """Private, loopback, and link-local IPs must be blocked."""

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/admin",
        "http://127.0.0.1:8080/",
        "http://10.0.0.1/internal",
        "http://172.16.0.1/secret",
        "http://192.168.1.1/router",
        "http://169.254.1.1/metadata",
        "http://0.0.0.0/",
    ])
    def test_rejects_private_ipv4(self, url):
        with pytest.raises(ValueError, match="private|loopback"):
            ValidationUtils.validate_url_no_ssrf(url)

    @pytest.mark.parametrize("url", [
        "http://[::1]/admin",
        "http://[fc00::1]/internal",
        "http://[fe80::1]/link-local",
    ])
    def test_rejects_private_ipv6(self, url):
        with pytest.raises(ValueError, match="private|loopback"):
            ValidationUtils.validate_url_no_ssrf(url)

    def test_allow_private_flag_bypasses(self):
        """The allow_private flag should skip private-IP checks (for testing)."""
        result = ValidationUtils.validate_url_no_ssrf(
            "http://127.0.0.1/test", allow_private=True
        )
        assert result == "http://127.0.0.1/test"


# ---------------------------------------------------------------------------
# Cloud metadata endpoints
# ---------------------------------------------------------------------------

class TestBlocksMetadataEndpoints:
    """Cloud provider metadata endpoints must be explicitly blocked."""

    def test_aws_metadata(self):
        with pytest.raises(ValueError, match="metadata"):
            ValidationUtils.validate_url_no_ssrf("http://169.254.169.254/latest/meta-data/")

    def test_gce_metadata(self):
        with pytest.raises(ValueError, match="metadata"):
            ValidationUtils.validate_url_no_ssrf("http://metadata.google.internal/v1/")


# ---------------------------------------------------------------------------
# Embedded credentials
# ---------------------------------------------------------------------------

class TestBlocksEmbeddedCredentials:
    """URLs with user:pass@ must be rejected."""

    def test_rejects_user_password(self):
        with pytest.raises(ValueError, match="credentials"):
            ValidationUtils.validate_url_no_ssrf("https://admin:secret@example.com/hook")

    def test_rejects_user_only(self):
        with pytest.raises(ValueError, match="credentials"):
            ValidationUtils.validate_url_no_ssrf("https://admin@example.com/hook")


# ---------------------------------------------------------------------------
# Missing / empty
# ---------------------------------------------------------------------------

class TestEmptyURL:
    """Empty and None URLs must be rejected."""

    def test_empty_string(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            ValidationUtils.validate_url_no_ssrf("")

    def test_none(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            ValidationUtils.validate_url_no_ssrf(None)

    def test_no_hostname(self):
        with pytest.raises(ValueError, match="hostname"):
            ValidationUtils.validate_url_no_ssrf("https://")


# ---------------------------------------------------------------------------
# Custom allowed schemes
# ---------------------------------------------------------------------------

class TestCustomSchemes:
    """Override allowed schemes."""

    def test_allow_only_https(self):
        # http should be rejected when only https is allowed
        with pytest.raises(ValueError, match="not allowed"):
            ValidationUtils.validate_url_no_ssrf(
                "http://example.com",
                allowed_schemes={"https"},
            )

    def test_allow_custom_scheme(self):
        result = ValidationUtils.validate_url_no_ssrf(
            "slack://example.com/hook",
            allowed_schemes={"slack", "https"},
        )
        assert result == "slack://example.com/hook"


# ---------------------------------------------------------------------------
# DNS resolution to private IP
# ---------------------------------------------------------------------------

class TestDNSResolution:
    """Hostname resolving to private IP should be blocked."""

    def test_hostname_resolving_to_loopback(self):
        """Mock DNS to return 127.0.0.1 for an innocent-looking domain."""
        fake_results = [(2, 1, 6, '', ('127.0.0.1', 0))]  # AF_INET, SOCK_STREAM
        with patch("socket.getaddrinfo", return_value=fake_results):
            with pytest.raises(ValueError, match="private IP"):
                ValidationUtils.validate_url_no_ssrf("https://evil-rebind.attacker.com/hook")

    def test_hostname_resolving_to_10_net(self):
        """Mock DNS to return 10.x address."""
        fake_results = [(2, 1, 6, '', ('10.0.0.5', 0))]
        with patch("socket.getaddrinfo", return_value=fake_results):
            with pytest.raises(ValueError, match="private IP"):
                ValidationUtils.validate_url_no_ssrf("https://corporate.example.com/internal")

    def test_unresolvable_hostname_passes(self):
        """If DNS fails, let it through — it will fail at connect time."""
        import socket
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("no such host")):
            result = ValidationUtils.validate_url_no_ssrf("https://nonexistent.example.com/hook")
            assert result == "https://nonexistent.example.com/hook"
