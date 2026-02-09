"""
Tests for spiderfoot.app_config — Typed Application Configuration.

Covers: section defaults, from_dict / to_dict round-trip, env-var
overlays, validation, dict-style access, merge, and descriptions.
"""

import os
import time
from copy import deepcopy
from unittest.mock import patch

import pytest

from spiderfoot.app_config import (
    ApiConfig,
    AppConfig,
    CacheBackend,
    CacheSettings,
    CoreConfig,
    DatabaseConfig,
    ElasticsearchConfig,
    EventBusBackend,
    EventBusSettings,
    FIELD_DESCRIPTIONS,
    LogLevel,
    NetworkConfig,
    ProxyType,
    RedisConfig,
    ValidationError,
    VectorConfig,
    WebConfig,
    WorkerConfig,
    WorkerStrategy,
    _KEY_TO_FIELD,
    _ENV_TO_KEY,
    _FIELD_TO_KEY,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _legacy_config(**overrides) -> dict:
    """Create a legacy-style flat config dict with optional overrides."""
    cfg = {
        "_debug": False,
        "_maxthreads": 3,
        "__logging": True,
        "__outputfilter": None,
        "_useragent": "TestBot/1.0",
        "_dnsserver": "",
        "_fetchtimeout": 5,
        "_internettlds": "https://publicsuffix.org/list/effective_tld_names.dat",
        "_internettlds_cache": 72,
        "_genericusers": "",
        "__database": "/tmp/test.db",
        "__modules__": None,
        "__correlationrules__": None,
        "_socks1type": "",
        "_socks2addr": "",
        "_socks3port": "",
        "_socks4user": "",
        "_socks5pwd": "",
    }
    cfg.update(overrides)
    return cfg


# ===================================================================
# Section defaults
# ===================================================================

class TestSectionDefaults:
    def test_core_defaults(self):
        c = CoreConfig()
        assert c.debug is False
        assert c.max_threads == 3
        assert c.logging_enabled is True
        assert c.output_filter is None
        assert "Firefox" in c.user_agent
        assert c.generic_users == ""
        assert c.production is False

    def test_network_defaults(self):
        n = NetworkConfig()
        assert n.dns_server == ""
        assert n.dns_timeout == 10
        assert n.fetch_timeout == 5
        assert "publicsuffix.org" in n.internet_tlds_url
        assert n.internet_tlds_cache_hours == 72
        assert n.proxy_type == ""
        assert n.proxy_host == ""
        assert n.proxy_port == ""

    def test_database_defaults(self):
        d = DatabaseConfig()
        assert d.db_path == ""
        assert d.pg_host == ""
        assert d.pg_port == 5432
        assert d.pg_db == "spiderfoot"

    def test_web_defaults(self):
        w = WebConfig()
        assert w.host == "127.0.0.1"
        assert w.port == 5001

    def test_api_defaults(self):
        a = ApiConfig()
        assert a.host == "127.0.0.1"
        assert a.port == 8001
        assert a.api_key is None
        assert a.log_level == "INFO"

    def test_cache_defaults(self):
        c = CacheSettings()
        assert c.backend == "memory"
        assert c.ttl == 3600
        assert c.max_size == 10000

    def test_eventbus_defaults(self):
        e = EventBusSettings()
        assert e.backend == "memory"
        assert e.redis_url == ""
        assert e.nats_url == ""

    def test_vector_defaults(self):
        v = VectorConfig()
        assert v.enabled is False
        assert v.endpoint == ""

    def test_worker_defaults(self):
        w = WorkerConfig()
        assert w.max_workers == 4
        assert w.strategy == "thread"
        assert w.max_scans == 5
        assert w.poll_interval == 1.0

    def test_redis_defaults(self):
        r = RedisConfig()
        assert r.url == ""
        assert r.host == "localhost"
        assert r.port == 6379

    def test_elasticsearch_defaults(self):
        e = ElasticsearchConfig()
        assert e.host == "localhost"
        assert e.port == 9200
        assert e.enabled is False


# ===================================================================
# AppConfig construction
# ===================================================================

class TestAppConfigConstruction:
    def test_default_construction(self):
        cfg = AppConfig()
        assert cfg.core.debug is False
        assert cfg.modules is None
        assert cfg.correlation_rules is None
        assert cfg.version == ""
        assert cfg._extra == {}

    def test_from_dict_core_fields(self):
        d = _legacy_config(_debug=True, _maxthreads=10)
        cfg = AppConfig.from_dict(d)
        assert cfg.core.debug is True
        assert cfg.core.max_threads == 10

    def test_from_dict_all_defaults(self):
        d = _legacy_config()
        cfg = AppConfig.from_dict(d)
        assert cfg.core.user_agent == "TestBot/1.0"
        assert cfg.network.fetch_timeout == 5
        assert cfg.database.db_path == "/tmp/test.db"

    def test_from_dict_modules(self):
        mods = {"sfp_test": {"opts": {}}}
        d = _legacy_config(__modules__=mods)
        cfg = AppConfig.from_dict(d)
        assert cfg.modules == mods

    def test_from_dict_correlation_rules(self):
        rules = [{"name": "r1"}]
        d = _legacy_config(__correlationrules__=rules)
        cfg = AppConfig.from_dict(d)
        assert cfg.correlation_rules == rules

    def test_from_dict_version(self):
        d = _legacy_config()
        d["__version__"] = "5.23.0"
        cfg = AppConfig.from_dict(d)
        assert cfg.version == "5.23.0"

    def test_from_dict_extra_keys_preserved(self):
        d = _legacy_config()
        d["_custom_plugin_key"] = "hello"
        d["scan_defaults"] = {"timeout": 30}
        cfg = AppConfig.from_dict(d)
        assert cfg._extra["_custom_plugin_key"] == "hello"
        assert cfg._extra["scan_defaults"] == {"timeout": 30}

    def test_from_dict_proxy_settings(self):
        d = _legacy_config(
            _socks1type="5",
            _socks2addr="10.0.0.1",
            _socks3port="1080",
            _socks4user="admin",
            _socks5pwd="secret",
        )
        cfg = AppConfig.from_dict(d)
        assert cfg.network.proxy_type == "5"
        assert cfg.network.proxy_host == "10.0.0.1"
        assert cfg.network.proxy_port == "1080"
        assert cfg.network.proxy_user == "admin"
        assert cfg.network.proxy_pass == "secret"

    def test_from_dict_api_settings(self):
        d = _legacy_config()
        d["__webaddr"] = "0.0.0.0"
        d["__webport"] = 9001
        d["__webaddr_apikey"] = "my-api-key"
        d["__loglevel"] = "DEBUG"
        cfg = AppConfig.from_dict(d)
        assert cfg.web.host == "0.0.0.0"
        assert cfg.web.port == 9001
        assert cfg.api.api_key == "my-api-key"
        assert cfg.api.log_level == "DEBUG"

    def test_from_dict_globaloptdescs_ignored(self):
        d = _legacy_config()
        d["__globaloptdescs__"] = {"_debug": "desc"}
        cfg = AppConfig.from_dict(d)
        assert "__globaloptdescs__" not in cfg._extra


# ===================================================================
# to_dict / round-trip
# ===================================================================

class TestToDict:
    def test_to_dict_contains_core_keys(self):
        cfg = AppConfig()
        d = cfg.to_dict()
        assert "_debug" in d
        assert "_maxthreads" in d
        assert "__logging" in d
        assert "_useragent" in d

    def test_to_dict_modules(self):
        cfg = AppConfig()
        cfg.modules = {"sfp_test": {}}
        d = cfg.to_dict()
        assert d["__modules__"] == {"sfp_test": {}}

    def test_to_dict_descriptions(self):
        d = AppConfig().to_dict()
        assert "__globaloptdescs__" in d
        assert "_debug" in d["__globaloptdescs__"]

    def test_to_dict_extras_preserved(self):
        cfg = AppConfig()
        cfg._extra["custom_key"] = "value"
        d = cfg.to_dict()
        assert d["custom_key"] == "value"

    def test_round_trip_preserves_values(self):
        original = _legacy_config(
            _debug=True,
            _maxthreads=8,
            _fetchtimeout=15,
            _socks1type="TOR",
            _socks2addr="127.0.0.1",
        )
        original["__modules__"] = {"sfp_x": {}}
        original["custom_addon"] = 42

        cfg = AppConfig.from_dict(original)
        exported = cfg.to_dict()

        assert exported["_debug"] is True
        assert exported["_maxthreads"] == 8
        assert exported["_fetchtimeout"] == 15
        assert exported["_socks1type"] == "TOR"
        assert exported["_socks2addr"] == "127.0.0.1"
        assert exported["__modules__"] == {"sfp_x": {}}
        assert exported["custom_addon"] == 42

    def test_round_trip_default_config(self):
        """from_dict then to_dict should preserve all default keys."""
        original = _legacy_config()
        cfg = AppConfig.from_dict(original)
        exported = cfg.to_dict()
        for key in original:
            if key in ("__globaloptdescs__",):
                continue
            assert key in exported, f"Key {key} lost in round-trip"

    def test_version_round_trip(self):
        d = _legacy_config()
        d["__version__"] = "5.0.0"
        cfg = AppConfig.from_dict(d)
        assert cfg.to_dict()["__version__"] == "5.0.0"


# ===================================================================
# Environment variable overlay
# ===================================================================

class TestEnvOverrides:
    def test_apply_single_env_var(self):
        cfg = AppConfig()
        with patch.dict(os.environ, {"SF_DEBUG": "true"}):
            overridden = cfg.apply_env_overrides()
        assert cfg.core.debug is True
        assert "SF_DEBUG" in overridden

    def test_apply_numeric_env_var(self):
        cfg = AppConfig()
        with patch.dict(os.environ, {"SF_MAX_THREADS": "16"}):
            cfg.apply_env_overrides()
        assert cfg.core.max_threads == 16

    def test_apply_multiple_env_vars(self):
        cfg = AppConfig()
        env = {
            "SF_FETCH_TIMEOUT": "30",
            "SF_DNS_SERVER": "8.8.8.8",
            "SF_API_KEY": "secret123",
        }
        with patch.dict(os.environ, env, clear=False):
            overridden = cfg.apply_env_overrides()
        assert cfg.network.fetch_timeout == 30
        assert cfg.network.dns_server == "8.8.8.8"
        assert cfg.api.api_key == "secret123"
        assert len(overridden) == 3

    def test_env_var_bool_false(self):
        cfg = AppConfig()
        cfg.core.debug = True
        with patch.dict(os.environ, {"SF_DEBUG": "false"}):
            cfg.apply_env_overrides()
        assert cfg.core.debug is False

    def test_no_env_vars_returns_empty(self):
        cfg = AppConfig()
        # Ensure none of the SF_* vars are set
        clean_env = {k: v for k, v in os.environ.items()
                     if not k.startswith("SF_") and k not in _ENV_TO_KEY}
        with patch.dict(os.environ, clean_env, clear=True):
            overridden = cfg.apply_env_overrides()
        assert overridden == []

    def test_env_postgres_settings(self):
        cfg = AppConfig()
        env = {
            "POSTGRES_HOST": "db.example.com",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DB": "mydb",
            "POSTGRES_USER": "app",
            "POSTGRES_PASSWORD": "pass",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg.apply_env_overrides()
        assert cfg.database.pg_host == "db.example.com"
        assert cfg.database.pg_port == 5433
        assert cfg.database.pg_db == "mydb"
        assert cfg.database.pg_user == "app"
        assert cfg.database.pg_password == "pass"

    def test_env_redis_settings(self):
        cfg = AppConfig()
        with patch.dict(os.environ, {"SF_REDIS_URL": "redis://my-host:6380"}):
            cfg.apply_env_overrides()
        assert cfg.redis.url == "redis://my-host:6380"

    def test_env_eventbus_settings(self):
        cfg = AppConfig()
        env = {
            "SF_EVENTBUS_BACKEND": "nats",
            "SF_EVENTBUS_NATS_URL": "nats://localhost:4222",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg.apply_env_overrides()
        assert cfg.eventbus.backend == "nats"
        assert cfg.eventbus.nats_url == "nats://localhost:4222"

    def test_env_vector_settings(self):
        cfg = AppConfig()
        with patch.dict(os.environ, {
            "SF_VECTOR_ENABLED": "yes",
            "SF_VECTOR_ENDPOINT": "http://vector:8686",
        }):
            cfg.apply_env_overrides()
        assert cfg.vector.enabled is True
        assert cfg.vector.endpoint == "http://vector:8686"

    def test_env_worker_settings(self):
        cfg = AppConfig()
        env = {
            "SF_WORKER_MAX": "8",
            "SF_WORKER_STRATEGY": "process",
            "SF_SCANNER_MAX_SCANS": "10",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg.apply_env_overrides()
        assert cfg.worker.max_workers == 8
        assert cfg.worker.strategy == "process"
        assert cfg.worker.max_scans == 10


# ===================================================================
# Validation
# ===================================================================

class TestValidation:
    def test_valid_config(self):
        cfg = AppConfig()
        errors = cfg.validate()
        assert errors == []

    def test_max_threads_too_low(self):
        cfg = AppConfig()
        cfg.core.max_threads = 0
        errors = cfg.validate()
        assert any(e.field == "_maxthreads" for e in errors)

    def test_max_threads_too_high(self):
        cfg = AppConfig()
        cfg.core.max_threads = 300
        errors = cfg.validate()
        assert any(e.field == "_maxthreads" and "200" in e.message
                   for e in errors)

    def test_fetch_timeout_too_low(self):
        cfg = AppConfig()
        cfg.network.fetch_timeout = 0
        errors = cfg.validate()
        assert any(e.field == "_fetchtimeout" for e in errors)

    def test_fetch_timeout_too_high(self):
        cfg = AppConfig()
        cfg.network.fetch_timeout = 999
        errors = cfg.validate()
        assert any(e.field == "_fetchtimeout" for e in errors)

    def test_dns_timeout_too_low(self):
        cfg = AppConfig()
        cfg.network.dns_timeout = 0
        errors = cfg.validate()
        assert any(e.field == "_dnstimeout" for e in errors)

    def test_invalid_proxy_type(self):
        cfg = AppConfig()
        cfg.network.proxy_type = "INVALID"
        errors = cfg.validate()
        assert any(e.field == "_socks1type" for e in errors)

    def test_proxy_without_host(self):
        cfg = AppConfig()
        cfg.network.proxy_type = "5"
        cfg.network.proxy_host = ""
        errors = cfg.validate()
        assert any(e.field == "_socks2addr" for e in errors)

    def test_proxy_with_host_ok(self):
        cfg = AppConfig()
        cfg.network.proxy_type = "5"
        cfg.network.proxy_host = "10.0.0.1"
        errors = cfg.validate()
        assert not any(e.field == "_socks2addr" for e in errors)

    def test_invalid_web_port(self):
        cfg = AppConfig()
        cfg.web.port = 0
        errors = cfg.validate()
        assert any(e.field == "_webport" for e in errors)

    def test_invalid_web_port_too_high(self):
        cfg = AppConfig()
        cfg.web.port = 99999
        errors = cfg.validate()
        assert any(e.field == "_webport" for e in errors)

    def test_invalid_api_port(self):
        cfg = AppConfig()
        cfg.api.port = -1
        errors = cfg.validate()
        assert any(e.field == "_apiport" for e in errors)

    def test_invalid_log_level(self):
        cfg = AppConfig()
        cfg.api.log_level = "VERBOSE"
        errors = cfg.validate()
        assert any(e.field == "__loglevel" for e in errors)

    def test_invalid_cache_backend(self):
        cfg = AppConfig()
        cfg.cache.backend = "memcached"
        errors = cfg.validate()
        assert any(e.field == "_cache_backend" for e in errors)

    def test_invalid_eventbus_backend(self):
        cfg = AppConfig()
        cfg.eventbus.backend = "kafka"
        errors = cfg.validate()
        assert any(e.field == "_eventbus_backend" for e in errors)

    def test_invalid_worker_strategy(self):
        cfg = AppConfig()
        cfg.worker.strategy = "coroutine"
        errors = cfg.validate()
        assert any(e.field == "_worker_strategy" for e in errors)

    def test_worker_max_too_low(self):
        cfg = AppConfig()
        cfg.worker.max_workers = 0
        errors = cfg.validate()
        assert any(e.field == "_worker_max" for e in errors)

    def test_max_scans_too_low(self):
        cfg = AppConfig()
        cfg.worker.max_scans = 0
        errors = cfg.validate()
        assert any(e.field == "_scheduler_max_scans" for e in errors)

    def test_cache_ttl_negative(self):
        cfg = AppConfig()
        cfg.cache.ttl = -1
        errors = cfg.validate()
        assert any(e.field == "_cache_ttl" for e in errors)

    def test_tld_cache_negative(self):
        cfg = AppConfig()
        cfg.network.internet_tlds_cache_hours = -5
        errors = cfg.validate()
        assert any(e.field == "_internettlds_cache" for e in errors)

    def test_pg_port_invalid(self):
        cfg = AppConfig()
        cfg.database.pg_host = "db.example.com"
        cfg.database.pg_port = 0
        errors = cfg.validate()
        assert any(e.field == "_pgport" for e in errors)

    def test_validation_error_repr(self):
        e = ValidationError("_debug", "bad", True)
        assert "_debug" in repr(e)
        assert "bad" in str(e)

    def test_multiple_errors(self):
        cfg = AppConfig()
        cfg.core.max_threads = 0
        cfg.network.fetch_timeout = 0
        cfg.web.port = 0
        errors = cfg.validate()
        assert len(errors) >= 3


# ===================================================================
# Dict-style access
# ===================================================================

class TestDictAccess:
    def test_getitem_core(self):
        cfg = AppConfig()
        assert cfg["_debug"] is False
        assert cfg["_maxthreads"] == 3

    def test_getitem_modules(self):
        cfg = AppConfig()
        cfg.modules = {"sfp_a": {}}
        assert cfg["__modules__"] == {"sfp_a": {}}

    def test_getitem_missing_raises(self):
        cfg = AppConfig()
        with pytest.raises(KeyError):
            _ = cfg["nonexistent_key"]

    def test_contains(self):
        cfg = AppConfig()
        assert "_debug" in cfg
        assert "_maxthreads" in cfg
        assert "__modules__" in cfg
        assert "nonexistent" not in cfg

    def test_get_with_default(self):
        cfg = AppConfig()
        assert cfg.get("nonexistent", 42) == 42

    def test_get_globaloptdescs(self):
        cfg = AppConfig()
        descs = cfg.get("__globaloptdescs__")
        assert isinstance(descs, dict)
        assert "_debug" in descs

    def test_get_extra_key(self):
        cfg = AppConfig()
        cfg._extra["custom_thing"] = "hello"
        assert cfg.get("custom_thing") == "hello"
        assert cfg["custom_thing"] == "hello"
        assert "custom_thing" in cfg


# ===================================================================
# Merge
# ===================================================================

class TestMerge:
    def test_merge_updates_fields(self):
        cfg = AppConfig()
        cfg.merge({"_debug": True, "_maxthreads": 16})
        assert cfg.core.debug is True
        assert cfg.core.max_threads == 16

    def test_merge_modules(self):
        cfg = AppConfig()
        mods = {"sfp_test": {}}
        cfg.merge({"__modules__": mods})
        assert cfg.modules == mods

    def test_merge_extra_keys(self):
        cfg = AppConfig()
        cfg.merge({"_custom_key": "val"})
        assert cfg._extra["_custom_key"] == "val"

    def test_merge_preserves_unrelated(self):
        cfg = AppConfig()
        cfg.core.user_agent = "Custom/1.0"
        cfg.merge({"_debug": True})
        assert cfg.core.user_agent == "Custom/1.0"

    def test_merge_version(self):
        cfg = AppConfig()
        cfg.merge({"__version__": "9.9.9"})
        assert cfg.version == "9.9.9"


# ===================================================================
# Type coercion
# ===================================================================

class TestTypeCoercion:
    def test_string_to_bool_true(self):
        cfg = AppConfig.from_dict({"_debug": "1"})
        assert cfg.core.debug is True

    def test_string_to_bool_false(self):
        cfg = AppConfig.from_dict({"_debug": "0"})
        assert cfg.core.debug is False

    def test_string_to_int(self):
        cfg = AppConfig.from_dict({"_maxthreads": "10"})
        assert cfg.core.max_threads == 10

    def test_float_to_int(self):
        cfg = AppConfig.from_dict({"_maxthreads": 5.0})
        assert cfg.core.max_threads == 5
        assert isinstance(cfg.core.max_threads, int)

    def test_string_to_int_invalid(self):
        cfg = AppConfig.from_dict({"_maxthreads": "abc"})
        assert cfg.core.max_threads == 0  # falls back to 0

    def test_int_to_bool(self):
        """Native int 1/0 -> bool is kept as int (no coercion needed)."""
        cfg = AppConfig.from_dict({"_debug": 1})
        # int 1 is truthy — we keep the Python-native behaviour
        assert cfg.core.debug == 1

    def test_none_for_optional(self):
        cfg = AppConfig.from_dict({"__outputfilter": None})
        assert cfg.core.output_filter is None


# ===================================================================
# Mapping completeness
# ===================================================================

class TestMappings:
    def test_key_to_field_all_sections_valid(self):
        """Every mapping must point to a real section attribute."""
        cfg = AppConfig()
        for key, (section, fld) in _KEY_TO_FIELD.items():
            assert hasattr(cfg, section), \
                f"Key {key} -> section {section} not found on AppConfig"
            sec = getattr(cfg, section)
            assert hasattr(sec, fld), \
                f"Key {key} -> field {fld} not found on {type(sec).__name__}"

    def test_env_map_all_keys_exist(self):
        """Every env var must map to a known legacy key."""
        for env_var, legacy_key in _ENV_TO_KEY.items():
            assert legacy_key in _KEY_TO_FIELD, \
                f"Env var {env_var} -> {legacy_key} not in _KEY_TO_FIELD"

    def test_field_to_key_reverse(self):
        """Every field has a reverse mapping to a legacy key."""
        for (section, fld), key in _FIELD_TO_KEY.items():
            assert key in _KEY_TO_FIELD
            assert _KEY_TO_FIELD[key] == (section, fld)


# ===================================================================
# Summary
# ===================================================================

class TestSummary:
    def test_summary_keys(self):
        cfg = AppConfig()
        s = cfg.summary()
        assert "debug" in s
        assert "max_threads" in s
        assert "db_path" in s
        assert "web" in s
        assert "api" in s
        assert "cache" in s
        assert "eventbus" in s
        assert "workers" in s

    def test_summary_format(self):
        cfg = AppConfig()
        s = cfg.summary()
        assert s["web"] == "127.0.0.1:5001"
        assert s["api"] == "127.0.0.1:8001"
        assert "thread" in s["workers"]


# ===================================================================
# Enums
# ===================================================================

class TestEnums:
    def test_proxy_type_values(self):
        assert ProxyType.NONE == ""
        assert ProxyType.SOCKS5 == "5"
        assert ProxyType.TOR == "TOR"

    def test_cache_backend_values(self):
        assert CacheBackend.MEMORY == "memory"
        assert CacheBackend.REDIS == "redis"

    def test_eventbus_backend_values(self):
        assert EventBusBackend.MEMORY == "memory"
        assert EventBusBackend.NATS == "nats"

    def test_worker_strategy_values(self):
        assert WorkerStrategy.THREAD == "thread"
        assert WorkerStrategy.PROCESS == "process"
        assert WorkerStrategy.ASYNC == "async"

    def test_log_level_values(self):
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"


# ===================================================================
# Edge cases
# ===================================================================

class TestEdgeCases:
    def test_empty_dict(self):
        cfg = AppConfig.from_dict({})
        assert cfg.core.debug is False  # defaults

    def test_from_dict_is_independent(self):
        d = _legacy_config()
        cfg = AppConfig.from_dict(d)
        d["_debug"] = True
        assert cfg.core.debug is False  # not affected

    def test_to_dict_is_independent(self):
        cfg = AppConfig()
        d = cfg.to_dict()
        d["_debug"] = True
        assert cfg.core.debug is False

    def test_multiple_legacy_keys_for_same_field(self):
        """__database and _dbpath both map to database.db_path."""
        d1 = {"__database": "/path/a.db"}
        d2 = {"_dbpath": "/path/b.db"}
        assert AppConfig.from_dict(d1).database.db_path == "/path/a.db"
        assert AppConfig.from_dict(d2).database.db_path == "/path/b.db"

    def test_descriptions_not_empty(self):
        assert len(FIELD_DESCRIPTIONS) > 10
        for key, desc in FIELD_DESCRIPTIONS.items():
            assert isinstance(desc, str)
            assert len(desc) > 5

    def test_large_extra_dict_preserved(self):
        extras = {f"_custom_{i}": i for i in range(100)}
        d = _legacy_config()
        d.update(extras)
        cfg = AppConfig.from_dict(d)
        assert len(cfg._extra) == 100
        for k, v in extras.items():
            assert cfg._extra[k] == v
