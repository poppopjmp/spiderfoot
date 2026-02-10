"""Centralized constants for SpiderFoot.

This module defines commonly used default values that were previously
scattered as magic numbers across the codebase. Import from here instead
of hardcoding values.
"""

# ---------------------------------------------------------------------------
# Time durations (in seconds)
# ---------------------------------------------------------------------------
DEFAULT_TTL_ONE_HOUR: int = 3600
"""Default TTL for tokens, sessions, caches, and rate-limit windows."""

MODULE_TIMEOUT_SECONDS: float = 300.0
"""Default module execution timeout (5 minutes)."""

SHORT_CACHE_TTL_SECONDS: float = 300.0
"""Default short-lived cache TTL (5 minutes)."""

SESSION_IDLE_TIMEOUT: int = 1800
"""Session idle timeout before expiry (30 minutes)."""

# ---------------------------------------------------------------------------
# Query / batch limits
# ---------------------------------------------------------------------------
DEFAULT_RESULT_LIMIT: int = 100
"""Default maximum number of results returned by queries."""

DEFAULT_BATCH_SIZE: int = 100
"""Default batch size for bulk operations."""

# ---------------------------------------------------------------------------
# Retry / backoff
# ---------------------------------------------------------------------------
DEFAULT_MAX_RETRIES: int = 3
"""Default maximum number of retry attempts."""

DB_RETRY_BACKOFF_BASE: float = 0.2
"""Base multiplier for database retry backoff: sleep(BASE * (attempt + 1))."""

# ---------------------------------------------------------------------------
# Network ports
# ---------------------------------------------------------------------------
DEFAULT_API_PORT: int = 8001
"""Default port for the FastAPI REST API service."""

DEFAULT_WEB_PORT: int = 5001
"""Default port for the CherryPy WebUI service."""

DEFAULT_VECTOR_PORT: int = 8686
"""Default port for the Vector telemetry endpoint."""

# ---------------------------------------------------------------------------
# Size limits
# ---------------------------------------------------------------------------
MAX_BODY_BYTES: int = 10 * 1024 * 1024
"""Maximum HTTP request body size (10 MB)."""

DEFAULT_MAX_TOKENS: int = 4096
"""Default LLM max token / event data truncation threshold."""

# ---------------------------------------------------------------------------
# Default service URLs
# ---------------------------------------------------------------------------
DEFAULT_OPENAI_BASE_URL: str = "https://api.openai.com/v1"
"""Default base URL for OpenAI-compatible API endpoints."""

DEFAULT_OLLAMA_BASE_URL: str = "http://localhost:11434"
"""Default base URL for Ollama local inference server."""

DEFAULT_VLLM_BASE_URL: str = "http://localhost:8000/v1"
"""Default base URL for vLLM / local model server."""

DEFAULT_DOH_URL: str = "https://cloudflare-dns.com/dns-query"
"""Default DNS-over-HTTPS resolver URL."""

DEFAULT_DATABASE_NAME: str = "spiderfoot.db"
"""Default SQLite database filename."""
