"""Input validation and security headers – lightweight stubs.

The original monolithic module was removed during the clean-up phase.
These thin implementations satisfy the interface expected by
``security_middleware.py`` without pulling in external dependencies.
"""

from __future__ import annotations

import html
import ipaddress
import os
import re
import secrets
from typing import Any
from urllib.parse import urlparse


class SecurityHeaders:
    """Default HTTP security headers injected into every response."""

    DEFAULT_HEADERS: dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
    }

    # Base CSP template — {nonce} placeholder is replaced per-request
    CSP_TEMPLATE: str = (
        "default-src 'self'; "
        "script-src 'self'{nonce_directive}; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    @classmethod
    def generate_nonce(cls) -> str:
        """Generate a cryptographically random CSP nonce (base64, 16 bytes)."""
        return secrets.token_urlsafe(16)

    @classmethod
    def get_headers(cls, *, nonce: str | None = None) -> dict[str, str]:
        """Return security headers with optional CSP nonce.

        Args:
            nonce: If provided, the CSP will include ``'nonce-{nonce}'``
                   in the script-src directive, allowing inline scripts
                   tagged with that nonce.

        Returns:
            Security headers dict ready to apply to a response.
        """
        headers = dict(cls.DEFAULT_HEADERS)

        if os.environ.get("SF_HSTS_ENABLED", "").lower() in ("1", "true", "yes"):
            headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )

        # Build CSP with optional nonce
        nonce_directive = f" 'nonce-{nonce}'" if nonce else ""
        headers["Content-Security-Policy"] = cls.CSP_TEMPLATE.format(
            nonce_directive=nonce_directive
        )

        return headers


# ---------------------------------------------------------------------------
# Patterns considered dangerous in user-supplied strings
# ---------------------------------------------------------------------------
_DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<\s*script", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),         # onclick=, onerror=, …
    re.compile(r"(\%27)|(\')|(\-\-)", re.IGNORECASE),  # SQL-injection hints
]

_MAX_INPUT_LENGTH = 10_000


class InputValidator:
    """Validate untrusted string / JSON inputs."""

    def validate_input(self, value: str) -> bool:
        """Return *True* when *value* looks safe."""
        if not isinstance(value, str):
            return True
        if len(value) > _MAX_INPUT_LENGTH:
            return False
        for pat in _DANGEROUS_PATTERNS:
            if pat.search(value):
                return False
        return True

    def validate_json_input(self, data: Any) -> bool:
        """Recursively validate every string leaf in a JSON structure."""
        if isinstance(data, str):
            return self.validate_input(data)
        if isinstance(data, dict):
            return all(
                self.validate_input(str(k)) and self.validate_json_input(v)
                for k, v in data.items()
            )
        if isinstance(data, (list, tuple)):
            return all(self.validate_json_input(item) for item in data)
        return True

    # -----------------------------------------------------------------------
    # SSRF protection — block scan targets pointing at internal resources
    # -----------------------------------------------------------------------

    # Cloud metadata endpoints attackers commonly target via SSRF
    _METADATA_HOSTS: frozenset[str] = frozenset({
        "169.254.169.254",  # AWS / GCP / Azure metadata
        "metadata.google.internal",
        "metadata.internal",
        "100.100.100.200",  # Alibaba Cloud
        "fd00:ec2::254",  # AWS IPv6 metadata
    })

    # Blocked hostnames that resolve to internal services
    _BLOCKED_HOSTS: frozenset[str] = frozenset({
        "localhost",
        "localhost.localdomain",
        "0.0.0.0",
        "[::]",
        "[::1]",
    })

    @classmethod
    def is_private_ip(cls, ip_str: str) -> bool:
        """Check if an IP address is private/reserved."""
        try:
            addr = ipaddress.ip_address(ip_str)
            return (
                addr.is_private
                or addr.is_loopback
                or addr.is_reserved
                or addr.is_link_local
                or addr.is_multicast
            )
        except ValueError:
            return False

    @classmethod
    def validate_url_target(cls, url: str) -> tuple[bool, str]:
        """Validate a URL is safe to scan (not pointing at internal resources).

        Returns:
            (is_safe, reason) — True if the URL is safe to use as a scan target.
        """
        if not url or not isinstance(url, str):
            return False, "empty or invalid URL"

        try:
            parsed = urlparse(url)
        except Exception:
            return False, "malformed URL"

        # Scheme check — only http(s) allowed
        if parsed.scheme not in ("http", "https", ""):
            return False, f"disallowed scheme: {parsed.scheme}"

        hostname = (parsed.hostname or "").lower().strip(".")
        if not hostname:
            return False, "no hostname"

        # Block cloud metadata endpoints
        if hostname in cls._METADATA_HOSTS:
            return False, f"blocked metadata endpoint: {hostname}"

        # Block known internal hostnames
        if hostname in cls._BLOCKED_HOSTS:
            return False, f"blocked internal host: {hostname}"

        # Check for private/reserved IPs
        if cls.is_private_ip(hostname):
            return False, f"private/reserved IP: {hostname}"

        # Block URLs with credentials
        if parsed.username or parsed.password:
            return False, "URL contains embedded credentials"

        # Block non-standard ports commonly used for internal services
        if parsed.port and parsed.port in (6379, 11211, 27017, 5432, 3306, 9200, 2379):
            return False, f"blocked internal service port: {parsed.port}"

        return True, ""


