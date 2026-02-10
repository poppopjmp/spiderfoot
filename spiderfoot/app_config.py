"""
Typed Application Configuration for SpiderFoot.

Single source of truth for all SpiderFoot global configuration fields.
Replaces the duplicated default-config dicts scattered across sf.py,
core/config.py, api/dependencies.py, and webui/routes.py.

Features:
  - Typed dataclass sections with defaults matching legacy behaviour
  - ``from_dict()`` / ``to_dict()`` for backward-compatible flat-dict I/O
  - ``from_env()`` overlay for SF_* environment variables
  - Built-in validation with descriptive errors
  - Merge semantics: defaults -> file/db -> env -> runtime overrides

Usage::

    from spiderfoot.app_config import AppConfig

    # From scratch with defaults
    cfg = AppConfig()

    # From legacy flat dict
    cfg = AppConfig.from_dict(legacy_dict)

    # Override with env vars
    cfg.apply_env_overrides()

    # Export back to flat dict for legacy consumers
    flat = cfg.to_dict()

    # Validate
    errors = cfg.validate()
    if errors:
        raise ValueError(errors)
"""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from dataclasses import dataclass, field, fields, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from spiderfoot.constants import DEFAULT_TTL_ONE_HOUR

log = logging.getLogger("spiderfoot.app_config")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ProxyType(str, Enum):
    """Supported SOCKS / proxy types."""
    NONE = ""
    SOCKS4 = "4"
    SOCKS5 = "5"
    HTTP = "HTTP"
    TOR = "TOR"


class CacheBackend(str, Enum):
    MEMORY = "memory"
    REDIS = "redis"


class EventBusBackend(str, Enum):
    MEMORY = "memory"
    REDIS = "redis"
    NATS = "nats"


class WorkerStrategy(str, Enum):
    THREAD = "thread"
    PROCESS = "process"
    ASYNC = "async"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Section dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CoreConfig:
    """Core / general settings."""
    debug: bool = False
    max_threads: int = 3
    logging_enabled: bool = True
    output_filter: Optional[str] = None
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) "
        "Gecko/20100101 Firefox/62.0"
    )
    generic_users: str = ""
    production: bool = False


@dataclass
class NetworkConfig:
    """HTTP / DNS / proxy settings."""
    dns_server: str = ""
    dns_timeout: int = 10
    fetch_timeout: int = 5
    internet_tlds_url: str = (
        "https://publicsuffix.org/list/effective_tld_names.dat"
    )
    internet_tlds_cache_hours: int = 72
    proxy_type: str = ""       # '', '4', '5', 'HTTP', 'TOR'
    proxy_host: str = ""
    proxy_port: str = ""
    proxy_user: str = ""
    proxy_pass: str = ""


@dataclass
class DatabaseConfig:
    """Database paths and connection settings."""
    db_path: str = ""          # SQLite path (set at runtime)
    pg_host: str = ""
    pg_port: int = 5432
    pg_db: str = "spiderfoot"
    pg_user: str = ""
    pg_password: str = ""


@dataclass
class WebConfig:
    """Web UI server settings."""
    host: str = "127.0.0.1"
    port: int = 5001


@dataclass
class ApiConfig:
    """REST API server settings."""
    host: str = "127.0.0.1"
    port: int = 8001
    api_key: Optional[str] = None
    log_level: str = "INFO"
    log_file: str = ""


@dataclass
class CacheSettings:
    """Cache layer settings."""
    backend: str = "memory"
    ttl: int = DEFAULT_TTL_ONE_HOUR
    max_size: int = 10000
    redis_url: str = ""


@dataclass
class EventBusSettings:
    """Event bus settings."""
    backend: str = "memory"
    redis_url: str = ""
    nats_url: str = ""


@dataclass
class VectorConfig:
    """Vector.dev log-pipeline settings."""
    enabled: bool = False
    endpoint: str = ""


@dataclass
class WorkerConfig:
    """Worker / scanner pool settings."""
    max_workers: int = 4
    strategy: str = "thread"
    max_scans: int = 5
    poll_interval: float = 1.0


