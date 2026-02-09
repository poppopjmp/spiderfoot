#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         config_service
# Purpose:      Centralized configuration service with environment variable
#               override, validation, hot-reload, and per-scan config isolation.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Config Service

Centralizes all configuration handling that was previously scattered across
sf.py, sfwebui.py, and the SpiderFoot god object.

Features:
    - Hierarchical config: defaults → file → env vars → runtime overrides
    - Environment variable mapping (SF_* → internal keys)
    - Validation with type coercion
    - Per-scan config isolation (snapshot semantics)
    - Hot-reload support for file-based config
    - Thread-safe access

Usage::

    from spiderfoot.config_service import ConfigService, get_config_service

    config = get_config_service()
    config.load_defaults()
    config.load_from_file("/path/to/config.yaml")
    config.apply_env_overrides()

    # Read
    timeout = config.get("_fetchtimeout", default=15, cast=int)

    # Per-scan snapshot
    scan_config = config.snapshot()
    scan_config["_fetchtimeout"] = 30  # doesn't affect global
"""

import copy
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

log = logging.getLogger("spiderfoot.config_service")


# ---------------------------------------------------------------------------
# Environment variable mapping
# ---------------------------------------------------------------------------

# Maps SF_* env vars to internal config keys
ENV_MAP: Dict[str, str] = {
    # Core
    "SF_DEBUG": "_debug",
    "SF_LOG_LEVEL": "_loglevel",
    "SF_MAX_THREADS": "_maxthreads",
    "SF_USER_AGENT": "_useragent",
    "SF_PRODUCTION": "_production",

    # Network
    "SF_FETCH_TIMEOUT": "_fetchtimeout",
    "SF_SOCKS_TYPE": "_socks1type",
    "SF_SOCKS_HOST": "_socks2addr",
    "SF_SOCKS_PORT": "_socks3port",
    "SF_SOCKS_USER": "_socks4user",
    "SF_SOCKS_PASS": "_socks5pwd",
    "SF_DNS_SERVER": "_dnsserver",
    "SF_DNS_TIMEOUT": "_dnstimeout",

    # Web UI
    "SF_WEB_HOST": "_webhost",
    "SF_WEB_PORT": "_webport",

    # API
    "SF_API_HOST": "_apihost",
    "SF_API_PORT": "_apiport",
    "SF_API_KEY": "_apikey",

    # Database
    "SF_DB_PATH": "_dbpath",
    "POSTGRES_HOST": "_pghost",
    "POSTGRES_PORT": "_pgport",
    "POSTGRES_DB": "_pgdb",
    "POSTGRES_USER": "_pguser",
    "POSTGRES_PASSWORD": "_pgpassword",

    # Redis
    "SF_REDIS_URL": "_redis_url",
    "REDIS_HOST": "_redis_host",
    "REDIS_PORT": "_redis_port",

    # Elasticsearch
    "ELASTICSEARCH_HOST": "_es_host",
    "ELASTICSEARCH_PORT": "_es_port",
    "ELASTICSEARCH_ENABLED": "_es_enabled",

    # EventBus
    "SF_EVENTBUS_BACKEND": "_eventbus_backend",
    "SF_EVENTBUS_REDIS_URL": "_eventbus_redis_url",
    "SF_EVENTBUS_NATS_URL": "_eventbus_nats_url",

    # Cache
    "SF_CACHE_BACKEND": "_cache_backend",
    "SF_CACHE_TTL": "_cache_ttl",
    "SF_CACHE_MAX_SIZE": "_cache_max_size",
    "SF_CACHE_REDIS_URL": "_cache_redis_url",

    # Vector.dev
    "SF_VECTOR_ENABLED": "_vector_enabled",
    "SF_VECTOR_ENDPOINT": "_vector_endpoint",

    # Worker pool
    "SF_WORKER_MAX": "_worker_max",
    "SF_WORKER_STRATEGY": "_worker_strategy",

    # Scheduler
    "SF_SCANNER_MAX_SCANS": "_scheduler_max_scans",
    "SF_SCANNER_POLL_INTERVAL": "_scheduler_poll_interval",

    # DataService (microservice mode)
    "SF_DATASERVICE_BACKEND": "_dataservice_backend",
    "SF_DATASERVICE_API_URL": "_dataservice_api_url",
    "SF_DATASERVICE_API_KEY": "_dataservice_api_key",
    "SF_DATASERVICE_GRPC_HOST": "_dataservice_grpc_host",
    "SF_DATASERVICE_GRPC_PORT": "_dataservice_grpc_port",

    # WebUI (microservice mode)
    "SF_WEBUI_API_MODE": "_webui_api_mode",
    "SF_WEBUI_API_URL": "_webui_api_url",
    "SF_WEBUI_API_KEY": "_webui_api_key",

    # gRPC
    "SF_GRPC_HOST": "_grpc_host",
    "SF_GRPC_PORT": "_grpc_port",

    # Service discovery
    "SF_SERVICE_NAME": "_service_name",
    "SF_SERVICE_ROLE": "_service_role",
    "SF_DEPLOYMENT_MODE": "_deployment_mode",
}


# ---------------------------------------------------------------------------
# Type coercion helpers
# ---------------------------------------------------------------------------

_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off", ""}


def _coerce(value: Any, target_type: Type) -> Any:
    """Coerce a value to the target type."""
    if value is None:
        return None

    if target_type == bool:
        if isinstance(value, bool):
            return value
        return str(value).lower().strip() in _BOOL_TRUE

    if target_type == int:
        return int(value)

    if target_type == float:
        return float(value)

    if target_type == str:
        return str(value)

    if target_type == list:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]
        return list(value)

    return value


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

class ConfigValidator:
    """Validates configuration values against rules."""

    def __init__(self):
        self._rules: Dict[str, Dict[str, Any]] = {}

    def add_rule(self, key: str, *,
                 type: Optional[Type] = None,
                 required: bool = False,
                 min_value: Optional[float] = None,
                 max_value: Optional[float] = None,
                 choices: Optional[Set] = None,
                 default: Any = None) -> None:
        """Add a validation rule for a config key."""
        self._rules[key] = {
            "type": type,
            "required": required,
            "min_value": min_value,
            "max_value": max_value,
            "choices": choices,
            "default": default,
        }

    def validate(self, config: Dict[str, Any]) -> List[str]:
        """Validate a config dict. Returns list of error messages."""
        errors = []

        for key, rule in self._rules.items():
            value = config.get(key)

            if value is None:
                if rule["required"]:
                    errors.append(f"Required config key missing: {key}")
                continue

            if rule["type"]:
                try:
                    config[key] = _coerce(value, rule["type"])
                except (ValueError, TypeError) as e:
                    errors.append(
                        f"Config '{key}' type error: expected "
                        f"{rule['type'].__name__}, got {type(value).__name__}")
                    continue

            if rule["min_value"] is not None and config[key] < rule["min_value"]:
                errors.append(
                    f"Config '{key}' below minimum: "
                    f"{config[key]} < {rule['min_value']}")

            if rule["max_value"] is not None and config[key] > rule["max_value"]:
                errors.append(
                    f"Config '{key}' above maximum: "
                    f"{config[key]} > {rule['max_value']}")

            if rule["choices"] and config[key] not in rule["choices"]:
                errors.append(
                    f"Config '{key}' invalid choice: "
                    f"{config[key]} not in {rule['choices']}")

        return errors

    def apply_defaults(self, config: Dict[str, Any]) -> None:
        """Apply default values for missing keys."""
        for key, rule in self._rules.items():
            if key not in config and rule["default"] is not None:
                config[key] = rule["default"]


# ---------------------------------------------------------------------------
# ConfigService
# ---------------------------------------------------------------------------

class ConfigService:
    """Centralized, thread-safe configuration management.

    Supports hierarchical config with defaults → file → env → runtime.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._config: Dict[str, Any] = {}
        self._sources: Dict[str, str] = {}  # key → source (default/file/env/runtime)
        self._watchers: List[Callable] = []
        self._validator = ConfigValidator()
        self._loaded_from: Optional[str] = None
        self._last_loaded: float = 0.0

        # Register default validation rules
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register validation rules for known config keys."""
        v = self._validator

        v.add_rule("_debug", type=bool, default=False)
        v.add_rule("_maxthreads", type=int, default=3, min_value=1, max_value=100)
        v.add_rule("_fetchtimeout", type=int, default=15, min_value=1, max_value=300)
        v.add_rule("_dnstimeout", type=int, default=10, min_value=1, max_value=60)

        v.add_rule("_socks1type", type=str, default="",
                   choices={"", "HTTP", "SOCKS4", "SOCKS5", "TOR"})

        v.add_rule("_cache_backend", type=str, default="memory",
                   choices={"memory", "file", "redis"})

        v.add_rule("_eventbus_backend", type=str, default="memory",
                   choices={"memory", "redis", "nats"})

        v.add_rule("_worker_strategy", type=str, default="thread",
                   choices={"thread", "process", "async"})

        v.add_rule("_worker_max", type=int, default=8, min_value=1, max_value=64)
        v.add_rule("_scheduler_max_scans", type=int, default=3, min_value=1, max_value=50)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_defaults(self) -> None:
        """Apply default values from validation rules."""
        with self._lock:
            self._validator.apply_defaults(self._config)
            for key in list(self._config.keys()):
                if key not in self._sources:
                    self._sources[key] = "default"

    def load_dict(self, config: Dict[str, Any]) -> None:
        """Merge a configuration dict into the current config."""
        with self._lock:
            self._config.update(config)
            for key in config:
                self._sources[key] = "runtime"

    def load_from_file(self, path: str) -> bool:
        """Load configuration from a JSON or YAML file.

        Args:
            path: Path to config file.

        Returns:
            True if loaded successfully.
        """
        p = Path(path)
        if not p.exists():
            log.warning("Config file not found: %s", path)
            return False

        try:
            content = p.read_text(encoding="utf-8")

            if p.suffix in (".yaml", ".yml"):
                try:
                    import yaml
                    data = yaml.safe_load(content)
                except ImportError:
                    log.error("PyYAML not installed, cannot load YAML config")
                    return False
            else:
                data = json.loads(content)

            if isinstance(data, dict):
                with self._lock:
                    self._config.update(data)
                    for key in data:
                        self._sources[key] = f"file:{p.name}"
                    self._loaded_from = str(p)
                    self._last_loaded = time.time()
                log.info("Loaded config from %s (%d keys)", path, len(data))
                return True
            else:
                log.error("Config file root must be a dict: %s", path)
                return False

        except Exception as e:
            log.error("Failed to load config from %s: %s", path, e)
            return False

    def apply_env_overrides(self) -> None:
        """Override config values from environment variables."""
        overrides = 0
        with self._lock:
            for env_var, config_key in ENV_MAP.items():
                value = os.environ.get(env_var)
                if value is not None:
                    self._config[config_key] = value
                    self._sources[config_key] = f"env:{env_var}"
                    overrides += 1

        if overrides > 0:
            log.info("Applied %d environment variable overrides", overrides)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None,
            cast: Optional[Type] = None) -> Any:
        """Get a config value with optional type casting.

        Args:
            key: Config key.
            default: Default value if key not found.
            cast: Type to cast value to (int, float, bool, str, list).

        Returns:
            The config value.
        """
        with self._lock:
            value = self._config.get(key, default)

        if cast is not None and value is not None:
            try:
                return _coerce(value, cast)
            except (ValueError, TypeError):
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set a config value and notify watchers."""
        with self._lock:
            old_value = self._config.get(key)
            self._config[key] = value
            self._sources[key] = "runtime"

        if old_value != value:
            self._notify_watchers(key, old_value, value)

    def has(self, key: str) -> bool:
        """Check if a config key exists."""
        with self._lock:
            return key in self._config

    def keys(self) -> List[str]:
        """Return all config keys."""
        with self._lock:
            return list(self._config.keys())

    def as_dict(self) -> Dict[str, Any]:
        """Return a copy of the full config dict."""
        with self._lock:
            return copy.deepcopy(self._config)

    # ------------------------------------------------------------------
    # Snapshots (per-scan isolation)
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Create an isolated copy of the current config.

        Used to give each scan its own config that won't be affected
        by global config changes during the scan.
        """
        with self._lock:
            return copy.deepcopy(self._config)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> List[str]:
        """Validate the current configuration.

        Returns:
            List of error messages (empty = valid).
        """
        with self._lock:
            config_copy = copy.deepcopy(self._config)
        return self._validator.validate(config_copy)

    # ------------------------------------------------------------------
    # Watchers (hot-reload support)
    # ------------------------------------------------------------------

    def watch(self, callback: Callable[[str, Any, Any], None]) -> None:
        """Register a watcher for config changes.

        Args:
            callback: Called with (key, old_value, new_value) on changes.
        """
        self._watchers.append(callback)

    def _notify_watchers(self, key: str, old_value: Any,
                         new_value: Any) -> None:
        """Notify all watchers of a config change."""
        for watcher in self._watchers:
            try:
                watcher(key, old_value, new_value)
            except Exception as e:
                log.warning("Config watcher error: %s", e)

    def reload(self) -> bool:
        """Reload config from the original file.

        Returns:
            True if reloaded successfully.
        """
        if self._loaded_from:
            return self.load_from_file(self._loaded_from)

        log.warning("No config file to reload from")
        return False

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return stats about the config service."""
        with self._lock:
            source_counts: Dict[str, int] = {}
            for src in self._sources.values():
                category = src.split(":")[0]
                source_counts[category] = source_counts.get(category, 0) + 1

            return {
                "total_keys": len(self._config),
                "loaded_from": self._loaded_from,
                "last_loaded": self._last_loaded,
                "watchers": len(self._watchers),
                "env_overrides": sum(
                    1 for env_var in ENV_MAP
                    if os.environ.get(env_var) is not None
                ),
                "source_breakdown": source_counts,
                "deployment_mode": self._config.get("_deployment_mode", "monolith"),
                "service_role": self._config.get("_service_role", "standalone"),
            }

    # ------------------------------------------------------------------
    # Config source tracing
    # ------------------------------------------------------------------

    def get_source(self, key: str) -> Optional[str]:
        """Return the source that last set a config key.

        Returns one of: 'default', 'file:<name>', 'env:<VAR>', 'runtime'
        or None if the key does not exist.
        """
        with self._lock:
            return self._sources.get(key)

    def get_sources(self) -> Dict[str, str]:
        """Return all key → source mappings (for diagnostics)."""
        with self._lock:
            return dict(self._sources)

    def get_env_overrides(self) -> Dict[str, str]:
        """Return active environment variable overrides and their values.

        Useful for diagnosing which env vars are in effect.
        """
        active: Dict[str, str] = {}
        for env_var in ENV_MAP:
            value = os.environ.get(env_var)
            if value is not None:
                active[env_var] = value
        return active

    def discover_env_vars(self) -> Dict[str, Dict[str, Any]]:
        """Discover all SF_* environment variables, including unknown ones.

        Returns a dict of env_var → {value, mapped_to, known}.
        Unknown SF_* vars are flagged for debugging misconfiguration.
        """
        result: Dict[str, Dict[str, Any]] = {}
        known_vars = set(ENV_MAP.keys())

        # Check known vars
        for env_var, config_key in ENV_MAP.items():
            value = os.environ.get(env_var)
            result[env_var] = {
                "value": value,
                "mapped_to": config_key,
                "known": True,
                "active": value is not None,
            }

        # Discover unknown SF_* vars
        for env_var, value in os.environ.items():
            if env_var.startswith("SF_") and env_var not in known_vars:
                result[env_var] = {
                    "value": value,
                    "mapped_to": None,
                    "known": False,
                    "active": True,
                }
                log.debug("Unknown env var %s=%s (not in ENV_MAP)", env_var, value)

        return result

    # ------------------------------------------------------------------
    # Deployment mode helpers
    # ------------------------------------------------------------------

    @property
    def is_microservice(self) -> bool:
        """True if running in microservice deployment mode."""
        mode = self.get("_deployment_mode", "monolith")
        return str(mode).lower() in ("microservice", "microservices", "distributed")

    @property
    def service_role(self) -> str:
        """Return the service role (scanner, api, webui, standalone)."""
        return str(self.get("_service_role", "standalone"))

    @property
    def service_name(self) -> str:
        """Return the logical service name."""
        return str(self.get("_service_name", "spiderfoot"))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[ConfigService] = None
_instance_lock = threading.Lock()


def get_config_service() -> ConfigService:
    """Get or create the global ConfigService singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ConfigService()
    return _instance


def reset_config_service() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    with _instance_lock:
        _instance = None
