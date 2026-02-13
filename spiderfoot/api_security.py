"""API key and JWT validation – lightweight stubs.

Provides ``APIKeyManager`` and ``JWTManager`` expected (optionally) by
``security_middleware.py``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import base64
import time
from typing import Any


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

    def validate_api_key(self, api_key: str) -> bool:
        if not self._keys:
            # no keys configured → allow all (dev mode)
            return True
        return api_key in self._keys


class JWTManager:
    """Minimal HMAC-SHA256 JWT validation (HS256)."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._secret: str = str(
            self.config.get("security.jwt_secret", "changeme")
        )

    def validate_token(self, token: str) -> dict[str, Any]:
        """Return ``{'valid': True, 'claims': …}`` or ``{'valid': False}``."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return {"valid": False}

            header_b64, payload_b64, sig_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}".encode()
            expected = hmac.new(
                self._secret.encode(), signing_input, hashlib.sha256,
            ).digest()
            provided = base64.urlsafe_b64decode(sig_b64 + "==")
            if not hmac.compare_digest(expected, provided):
                return {"valid": False}

            payload = json.loads(
                base64.urlsafe_b64decode(payload_b64 + "==")
            )
            if "exp" in payload and payload["exp"] < time.time():
                return {"valid": False, "reason": "expired"}

            return {"valid": True, "claims": payload}
        except Exception:
            return {"valid": False}