@dataclass
class RedisConfig:
    """Standalone Redis settings (used by multiple subsystems)."""
    url: str = ""
    host: str = "localhost"
    port: int = 6379


@dataclass
class ElasticsearchConfig:
    """Elasticsearch settings."""
    host: str = "localhost"
    port: int = 9200
    enabled: bool = False


# ---------------------------------------------------------------------------
# Field-key mappings  (section_attr, field_attr) <-> legacy flat key
# ---------------------------------------------------------------------------

# Maps legacy flat-dict key -> (section_attr, field_attr)
_KEY_TO_FIELD: Dict[str, Tuple[str, str]] = {
    # Core
    "_debug": ("core", "debug"),
    "_maxthreads": ("core", "max_threads"),
    "__logging": ("core", "logging_enabled"),
    "__outputfilter": ("core", "output_filter"),
    "_useragent": ("core", "user_agent"),
    "_genericusers": ("core", "generic_users"),
    "_production": ("core", "production"),

    # Network / proxy
    "_dnsserver": ("network", "dns_server"),
    "_dnstimeout": ("network", "dns_timeout"),
    "_fetchtimeout": ("network", "fetch_timeout"),
    "_internettlds": ("network", "internet_tlds_url"),
    "_internettlds_cache": ("network", "internet_tlds_cache_hours"),
    "_socks1type": ("network", "proxy_type"),
    "_socks2addr": ("network", "proxy_host"),
    "_socks3port": ("network", "proxy_port"),
    "_socks4user": ("network", "proxy_user"),
    "_socks5pwd": ("network", "proxy_pass"),

    # Database
    "__database": ("database", "db_path"),
    "_dbpath": ("database", "db_path"),
    "_pghost": ("database", "pg_host"),
    "_pgport": ("database", "pg_port"),
    "_pgdb": ("database", "pg_db"),
    "_pguser": ("database", "pg_user"),
    "_pgpassword": ("database", "pg_password"),

    # Web UI
    "_webhost": ("web", "host"),
    "_webport": ("web", "port"),
    "__webaddr": ("web", "host"),
    "__webport": ("web", "port"),

    # API
    "_apihost": ("api", "host"),
    "_apiport": ("api", "port"),
    "_apikey": ("api", "api_key"),
    "__webaddr_apikey": ("api", "api_key"),
    "__loglevel": ("api", "log_level"),
    "__logfile": ("api", "log_file"),

    # Cache
    "_cache_backend": ("cache", "backend"),
    "_cache_ttl": ("cache", "ttl"),
    "_cache_max_size": ("cache", "max_size"),
    "_cache_redis_url": ("cache", "redis_url"),

    # EventBus
    "_eventbus_backend": ("eventbus", "backend"),
    "_eventbus_redis_url": ("eventbus", "redis_url"),
    "_eventbus_nats_url": ("eventbus", "nats_url"),

    # Vector.dev
    "_vector_enabled": ("vector", "enabled"),
    "_vector_endpoint": ("vector", "endpoint"),

    # Worker
    "_worker_max": ("worker", "max_workers"),
    "_worker_strategy": ("worker", "strategy"),
    "_scheduler_max_scans": ("worker", "max_scans"),
    "_scheduler_poll_interval": ("worker", "poll_interval"),

    # Redis (standalone)
    "_redis_url": ("redis", "url"),
    "_redis_host": ("redis", "host"),
    "_redis_port": ("redis", "port"),

    # Elasticsearch
    "_es_host": ("elasticsearch", "host"),
    "_es_port": ("elasticsearch", "port"),
    "_es_enabled": ("elasticsearch", "enabled"),
}

# Reverse mapping: (section, field) -> legacy key  (first occurrence wins)
_FIELD_TO_KEY: Dict[Tuple[str, str], str] = {}
for _k, _sf in _KEY_TO_FIELD.items():
    if _sf not in _FIELD_TO_KEY:
        _FIELD_TO_KEY[_sf] = _k

