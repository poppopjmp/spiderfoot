"""Input validation and security headers – lightweight stubs.

The original monolithic module was removed during the clean-up phase.
These thin implementations satisfy the interface expected by
``security_middleware.py`` without pulling in external dependencies.
"""

from __future__ import annotations

import html
import os
import re
from typing import Any


class SecurityHeaders:
    """Default HTTP security headers injected into every response."""

    DEFAULT_HEADERS: dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        ),
    }

    @classmethod
    def get_headers(cls) -> dict[str, str]:
        """Return security headers, adding HSTS when SF_HSTS_ENABLED is set."""
        headers = dict(cls.DEFAULT_HEADERS)
        if os.environ.get("SF_HSTS_ENABLED", "").lower() in ("1", "true", "yes"):
            headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
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
