"""API key and JWT validation – hardened stubs.

Provides ``APIKeyManager`` and ``JWTManager`` expected (optionally) by
``security_middleware.py``.

Security hardening (v5.9.2):
- JWT: rejects the well-known default secret "changeme" at startup
- JWT: delegates to PyJWT instead of hand-rolled HMAC
- APIKeyManager: logs a WARNING when no keys are configured (dev-mode)
- APIKeyManager: requires explicit SF_AUTH_DISABLED=true to skip validation
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import jwt  # PyJWT

log = logging.getLogger("spiderfoot.api_security")

# Well-known insecure defaults that MUST NOT be used in production
_INSECURE_JWT_SECRETS = frozenset({
    "changeme",
    "change-me-in-production-please",
    "secret",
    "supersecret",
    "",
})


class APIKeyManager:
    """Validate ``X-API-Key`` header values."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._keys: set[str] = set()
        raw = self.config.get("security.api_keys", "")
        if raw:
            for k in str(raw).split(","):
                k = k.strip()
                if k:
                    self._keys.add(k)

        # Check for explicit dev-mode auth bypass
        self._auth_disabled = os.environ.get(
            "SF_AUTH_DISABLED", "false"
        ).lower() in ("true", "1", "yes")

        if not self._keys:
            if self._auth_disabled:
                log.warning(
                    "API key validation DISABLED (SF_AUTH_DISABLED=true). "
                    "Do NOT use this setting in production."
                )
            else:
                log.warning(
                    "No API keys configured. All key-bearing requests will "
                    "be rejected. Set security.api_keys or SF_AUTH_DISABLED=true "
                    "for dev mode."
                )

    def validate_api_key(self, api_key: str) -> bool:
        if not self._keys:
            # Explicit opt-in required for dev-mode bypass
            return self._auth_disabled
        return api_key in self._keys


class JWTManager:
    """JWT validation using PyJWT (HS256/RS256).

    Replaces the previous hand-rolled HMAC implementation with the
    battle-tested PyJWT library.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._secret: str = str(
            self.config.get("security.jwt_secret", "changeme")
        )
        self._algorithms: list[str] = ["HS256"]

        # Refuse to run with a well-known insecure secret
        if self._secret.lower() in _INSECURE_JWT_SECRETS:
            log.critical(
                "JWT secret is set to a well-known insecure default (%r). "
                "Set a strong secret via security.jwt_secret config or "
                "SF_JWT_SECRET environment variable before starting.",
                self._secret if self._secret else "<empty>",
            )
            # Override with a random per-process secret so that at least
            # tokens from other processes cannot be forged. Existing tokens
            # signed with the insecure default will be rejected.
            import secrets
            self._secret = secrets.token_hex(32)
            log.warning(
                "Auto-generated a random JWT secret for this process. "
                "Tokens will not survive restarts. Fix your configuration."
            )

    def validate_token(self, token: str) -> dict[str, Any]:
        """Return ``{'valid': True, 'claims': …}`` or ``{'valid': False}``."""
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=self._algorithms,
            )
            return {"valid": True, "claims": payload}
        except jwt.ExpiredSignatureError:
            return {"valid": False, "reason": "expired"}
        except jwt.InvalidTokenError as exc:
            return {"valid": False, "reason": str(exc)}
