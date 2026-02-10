"""
Inter-service authentication for microservice deployments.

Provides a lightweight shared-secret token scheme that scanner and
WebUI services use to authenticate with the API service.  Tokens are
rotated on a configurable interval and validated with constant-time
comparison.

In microservice mode, every request from scanner/webui to the API
must include an ``Authorization: Bearer <service-token>`` header.
The API validates tokens against the shared secret / HMAC.

Environment variables:
    SF_SERVICE_TOKEN       — Pre-shared static token (simplest setup)
    SF_SERVICE_SECRET      — HMAC secret for time-based token generation
    SF_SERVICE_TOKEN_TTL   — Token lifetime in seconds (default: 3600)
    SF_SERVICE_AUTH_ENABLED — Enable/disable inter-service auth (default: true in microservice mode)

Usage — Token issuer (scanner/webui side):
    from spiderfoot.service_auth import ServiceTokenIssuer
    issuer = ServiceTokenIssuer()
    headers = issuer.auth_headers()  # {"Authorization": "Bearer ..."}

Usage — Token validator (API side):
    from spiderfoot.service_auth import ServiceTokenValidator
    validator = ServiceTokenValidator()
    if validator.validate(token):
        ...
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass
from spiderfoot.constants import DEFAULT_TTL_ONE_HOUR

log = logging.getLogger(__name__)


@dataclass
class TokenValidationResult:
    """Result of a service token validation."""
    valid: bool
    service_name: str = ""
    issued_at: float = 0.0
    expires_at: float = 0.0
    reason: str = ""


class ServiceTokenIssuer:
    """Issues authentication tokens for inter-service requests.

    Supports two modes:
    1. **Static token** — uses ``SF_SERVICE_TOKEN`` directly
    2. **HMAC token** — generates time-based tokens from ``SF_SERVICE_SECRET``

    The HMAC mode creates tokens of the form:
        ``<service_name>:<timestamp>:<hmac_signature>``
    """

    def __init__(
        self,
        service_name: str | None = None,
        static_token: str | None = None,
        secret: str | None = None,
        ttl: int = DEFAULT_TTL_ONE_HOUR,
    ) -> None:
        self.service_name = service_name or os.environ.get("SF_SERVICE_NAME", "unknown")
        self._static_token = static_token or os.environ.get("SF_SERVICE_TOKEN", "")
        self._secret = secret or os.environ.get("SF_SERVICE_SECRET", "")
        self._ttl = int(os.environ.get("SF_SERVICE_TOKEN_TTL", str(ttl)))

        # Cache for HMAC tokens
        self._cached_token: str | None = None
        self._cached_expires: float = 0.0

    def get_token(self) -> str:
        """Generate or return a cached service token."""
        # Static token mode
        if self._static_token:
            return self._static_token

        # HMAC mode — generate time-based token
        if self._secret:
            now = time.time()
            if self._cached_token and now < self._cached_expires:
                return self._cached_token

            token = self._generate_hmac_token(now)
            self._cached_token = token
            # Cache for 80% of TTL to avoid edge-case expiry
            self._cached_expires = now + (self._ttl * 0.8)
            return token

        # No auth configured — return empty
        return ""

    def auth_headers(self) -> dict[str, str]:
        """Return HTTP headers for inter-service authentication."""
        token = self.get_token()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def _generate_hmac_token(self, timestamp: float) -> str:
        """Create an HMAC-signed token."""
        ts_str = str(int(timestamp))
        message = f"{self.service_name}:{ts_str}"
        signature = hmac.new(
            self._secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{self.service_name}:{ts_str}:{signature}"


class ServiceTokenValidator:
    """Validates inter-service authentication tokens on the API side.

    Args:
        static_token: Expected static token (for static mode).
        secret: HMAC secret (for HMAC mode).
        ttl: Maximum token age in seconds.
        enabled: Whether validation is enforced.
    """

    def __init__(
        self,
        static_token: str | None = None,
        secret: str | None = None,
        ttl: int = DEFAULT_TTL_ONE_HOUR,
        enabled: bool | None = None,
    ) -> None:
        self._static_token = static_token or os.environ.get("SF_SERVICE_TOKEN", "")
        self._secret = secret or os.environ.get("SF_SERVICE_SECRET", "")
        self._ttl = int(os.environ.get("SF_SERVICE_TOKEN_TTL", str(ttl)))

        # Auto-detect: enabled in microservice mode unless explicitly set
        if enabled is not None:
            self._enabled = enabled
        else:
            env_val = os.environ.get("SF_SERVICE_AUTH_ENABLED", "").lower()
            if env_val in ("0", "false", "no", "off"):
                self._enabled = False
            elif env_val in ("1", "true", "yes", "on"):
                self._enabled = True
            else:
                # Auto: enable if any auth config is present
                self._enabled = bool(self._static_token or self._secret)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def validate(self, token: str) -> TokenValidationResult:
        """Validate a service token.

        Returns a ``TokenValidationResult`` with validation details.
        """
        if not self._enabled:
            return TokenValidationResult(valid=True, reason="auth_disabled")

        if not token:
            return TokenValidationResult(valid=False, reason="no_token")

        # Try static token first
        if self._static_token:
            if hmac.compare_digest(token, self._static_token):
                return TokenValidationResult(valid=True, reason="static_token")

        # Try HMAC token
        if self._secret:
            return self._validate_hmac_token(token)

        # No auth configured but token provided
        return TokenValidationResult(valid=False, reason="no_auth_configured")

    def _validate_hmac_token(self, token: str) -> TokenValidationResult:
        """Validate an HMAC-signed token."""
        parts = token.split(":")
        if len(parts) != 3:
            return TokenValidationResult(valid=False, reason="invalid_token_format")

        service_name, ts_str, signature = parts

        # Verify timestamp
        try:
            issued_at = float(ts_str)
        except ValueError:
            return TokenValidationResult(valid=False, reason="invalid_timestamp")

        now = time.time()
        age = now - issued_at
        if age > self._ttl:
            return TokenValidationResult(
                valid=False,
                service_name=service_name,
                issued_at=issued_at,
                expires_at=issued_at + self._ttl,
                reason="token_expired",
            )
        if age < -60:  # Allow 60s clock skew
            return TokenValidationResult(
                valid=False,
                service_name=service_name,
                issued_at=issued_at,
                reason="token_from_future",
            )

        # Verify HMAC
        message = f"{service_name}:{ts_str}"
        expected = hmac.new(
            self._secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if hmac.compare_digest(signature, expected):
            return TokenValidationResult(
                valid=True,
                service_name=service_name,
                issued_at=issued_at,
                expires_at=issued_at + self._ttl,
                reason="hmac_valid",
            )

        return TokenValidationResult(
            valid=False,
            service_name=service_name,
            reason="hmac_invalid",
        )

    def extract_token(self, authorization: str) -> str:
        """Extract token from an Authorization header value.

        Supports:
            ``Bearer <token>``
            ``<token>``   (raw)
        """
        if not authorization:
            return ""
        if authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return authorization.strip()


def generate_service_secret() -> str:
    """Generate a cryptographically random service secret."""
    return secrets.token_hex(32)