# ---------------------------------------------------------------------------
# Field-length constants (usable in Pydantic Field / FastAPI Query)
# ---------------------------------------------------------------------------

MAX_TARGET_LENGTH: int = int(os.environ.get("SF_MAX_TARGET_LENGTH", "2048"))
MAX_SCAN_NAME_LENGTH: int = int(os.environ.get("SF_MAX_SCAN_NAME_LENGTH", "255"))
MAX_NOTE_LENGTH: int = int(os.environ.get("SF_MAX_NOTE_LENGTH", "10000"))
MAX_BATCH_TARGETS: int = int(os.environ.get("SF_MAX_BATCH_TARGETS", "500"))
MAX_TAG_LENGTH: int = 64
MAX_TAGS_COUNT: int = 50
MAX_SEARCH_QUERY_LENGTH: int = 1024
MAX_DESCRIPTION_LENGTH: int = 5000
MAX_USERNAME_LENGTH: int = 128
MAX_PASSWORD_LENGTH: int = 256
MAX_EMAIL_LENGTH: int = 320  # RFC 5321


def validate_string_length(
    value: str,
    field_name: str,
    max_length: int,
    *,
    min_length: int = 0,
    strip: bool = True,
) -> str:
    """Validate and optionally strip a string field.

    Raises ValueError if validation fails.
    """
    if strip:
        value = value.strip()
    if len(value) < min_length:
        raise ValueError(f"{field_name} must be at least {min_length} characters")
    if len(value) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return value


def validate_batch_targets(targets: list[str]) -> list[str]:
    """Validate and deduplicate a batch of scan targets.

    Raises ValueError if too many targets are provided.
    """
    if len(targets) > MAX_BATCH_TARGETS:
        raise ValueError(f"Too many targets (max {MAX_BATCH_TARGETS})")

    seen: set[str] = set()
    validated: list[str] = []
    for t in targets:
        t = t.strip()
        if not t or t in seen:
            continue
        if len(t) > MAX_TARGET_LENGTH:
            raise ValueError(f"Target '{t[:50]}...' exceeds maximum length")
        if "\x00" in t:
            raise ValueError("Target contains null bytes")
        seen.add(t)
        validated.append(t)

    return validated


def validate_tags(tags: list[str]) -> list[str]:
    """Validate, clean, and deduplicate tag strings."""
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        tag = tag.strip()[:MAX_TAG_LENGTH]
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            result.append(tag)
        if len(result) >= MAX_TAGS_COUNT:
            break
    return result
