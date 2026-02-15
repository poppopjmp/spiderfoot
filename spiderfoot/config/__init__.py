"""SpiderFoot config subpackage.

This subpackage contains configuration management components including
application configuration, schema validation, and constants.

Usage::

    from spiderfoot.config import AppConfig, CoreConfig
    from spiderfoot.config import ConfigSchema, FieldSchema
    from spiderfoot.config.constants import DEFAULT_TTL_ONE_HOUR
"""

from __future__ import annotations

# App configuration
from .app_config import (
    ApiConfig,
    AppConfig,
    CacheBackend,
    CacheSettings,
    CoreConfig,
    DatabaseConfig,
    ElasticsearchConfig,
    EventBusBackend,
    EventBusSettings,
    LogLevel,
    NetworkConfig,
    ProxyType,
    RedisConfig,
    ValidationError,
    VectorConfig,
    WebConfig,
    WorkerConfig,
    WorkerStrategy,
)

# Config schema
from .config_schema import (
    ConfigSchema,
    FieldSchema,
    infer_schema_from_module,
    validate_module_config,
)

# Constants
from .constants import (
    DB_RETRY_BACKOFF_BASE,
    DEFAULT_API_PORT,
    DEFAULT_BATCH_SIZE,
    DEFAULT_DATABASE_NAME,
    DEFAULT_DOH_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_RESULT_LIMIT,
    DEFAULT_TTL_ONE_HOUR,
    DEFAULT_VECTOR_PORT,
    DEFAULT_VLLM_BASE_URL,
    DEFAULT_WEB_PORT,
    MAX_BODY_BYTES,
    MODULE_TIMEOUT_SECONDS,
    SESSION_IDLE_TIMEOUT,
    SHORT_CACHE_TTL_SECONDS,
)

__all__ = [
    # App configuration
    "ApiConfig",
    "AppConfig",
    "CacheBackend",
    "CacheSettings",
    "CoreConfig",
    "DatabaseConfig",
    "ElasticsearchConfig",
    "EventBusBackend",
    "EventBusSettings",
    "LogLevel",
    "NetworkConfig",
    "ProxyType",
    "RedisConfig",
    "ValidationError",
    "VectorConfig",
    "WebConfig",
    "WorkerConfig",
    "WorkerStrategy",
    # Config schema
    "ConfigSchema",
    "FieldSchema",
    "infer_schema_from_module",
    "validate_module_config",
    # Constants
    "DB_RETRY_BACKOFF_BASE",
    "DEFAULT_API_PORT",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_DATABASE_NAME",
    "DEFAULT_DOH_URL",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_OPENAI_BASE_URL",
    "DEFAULT_RESULT_LIMIT",
    "DEFAULT_TTL_ONE_HOUR",
    "DEFAULT_VECTOR_PORT",
    "DEFAULT_VLLM_BASE_URL",
    "DEFAULT_WEB_PORT",
    "MAX_BODY_BYTES",
    "MODULE_TIMEOUT_SECONDS",
    "SESSION_IDLE_TIMEOUT",
    "SHORT_CACHE_TTL_SECONDS",
]
