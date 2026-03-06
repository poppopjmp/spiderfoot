# -------------------------------------------------------------------------------
# Name:         SpiderFoot Startup Secrets Checker
# Purpose:      Detect insecure default credentials at startup.
#
# Author:       SpiderFoot Security Hardening
#
# Created:      2025-07-17
# Licence:      MIT
# -------------------------------------------------------------------------------
"""
Detect insecure default credentials at application startup.

Runs as an early startup check and **blocks** the application from
starting in ``production`` mode if any well-known default passwords
or secrets are detected in environment variables.

In ``development`` mode the defaults are allowed but noisy warnings
are emitted to the logger.

Usage::

    from spiderfoot.security.startup_check import check_startup_secrets
    check_startup_secrets()  # raises SystemExit in prod with defaults
"""
from __future__ import annotations

import logging
import os
import re
import sys

log = logging.getLogger("spiderfoot.security")


# ---------------------------------------------------------------------------
# Known insecure defaults
# ---------------------------------------------------------------------------

# Map of env var → set of known-insecure default values.
# Values are compared case-insensitively.
INSECURE_DEFAULTS: dict[str, set[str]] = {
    "POSTGRES_PASSWORD": {"changeme", "password", "postgres", "secret", ""},
    "SF_JWT_SECRET": {
        "change-me-in-production-please",
        "changeme",
        "secret",
        "jwt-secret",
        "",
    },
    "SF_ADMIN_PASSWORD": {"admin", "password", "changeme", "spiderfoot", ""},
    "MINIO_ROOT_PASSWORD": {
        "changeme123",
        "minioadmin",
        "password",
        "changeme",
        "",
    },
    "GF_SECURITY_ADMIN_PASSWORD": {"admin", "spiderfoot", "changeme", "grafana", ""},
    "KC_ADMIN_PASSWORD": {"admin", "changeme", "password", "keycloak", ""},
    "LITELLM_MASTER_KEY": {"changeme", "sk-1234", ""},
}

# Env vars that should contain strong secrets (length check).
MIN_SECRET_LENGTH: dict[str, int] = {
    "SF_JWT_SECRET": 32,
    "POSTGRES_PASSWORD": 12,
    "MINIO_ROOT_PASSWORD": 12,
}

# Patterns detected as weak (dictionary words, sequential chars, etc.)
_WEAK_PATTERN = re.compile(
    r"^(password|secret|changeme|admin|test|default|12345|qwerty|letmein)", re.I
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_startup_secrets(
    *,
    mode: str | None = None,
    fail_in_production: bool = True,
) -> list[str]:
    """Check environment variables for insecure default secrets.

    Args:
        mode: Override for run mode. Default reads ``SF_ENV`` or
              ``ENVIRONMENT`` from the environment (fallback: ``development``).
        fail_in_production: If True, exit the process when insecure
              defaults are found in production mode.

    Returns:
        List of warning messages (one per issue found).
    """
    if mode is None:
        mode = os.environ.get("SF_ENV", os.environ.get("ENVIRONMENT", "development"))
    mode = mode.lower()
    is_prod = mode in ("production", "prod", "staging")

    warnings: list[str] = []

    # ── Check known insecure defaults ────────────────────────────────
    for env_var, bad_values in INSECURE_DEFAULTS.items():
        value = os.environ.get(env_var)
        if value is None:
            continue  # Not set — typically okay (fallback generates random)

        if value.lower() in bad_values:
            msg = (
                f"INSECURE DEFAULT: {env_var} is set to a well-known default value. "
                f"Change it before deploying to production."
            )
            warnings.append(msg)

    # ── Check minimum secret length ──────────────────────────────────
    for env_var, min_len in MIN_SECRET_LENGTH.items():
        value = os.environ.get(env_var)
        if value is not None and 0 < len(value) < min_len:
            msg = (
                f"WEAK SECRET: {env_var} is only {len(value)} characters. "
                f"Minimum recommended length is {min_len}."
            )
            warnings.append(msg)

    # ── Check for weak patterns ──────────────────────────────────────
    for env_var in MIN_SECRET_LENGTH:
        value = os.environ.get(env_var)
        if value and _WEAK_PATTERN.match(value):
            msg = (
                f"WEAK SECRET: {env_var} appears to use a dictionary word. "
                f"Use a cryptographically random value."
            )
            # Don't double-report if already caught as insecure default
            if msg not in warnings:
                warnings.append(msg)

    # ── Emit warnings / fail ─────────────────────────────────────────
    for w in warnings:
        log.warning(w)

    if warnings and is_prod and fail_in_production:
        # Allow explicit opt-in to suppress the exit (CI/test only)
        if os.environ.get("SF_ALLOW_INSECURE_DEFAULTS", "").lower() in ("1", "true", "yes"):
            log.warning(
                "SF_ALLOW_INSECURE_DEFAULTS is set — allowing %d insecure "
                "default(s) in %s mode. THIS IS NOT SAFE FOR PRODUCTION.",
                len(warnings),
                mode,
            )
        else:
            log.critical(
                "Refusing to start in %s mode with %d insecure default(s). "
                "Set secure values for the flagged environment variables.",
                mode,
                len(warnings),
            )
            sys.exit(78)  # EX_CONFIG from sysexits.h

    return warnings
