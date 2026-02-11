"""Centralized constants for SpiderFoot.

This module defines commonly used default values that were previously
scattered as magic numbers across the codebase. Import from here instead
of hardcoding values.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "DEFAULT_TTL_ONE_HOUR",
    "MODULE_TIMEOUT_SECONDS",
    "SHORT_CACHE_TTL_SECONDS",
    "SESSION_IDLE_TIMEOUT",
    "DEFAULT_RESULT_LIMIT",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_MAX_RETRIES",
    "DB_RETRY_BACKOFF_BASE",
    "DEFAULT_API_PORT",
    "DEFAULT_WEB_PORT",
    "DEFAULT_VECTOR_PORT",
    "MAX_BODY_BYTES",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_OPENAI_BASE_URL",
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_VLLM_BASE_URL",
    "DEFAULT_DOH_URL",
    "DEFAULT_DATABASE_NAME",
]

# ---------------------------------------------------------------------------
# Time durations (in seconds)
# ---------------------------------------------------------------------------
DEFAULT_TTL_ONE_HOUR: Final[int] = 3600
"""Default TTL for tokens, sessions, caches, and rate-limit windows."""

MODULE_TIMEOUT_SECONDS: Final[float] = 300.0
"""Default module execution timeout (5 minutes)."""

SHORT_CACHE_TTL_SECONDS: Final[float] = 300.0
"""Default short-lived cache TTL (5 minutes)."""

SESSION_IDLE_TIMEOUT: Final[int] = 1800
"""Session idle timeout before expiry (30 minutes)."""

# ---------------------------------------------------------------------------
# Query / batch limits
# ---------------------------------------------------------------------------
DEFAULT_RESULT_LIMIT: Final[int] = 100
"""Default maximum number of results returned by queries."""

DEFAULT_BATCH_SIZE: Final[int] = 100
"""Default batch size for bulk operations."""

# ---------------------------------------------------------------------------
# Retry / backoff
# ---------------------------------------------------------------------------
DEFAULT_MAX_RETRIES: Final[int] = 3
"""Default maximum number of retry attempts."""

DB_RETRY_BACKOFF_BASE: Final[float] = 0.2
"""Base multiplier for database retry backoff: sleep(BASE * (attempt + 1))."""

# ---------------------------------------------------------------------------
# Network ports
# ---------------------------------------------------------------------------
DEFAULT_API_PORT: Final[int] = 8001
"""Default port for the FastAPI REST API service."""

DEFAULT_WEB_PORT: Final[int] = 5001
"""Default port for the CherryPy WebUI service."""

DEFAULT_VECTOR_PORT: Final[int] = 8686
"""Default port for the Vector telemetry endpoint."""

# ---------------------------------------------------------------------------
# Size limits
# ---------------------------------------------------------------------------
MAX_BODY_BYTES: Final[int] = 10 * 1024 * 1024
"""Maximum HTTP request body size (10 MB)."""

DEFAULT_MAX_TOKENS: Final[int] = 4096
"""Default LLM max token / event data truncation threshold."""

# ---------------------------------------------------------------------------
# Default service URLs
# ---------------------------------------------------------------------------
DEFAULT_OPENAI_BASE_URL: Final[str] = "https://api.openai.com/v1"
"""Default base URL for OpenAI-compatible API endpoints."""

DEFAULT_OLLAMA_BASE_URL: Final[str] = "http://localhost:11434"
"""Default base URL for Ollama local inference server."""

DEFAULT_VLLM_BASE_URL: Final[str] = "http://localhost:8000/v1"
"""Default base URL for vLLM / local model server."""

DEFAULT_DOH_URL: Final[str] = "https://cloudflare-dns.com/dns-query"
"""Default DNS-over-HTTPS resolver URL."""

DEFAULT_DATABASE_NAME: Final[str] = "spiderfoot.db"
"""Default SQLite database filename."""
