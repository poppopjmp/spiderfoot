# -------------------------------------------------------------------------------
# Name:         SpiderFoot Response Filtering
# Purpose:      Strip internal / sensitive fields from API responses.
#
# Author:       SpiderFoot Security Hardening
#
# Created:      2025-07-17
# Licence:      MIT
# -------------------------------------------------------------------------------
"""
Response-filtering utilities for API endpoints.

Ensures internal implementation details, hashed passwords, database IDs,
and debugging artifacts are never leaked to API consumers.

Usage::

    from spiderfoot.api.response_filter import strip_internal_fields

    @router.get("/users/{user_id}")
    def get_user(user_id: str):
        user = db.get_user(user_id)
        return strip_internal_fields(user)
"""
from __future__ import annotations

import copy
import re
from typing import Any


# ---------------------------------------------------------------------------
# Fields that must NEVER appear in API responses
# ---------------------------------------------------------------------------

# Exact field names (case-insensitive comparison)
BLOCKED_FIELDS: frozenset[str] = frozenset({
    # Authentication secrets
    "password",
    "password_hash",
    "hashed_password",
    "password_salt",
    "salt",
    "secret",
    "secret_key",
    "private_key",
    "api_secret",
    # Tokens & sessions
    "session_token",
    "refresh_token",
    "access_token",
    "jwt_token",
    "csrf_token",
    # Internal identifiers
    "_internal_id",
    "_row_id",
    "internal_id",
    # Database internals
    "_sa_instance_state",   # SQLAlchemy
    "xmin", "xmax",         # PostgreSQL system columns
    "ctid",
    "tableoid",
    # Debug / tracing
    "stack_trace",
    "stacktrace",
    "traceback",
    "debug_info",
    "_debug",
    # Infrastructure
    "dsn",
    "connection_string",
    "database_url",
    "redis_url",
})

# Patterns for field names that should be redacted rather than removed.
# The value is replaced with "[REDACTED]".
REDACT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r".*_key$", re.IGNORECASE),          # api_key, encryption_key
    re.compile(r".*_secret$", re.IGNORECASE),        # client_secret
    re.compile(r".*_token$", re.IGNORECASE),         # auth_token
    re.compile(r".*_password$", re.IGNORECASE),      # db_password
    re.compile(r".*_credential.*", re.IGNORECASE),   # service_credentials
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def strip_internal_fields(
    data: Any,
    *,
    blocked: frozenset[str] | None = None,
    redact_patterns: list[re.Pattern[str]] | None = None,
    max_depth: int = 20,
) -> Any:
    """Remove or redact sensitive fields from an API response payload.

    Works recursively on dicts and lists.  Returns a *new* object;
    the original is not mutated.

    Args:
        data: The response payload (dict, list, or scalar).
        blocked: Override set of field names to remove entirely.
        redact_patterns: Override list of patterns to redact.
        max_depth: Maximum recursion depth (DoS protection).

    Returns:
        Cleaned copy of the data.
    """
    _blocked = blocked or BLOCKED_FIELDS
    _patterns = redact_patterns or REDACT_PATTERNS
    return _filter(data, _blocked, _patterns, 0, max_depth)


def _filter(
    obj: Any,
    blocked: frozenset[str],
    patterns: list[re.Pattern[str]],
    depth: int,
    max_depth: int,
) -> Any:
    if depth > max_depth:
        return obj

    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for key, value in obj.items():
            lower_key = key.lower() if isinstance(key, str) else str(key).lower()

            # Remove blocked fields entirely
            if lower_key in blocked:
                continue

            # Redact matching patterns
            if any(p.match(lower_key) for p in patterns):
                result[key] = "[REDACTED]"
                continue

            # Recurse
            result[key] = _filter(value, blocked, patterns, depth + 1, max_depth)
        return result

    if isinstance(obj, (list, tuple)):
        return [_filter(item, blocked, patterns, depth + 1, max_depth) for item in obj]

    return obj


def filter_user_response(user: dict[str, Any]) -> dict[str, Any]:
    """Convenience filter specifically for user objects.

    Ensures password hashes, tokens, and internal state are stripped.
    """
    return strip_internal_fields(user)


def filter_scan_response(scan: dict[str, Any]) -> dict[str, Any]:
    """Convenience filter for scan result objects."""
    return strip_internal_fields(scan)