# Environment variable -> legacy key (mirrors config_service.ENV_MAP)
_ENV_TO_KEY: Dict[str, str] = {
    "SF_DEBUG": "_debug",
    "SF_LOG_LEVEL": "__loglevel",
    "SF_MAX_THREADS": "_maxthreads",
    "SF_USER_AGENT": "_useragent",
    "SF_PRODUCTION": "_production",
    "SF_FETCH_TIMEOUT": "_fetchtimeout",
    "SF_SOCKS_TYPE": "_socks1type",
    "SF_SOCKS_HOST": "_socks2addr",
    "SF_SOCKS_PORT": "_socks3port",
    "SF_SOCKS_USER": "_socks4user",
    "SF_SOCKS_PASS": "_socks5pwd",
    "SF_DNS_SERVER": "_dnsserver",
    "SF_DNS_TIMEOUT": "_dnstimeout",
    "SF_WEB_HOST": "_webhost",
    "SF_WEB_PORT": "_webport",
    "SF_API_HOST": "_apihost",
    "SF_API_PORT": "_apiport",
    "SF_API_KEY": "_apikey",
    "SF_DB_PATH": "_dbpath",
    "POSTGRES_HOST": "_pghost",
    "POSTGRES_PORT": "_pgport",
    "POSTGRES_DB": "_pgdb",
    "POSTGRES_USER": "_pguser",
    "POSTGRES_PASSWORD": "_pgpassword",
    "SF_REDIS_URL": "_redis_url",
    "REDIS_HOST": "_redis_host",
    "REDIS_PORT": "_redis_port",
    "ELASTICSEARCH_HOST": "_es_host",
    "ELASTICSEARCH_PORT": "_es_port",
    "ELASTICSEARCH_ENABLED": "_es_enabled",
    "SF_EVENTBUS_BACKEND": "_eventbus_backend",
    "SF_EVENTBUS_REDIS_URL": "_eventbus_redis_url",
    "SF_EVENTBUS_NATS_URL": "_eventbus_nats_url",
    "SF_CACHE_BACKEND": "_cache_backend",
    "SF_CACHE_TTL": "_cache_ttl",
    "SF_CACHE_MAX_SIZE": "_cache_max_size",
    "SF_CACHE_REDIS_URL": "_cache_redis_url",
    "SF_VECTOR_ENABLED": "_vector_enabled",
    "SF_VECTOR_ENDPOINT": "_vector_endpoint",
    "SF_WORKER_MAX": "_worker_max",
    "SF_WORKER_STRATEGY": "_worker_strategy",
    "SF_SCANNER_MAX_SCANS": "_scheduler_max_scans",
    "SF_SCANNER_POLL_INTERVAL": "_scheduler_poll_interval",
}


# ---------------------------------------------------------------------------
# Config field descriptions (for UI / docs)
# ---------------------------------------------------------------------------

