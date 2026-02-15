"""Input validation and security headers – lightweight stubs.

The original monolithic module was removed during the clean-up phase.
These thin implementations satisfy the interface expected by
``security_middleware.py`` without pulling in external dependencies.
"""

from __future__ import annotations

import html
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
    }


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
