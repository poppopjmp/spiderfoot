"""
Unified logging configuration for SpiderFoot.

Consolidates the three coexisting logging systems (SQLite handler,
structured JSON formatter, and Vector.dev sink) into a single
canonical configuration entry point.

The canonical logging pipeline is:

    Application code
        │
        ▼
    logging.getLogger("spiderfoot.*")
        │
        ├──► StructuredLogHandler (JSON to stdout)
        │        └──► Vector.dev / Loki / Elasticsearch
        │
        ├──► FileHandler (debug.log, errors.log)
        │
        └──► [DEPRECATED] SpiderFootSqliteLogHandler
                 (disabled by default, opt-in only)

Usage::

    from spiderfoot.logging_config import configure_logging

    configure_logging(config)  # Call once at startup
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import warnings
from typing import Any, Dict, Optional

from spiderfoot.structured_logging import StructuredFormatter, StructuredLogHandler


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LOG_LEVEL = logging.INFO
LOG_FORMAT_TEXT = "%(asctime)s [%(levelname)s] %(name)s : %(message)s"
LOG_FORMAT_DEBUG = "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)s : %(message)s"

_CONFIGURED = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def configure_logging(
    config: Optional[Dict[str, Any]] = None,
    *,
    force_json: Optional[bool] = None,
    force_text: bool = False,
    log_dir: Optional[str] = None,
    enable_sqlite: bool = False,
    enable_vector: bool = False,
) -> logging.Logger:
    """Configure the canonical SpiderFoot logging pipeline.

    This should be called **once** at application startup, before any
    modules run.  Subsequent calls are no-ops unless the root logger
    has been reset.

    The default pipeline writes **structured JSON to stdout** (suitable
    for Vector.dev ingestion) plus rotating text files for debug / error
    logs.  Set ``force_text=True`` for human-readable console output
    during development.

    Args:
        config: SpiderFoot configuration dict. Relevant keys:
            ``_debug`` (bool), ``_production`` (bool),
            ``__logging`` (bool), ``__version__`` (str),
            ``_vector_enabled`` (bool), ``_log_dir`` (str).
        force_json: Explicitly enable JSON output (default: auto-detect
            based on ``_production`` flag or ``SF_LOG_FORMAT=json`` env).
        force_text: Force plain-text console output (overrides JSON).
        log_dir: Directory for file-based logs.  Falls back to
            ``config['_log_dir']`` or ``logs/``.
        enable_sqlite: **DEPRECATED** — opt-in to the legacy SQLite
            log handler.  Will be removed in a future version.
        enable_vector: Forward logs to Vector.dev via the VectorLogHandler.

    Returns:
        The root ``spiderfoot`` logger.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return logging.getLogger("spiderfoot")

    config = config or {}

    # ── Determine log level ──────────────────────────────────────────
    quiet = not config.get("__logging", True)
    debug = config.get("_debug", False)

    if quiet:
        level = logging.WARNING
    elif debug:
        level = logging.DEBUG
    else:
        level = DEFAULT_LOG_LEVEL

    # ── Determine output format ──────────────────────────────────────
    production = config.get("_production", False)
    env_format = os.environ.get("SF_LOG_FORMAT", "").lower()

    if force_text:
        use_json = False
    elif force_json is not None:
        use_json = force_json
    elif env_format == "json":
        use_json = True
    elif env_format == "text":
        use_json = False
    else:
        # Auto: JSON in production / Docker, text in development
        use_json = production or _running_in_container()

    # ── Root logger ──────────────────────────────────────────────────
    root = logging.getLogger("spiderfoot")
    root.setLevel(logging.DEBUG)  # handlers filter further
    root.handlers.clear()

    # ── Console handler ──────────────────────────────────────────────
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)

    if use_json:
        environment = "production" if production else "development"
        console.setFormatter(StructuredFormatter(
            service_name=config.get("_service_name", "spiderfoot"),
            environment=environment,
            include_caller=debug,
            extra_fields={"version": config.get("__version__", "unknown")},
        ))
    else:
        console.setFormatter(logging.Formatter(LOG_FORMAT_TEXT))

    root.addHandler(console)

    # ── File handlers (rotating) ─────────────────────────────────────
    resolved_log_dir = _resolve_log_dir(config, log_dir)
    if resolved_log_dir:
        _add_file_handlers(root, resolved_log_dir, debug)

    # ── Vector.dev handler (opt-in) ──────────────────────────────────
    vector_enabled = enable_vector or config.get("_vector_enabled", False)
    if vector_enabled:
        _add_vector_handler(root, config)

    # ── DEPRECATED: SQLite handler ───────────────────────────────────
    if enable_sqlite:
        warnings.warn(
            "SQLite log handler is deprecated and will be removed in v6.0. "
            "Use structured JSON logging with Vector.dev instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        _add_sqlite_handler(root, config, level)

    _CONFIGURED = True

    root.info(
        "Logging configured",
        extra={
            "log_format": "json" if use_json else "text",
            "log_level": logging.getLevelName(level),
            "vector_enabled": vector_enabled,
            "sqlite_enabled": enable_sqlite,
        },
    )

    return root


def reset_logging() -> None:
    """Reset the logging configuration (for testing)."""
    global _CONFIGURED
    _CONFIGURED = False
    root = logging.getLogger("spiderfoot")
    root.handlers.clear()


def get_module_logger(module_name: str, scan_id: str = "") -> logging.Logger:
    """Get a logger for a SpiderFoot module with contextual defaults.

    Args:
        module_name: Module name (e.g. ``sfp_dnsresolve``)
        scan_id: Current scan ID for contextual logging

    Returns:
        Logger with module-specific name
    """
    logger = logging.getLogger(f"spiderfoot.modules.{module_name}")
    if scan_id:
        logger = logging.LoggerAdapter(logger, {"scanId": scan_id, "sf_module": module_name})
    return logger


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _running_in_container() -> bool:
    """Detect if we're running inside a Docker container."""
    return (
        os.path.exists("/.dockerenv")
        or os.environ.get("DOCKER_CONTAINER", "") == "1"
        or os.environ.get("KUBERNETES_SERVICE_HOST", "") != ""
    )


def _resolve_log_dir(config: dict, explicit_dir: Optional[str]) -> Optional[str]:
    """Resolve the log directory, creating it if needed."""
    log_dir = explicit_dir or config.get("_log_dir", "")

    if not log_dir:
        # Use default path
        try:
            from spiderfoot import SpiderFootHelpers
            log_dir = SpiderFootHelpers.logPath()
        except (ImportError, AttributeError):
            log_dir = os.path.join(os.getcwd(), "logs")

    try:
        os.makedirs(log_dir, exist_ok=True)
        return log_dir
    except OSError:
        return None


def _add_file_handlers(
    logger: logging.Logger, log_dir: str, debug: bool
) -> None:
    """Add rotating debug and error file handlers."""
    try:
        debug_handler = logging.handlers.TimedRotatingFileHandler(
            os.path.join(log_dir, "spiderfoot.debug.log"),
            when="d", interval=1, backupCount=30,
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(logging.Formatter(LOG_FORMAT_DEBUG))
        logger.addHandler(debug_handler)

        error_handler = logging.handlers.TimedRotatingFileHandler(
            os.path.join(log_dir, "spiderfoot.error.log"),
            when="d", interval=1, backupCount=30,
        )
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(logging.Formatter(LOG_FORMAT_DEBUG))
        logger.addHandler(error_handler)
    except OSError:
        pass  # File logging not available (read-only filesystem, etc.)


def _add_vector_handler(logger: logging.Logger, config: dict) -> None:
    """Add the Vector.dev log forwarding handler."""
    try:
        from spiderfoot.vector_sink import VectorConfig, VectorLogHandler, VectorSink

        vec_config = VectorConfig.from_sf_config(config)
        vec_config.enabled = True  # Explicitly enabled at this point
        sink = VectorSink(vec_config)
        sink.start()

        handler = VectorLogHandler(sink)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
    except Exception as e:
        logger.warning(f"Failed to initialize Vector.dev handler: {e}")


def _add_sqlite_handler(
    logger: logging.Logger, config: dict, level: int
) -> None:
    """Add the deprecated SQLite log handler."""
    try:
        from spiderfoot.logger import SpiderFootSqliteLogHandler

        sqlite_handler = SpiderFootSqliteLogHandler(config)
        sqlite_handler.setLevel(level)
        logger.addHandler(sqlite_handler)
    except Exception as e:
        logger.warning(f"Failed to initialize SQLite handler: {e}")