FIELD_DESCRIPTIONS: Dict[str, str] = {
    "_debug": "Enable debugging?",
    "_maxthreads": "Max number of modules to run concurrently",
    "_useragent": (
        "User-Agent string to use for HTTP requests. Prefix with an '@' "
        "to randomly select the User Agent from a file containing user "
        "agent strings for each request, e.g. @C:\\useragents.txt or "
        "@/home/bob/useragents.txt. Or supply a URL to load the list "
        "from there."
    ),
    "_dnsserver": (
        "Override the default resolver with another DNS server. "
        "For example, 8.8.8.8 is Google's open DNS server."
    ),
    "_fetchtimeout": "Number of seconds before giving up on a HTTP request.",
    "_internettlds": "List of Internet TLDs.",
    "_internettlds_cache": (
        "Hours to cache the Internet TLD list. This can safely be "
        "quite a long time given that the list doesn't change too often."
    ),
    "_genericusers": (
        "List of usernames that if found as usernames or as part of "
        "e-mail addresses, should be treated differently to non-generics."
    ),
    "_socks1type": "SOCKS Server Type. Can be '4', '5', 'HTTP' or 'TOR'",
    "_socks2addr": "SOCKS Server IP Address.",
    "_socks3port": (
        "SOCKS Server TCP Port. Usually 1080 for 4/5, 8080 for HTTP "
        "and 9050 for TOR."
    ),
    "_socks4user": "SOCKS Username. Valid only for SOCKS4 and SOCKS5 servers.",
    "_socks5pwd": "SOCKS Password. Valid only for SOCKS5 servers.",
    "_modulesenabled": "Modules enabled for the scan.",
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

class ValidationError:
    """Single validation failure."""

    __slots__ = ("field", "message", "value")

    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.message = message
        self.value = value

    def __repr__(self) -> str:
        return f"ValidationError({self.field!r}, {self.message!r})"

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


# ---------------------------------------------------------------------------
# AppConfig — main typed configuration
# ---------------------------------------------------------------------------

@dataclass
class AppConfig:
    """Typed SpiderFoot application configuration.

    Groups all settings into logical sections.  Each section is a
    nested dataclass with sensible defaults matching the legacy
    ``sfConfig`` dictionary.
    """

    core: CoreConfig = field(default_factory=CoreConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    web: WebConfig = field(default_factory=WebConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    cache: CacheSettings = field(default_factory=CacheSettings)
    eventbus: EventBusSettings = field(default_factory=EventBusSettings)
    vector: VectorConfig = field(default_factory=VectorConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    elasticsearch: ElasticsearchConfig = field(
        default_factory=ElasticsearchConfig
    )

    # Opaque containers for module / correlation data (no typed schema)
    modules: Optional[Dict[str, Any]] = None
    correlation_rules: Optional[List[Any]] = None
    version: str = ""

    # ---- Extra keys not in any section (forward-compat) ----
    _extra: Dict[str, Any] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AppConfig":
        """Build an ``AppConfig`` from a legacy flat config dict.

        Unknown keys are preserved in ``_extra`` so nothing is lost
        during round-trip conversion.
        """
        cfg = cls()
        consumed: set = set()

        for key, value in d.items():
            if key == "__modules__":
                cfg.modules = value
                consumed.add(key)
            elif key == "__correlationrules__":
                cfg.correlation_rules = value
                consumed.add(key)
            elif key == "__version__":
                cfg.version = str(value) if value else ""
                consumed.add(key)
            elif key == "__globaloptdescs__":
                consumed.add(key)
            elif key in _KEY_TO_FIELD:
                section_attr, field_attr = _KEY_TO_FIELD[key]
                section = getattr(cfg, section_attr)
                _set_field(section, field_attr, value)
                consumed.add(key)

        # Stash anything we didn't recognise
        for key, value in d.items():
            if key not in consumed:
                cfg._extra[key] = value

        return cfg

    def to_dict(self) -> Dict[str, Any]:
        """Export back to a legacy flat config dict.

        Round-trips: ``AppConfig.from_dict(d).to_dict()`` preserves
        all keys from the original dict (mapped keys are re-exported
        under their canonical legacy name; extras are passed through).
        """
        out: Dict[str, Any] = {}

        # Walk every mapped field and emit the canonical legacy key
        for (section_attr, field_attr), legacy_key in _FIELD_TO_KEY.items():
            section = getattr(self, section_attr, None)
            if section is None:
                continue
            val = getattr(section, field_attr, None)
            out[legacy_key] = val

        # Special containers
        out["__modules__"] = self.modules
        out["__correlationrules__"] = self.correlation_rules
        if self.version:
            out["__version__"] = self.version

        # Descriptions (expected by legacy consumers)
        out["__globaloptdescs__"] = FIELD_DESCRIPTIONS

        # Extra passthrough
        out.update(self._extra)

        return out

    # ------------------------------------------------------------------
    # Environment variable overlay
    # ------------------------------------------------------------------

    def apply_env_overrides(self) -> List[str]:
        """Read ``SF_*`` environment variables and override matching fields.

        Returns a list of keys that were overridden (for logging).
        """
        overridden: List[str] = []

        for env_var, legacy_key in _ENV_TO_KEY.items():
            raw = os.environ.get(env_var)
            if raw is None:
                continue

            mapping = _KEY_TO_FIELD.get(legacy_key)
            if mapping is None:
                continue

            section_attr, field_attr = mapping
            section = getattr(self, section_attr)
            _set_field(section, field_attr, raw)
            overridden.append(env_var)

        if overridden:
            log.info(
                "Applied %d env-var override(s): %s",
                len(overridden),
                ", ".join(overridden),
            )
        return overridden

    # ------------------------------------------------------------------
    # Merge / update
    # ------------------------------------------------------------------

    def merge(self, overrides: Dict[str, Any]) -> None:
        """Apply a flat dict of overrides (same keys as legacy config).

        Useful for applying DB-stored user settings on top of defaults.
        """
        for key, value in overrides.items():
            if key == "__modules__":
                self.modules = value
            elif key == "__correlationrules__":
                self.correlation_rules = value
            elif key == "__version__":
                self.version = str(value) if value else ""
            elif key in _KEY_TO_FIELD:
                section_attr, field_attr = _KEY_TO_FIELD[key]
                section = getattr(self, section_attr)
                _set_field(section, field_attr, value)
            else:
                self._extra[key] = value

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> List[ValidationError]:
        """Validate all fields. Returns a list of errors (empty = valid)."""
        errors: List[ValidationError] = []

        # Core
        if self.core.max_threads < 1:
            errors.append(ValidationError(
                "_maxthreads",
                "Must be >= 1",
                self.core.max_threads,
            ))
        if self.core.max_threads > 200:
            errors.append(ValidationError(
                "_maxthreads",
                "Must be <= 200 (excessive concurrency)",
                self.core.max_threads,
            ))

        # Network
        if self.network.fetch_timeout < 1:
            errors.append(ValidationError(
                "_fetchtimeout",
                "Must be >= 1 second",
                self.network.fetch_timeout,
            ))
        if self.network.fetch_timeout > 300:
            errors.append(ValidationError(
                "_fetchtimeout",
                "Must be <= 300 seconds",
                self.network.fetch_timeout,
            ))
        if self.network.dns_timeout < 1:
            errors.append(ValidationError(
                "_dnstimeout",
                "Must be >= 1 second",
                self.network.dns_timeout,
            ))
        if self.network.proxy_type and self.network.proxy_type not in (
            "", "4", "5", "HTTP", "TOR"
        ):
            errors.append(ValidationError(
                "_socks1type",
                "Must be one of: '', '4', '5', 'HTTP', 'TOR'",
                self.network.proxy_type,
            ))
        if self.network.proxy_type and not self.network.proxy_host:
            errors.append(ValidationError(
                "_socks2addr",
                "Proxy host is required when proxy type is set",
            ))
        if self.network.internet_tlds_cache_hours < 0:
            errors.append(ValidationError(
                "_internettlds_cache",
                "Must be >= 0",
                self.network.internet_tlds_cache_hours,
            ))

        # Database
        if self.database.pg_host and self.database.pg_port < 1:
            errors.append(ValidationError(
                "_pgport",
                "Invalid PostgreSQL port",
                self.database.pg_port,
            ))

        # Web
        if self.web.port < 1 or self.web.port > 65535:
            errors.append(ValidationError(
                "_webport",
                "Must be 1-65535",
                self.web.port,
            ))

        # API
        if self.api.port < 1 or self.api.port > 65535:
            errors.append(ValidationError(
                "_apiport",
                "Must be 1-65535",
                self.api.port,
            ))
        if self.api.log_level.upper() not in (
            "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
        ):
            errors.append(ValidationError(
                "__loglevel",
                "Invalid log level",
                self.api.log_level,
            ))

        # Cache
        if self.cache.backend not in ("memory", "redis"):
            errors.append(ValidationError(
                "_cache_backend",
                "Must be 'memory' or 'redis'",
                self.cache.backend,
            ))
        if self.cache.ttl < 0:
            errors.append(ValidationError(
                "_cache_ttl",
                "Must be >= 0",
                self.cache.ttl,
            ))

        # EventBus
        if self.eventbus.backend not in ("memory", "redis", "nats"):
            errors.append(ValidationError(
                "_eventbus_backend",
                "Must be 'memory', 'redis', or 'nats'",
                self.eventbus.backend,
            ))

        # Worker
        if self.worker.max_workers < 1:
            errors.append(ValidationError(
                "_worker_max",
                "Must be >= 1",
                self.worker.max_workers,
            ))
        if self.worker.strategy not in ("thread", "process", "async"):
            errors.append(ValidationError(
                "_worker_strategy",
                "Must be 'thread', 'process', or 'async'",
                self.worker.strategy,
            ))
        if self.worker.max_scans < 1:
            errors.append(ValidationError(
                "_scheduler_max_scans",
                "Must be >= 1",
                self.worker.max_scans,
            ))

        return errors

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def get(self, legacy_key: str, default: Any = None) -> Any:
        """Look up a value by legacy flat-dict key name.

        Allows ``cfg.get("_maxthreads")`` style access for gradual
        migration from the untyped dict.
        """
        if legacy_key == "__modules__":
            return self.modules
        if legacy_key == "__correlationrules__":
            return self.correlation_rules
        if legacy_key == "__version__":
            return self.version
        if legacy_key == "__globaloptdescs__":
            return FIELD_DESCRIPTIONS

        mapping = _KEY_TO_FIELD.get(legacy_key)
        if mapping is not None:
            section_attr, field_attr = mapping
            section = getattr(self, section_attr)
            return getattr(section, field_attr, default)

        return self._extra.get(legacy_key, default)

    def __getitem__(self, key: str) -> Any:
        """Dict-style access for backward compatibility."""
        val = self.get(key, _SENTINEL)
        if val is _SENTINEL:
            raise KeyError(key)
        return val

    def __contains__(self, key: str) -> bool:
        """Support ``'key' in cfg`` checks."""
        return self.get(key, _SENTINEL) is not _SENTINEL

    # ------------------------------------------------------------------
    # repr / summary
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Return a concise overview suitable for logging."""
        return {
            "debug": self.core.debug,
            "max_threads": self.core.max_threads,
            "db_path": self.database.db_path,
            "web": f"{self.web.host}:{self.web.port}",
            "api": f"{self.api.host}:{self.api.port}",
            "proxy": self.network.proxy_type or "none",
            "cache": self.cache.backend,
            "eventbus": self.eventbus.backend,
            "vector": self.vector.enabled,
            "workers": f"{self.worker.max_workers} ({self.worker.strategy})",
            "extra_keys": len(self._extra),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SENTINEL = object()


def _set_field(section: Any, field_attr: str, value: Any) -> None:
    """Coerce *value* to the target field's type and set it."""
    # Discover the target type from the dataclass field default
    target_type: type = str
    for f in fields(section):
        if f.name == field_attr:
            origin = getattr(f.type, "__origin__", None)
            if f.type in (bool, int, float, str):
                target_type = f.type
            elif f.type == "bool":
                target_type = bool
            elif f.type == "int":
                target_type = int
            elif f.type == "float":
                target_type = float
            elif f.type == "str":
                target_type = str
            else:
                # Optional[X] or complex — keep as-is
                target_type = type(None)
            break

    if target_type is type(None):
        setattr(section, field_attr, value)
        return

    # Coerce string env-var values
    if isinstance(value, str) and target_type is not str:
        value = _coerce(value, target_type)

    # Coerce numeric strings that came from DB (all DB values are strings)
    if target_type is int and isinstance(value, float):
        value = int(value)

    setattr(section, field_attr, value)


def _coerce(raw: str, target: type) -> Any:
    """Best-effort coercion from string to target type."""
    if target is bool:
        return raw.lower() in ("1", "true", "yes", "on")
    if target is int:
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 0
    if target is float:
        try:
            return float(raw)
        except (ValueError, TypeError):
            return 0.0
    return raw
