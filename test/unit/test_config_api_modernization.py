"""
Tests for Cycle 20 — Config API Modernization.

Validates that the ``Config`` class in ``dependencies.py`` properly
wraps ``AppConfig`` and that the config router endpoints use real
validation, Pydantic models, and structured responses.
"""
from __future__ import annotations

import asyncio
import json
import logging
from unittest.mock import patch, MagicMock, PropertyMock
import pytest

from spiderfoot.config.app_config import AppConfig, ValidationError as AppValidationError


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _make_config(extra=None, modules=None):
    """Build a Config instance without touching DB."""
    from spiderfoot.api.dependencies import Config
    base = {
        '__modules__': modules or {},
        '__correlationrules__': [],
        '_debug': False,
        '__webaddr': '127.0.0.1',
        '__webport': '8001',
        '__webaddr_apikey': None,
        '__loglevel': 'INFO',
        '__logfile': '',
        '__version__': '5.23.9-test',
        'scan_defaults': {'scope': 'full'},
        'workspace_defaults': {'theme': 'dark'},
        'api_keys': [{'key': 'k1', 'name': 'test'}],
        'credentials': [{'key': 'c1', 'service': 'github'}],
    }
    if extra:
        base.update(extra)
    return Config(_skip_db=True, _app_config=AppConfig.from_dict(base))


def _make_test_client(config_instance):
    """Build a FastAPI TestClient with the config injected."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from spiderfoot.api.routers import config as config_router
    from spiderfoot.api import dependencies as deps

    app = FastAPI()
    app.include_router(config_router.router, prefix="/api")

    original = deps.app_config
    deps.app_config = config_instance
    try:
        client = TestClient(app)
    finally:
        pass  # keep it set for the duration of tests
    return client, deps


# =====================================================================
# Config class unit tests
# =====================================================================

class TestConfigWrapsAppConfig:
    """Config class wraps AppConfig correctly."""

    def test_app_config_property(self):
        cfg = _make_config()
        assert isinstance(cfg.app_config, AppConfig)

    def test_get_config_returns_dict(self):
        cfg = _make_config()
        flat = cfg.get_config()
        assert isinstance(flat, dict)

    def test_config_property_alias(self):
        cfg = _make_config()
        assert cfg.config == cfg.get_config()

    def test_version_preserved(self):
        cfg = _make_config()
        assert cfg.app_config.version == '5.23.9-test'
        flat = cfg.get_config()
        assert flat.get('__version__') == '5.23.9-test'

    def test_modules_preserved(self):
        mods = {'sfp_test': {'descr': 'Test module', 'cats': ['Test']}}
        cfg = _make_config(modules=mods)
        assert cfg.app_config.modules == mods
        assert cfg.get_config()['__modules__'] == mods

    def test_debug_flag_round_trip(self):
        cfg = _make_config({'_debug': True})
        assert cfg.app_config.core.debug is True
        assert cfg.get_config()['_debug'] is True

    def test_extra_keys_preserved(self):
        cfg = _make_config({'scan_defaults': {'scope': 'full'}})
        assert cfg.get_scan_defaults() == {'scope': 'full'}

    def test_set_config_option(self):
        cfg = _make_config()
        cfg.set_config_option('_debug', True)
        assert cfg.app_config.core.debug is True

    def test_update_config(self):
        cfg = _make_config()
        result = cfg.update_config({'_debug': True, '_maxthreads': 10})
        assert cfg.app_config.core.debug is True
        assert cfg.app_config.core.max_threads == 10
        assert isinstance(result, dict)

    def test_replace_config(self):
        cfg = _make_config()
        new_data = {
            '_debug': True,
            '__version__': '99.0.0',
            '__modules__': {'sfp_new': {}},
        }
        cfg.replace_config(new_data)
        assert cfg.app_config.core.debug is True
        assert cfg.app_config.version == '99.0.0'
        assert cfg.app_config.modules == {'sfp_new': {}}

    def test_config_setter(self):
        cfg = _make_config()
        cfg.config = {'_debug': True, '__version__': '1.0.0'}
        assert cfg.app_config.core.debug is True


# =====================================================================
# Validation tests
# =====================================================================

class TestConfigValidation:
    """validate_config delegates to AppConfig.validate()."""

    def test_valid_config(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config()
        assert is_valid is True
        assert errors == []

    def test_invalid_max_threads(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config({'_maxthreads': 0})
        assert is_valid is False
        assert any(e['field'] == '_maxthreads' for e in errors)

    def test_invalid_fetch_timeout(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config({'_fetchtimeout': 0})
        assert is_valid is False
        assert any(e['field'] == '_fetchtimeout' for e in errors)

    def test_invalid_proxy_type(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config({'_socks1type': 'INVALID'})
        assert is_valid is False
        assert any(e['field'] == '_socks1type' for e in errors)

    def test_invalid_port(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config({'_apiport': 99999})
        assert is_valid is False
        assert any(e['field'] == '_apiport' for e in errors)

    def test_invalid_log_level(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config({'__loglevel': 'BANANA'})
        assert is_valid is False
        assert any(e['field'] == '__loglevel' for e in errors)

    def test_invalid_cache_backend(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config({'_cache_backend': 'memcached'})
        assert is_valid is False
        assert any(e['field'] == '_cache_backend' for e in errors)

    def test_invalid_eventbus_backend(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config({'_eventbus_backend': 'kafka'})
        assert is_valid is False
        assert any(e['field'] == '_eventbus_backend' for e in errors)

    def test_invalid_worker_strategy(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config({'_worker_strategy': 'magic'})
        assert is_valid is False
        assert any(e['field'] == '_worker_strategy' for e in errors)

    def test_validation_with_options_dict(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config(
            {'_maxthreads': 5, '_fetchtimeout': 10}
        )
        assert is_valid is True
        assert errors == []

    def test_validation_error_structure(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config({'_maxthreads': -1})
        assert is_valid is False
        err = errors[0]
        assert 'field' in err
        assert 'message' in err
        assert 'value' in err

    def test_multiple_errors(self):
        cfg = _make_config()
        is_valid, errors = cfg.validate_config({
            '_maxthreads': 0,
            '_fetchtimeout': 0,
            '__loglevel': 'BAD',
        })
        assert is_valid is False
        assert len(errors) >= 3


# =====================================================================
# Scan / workspace defaults
# =====================================================================

class TestScanWorkspaceDefaults:

    def test_get_scan_defaults(self):
        cfg = _make_config()
        assert cfg.get_scan_defaults() == {'scope': 'full'}

    def test_set_scan_defaults(self):
        cfg = _make_config()
        cfg.set_scan_defaults({'scope': 'narrow', 'depth': 2})
        assert cfg.get_scan_defaults() == {'scope': 'narrow', 'depth': 2}

    def test_get_workspace_defaults(self):
        cfg = _make_config()
        assert cfg.get_workspace_defaults() == {'theme': 'dark'}

    def test_set_workspace_defaults(self):
        cfg = _make_config()
        cfg.set_workspace_defaults({'theme': 'light'})
        assert cfg.get_workspace_defaults() == {'theme': 'light'}


# =====================================================================
# API key / credential management
# =====================================================================

class TestApiKeyManagement:

    def test_get_api_keys(self):
        cfg = _make_config()
        keys = cfg.get_api_keys()
        assert len(keys) == 1
        assert keys[0]['key'] == 'k1'

    def test_add_api_key(self):
        cfg = _make_config()
        cfg.add_api_key({'key': 'k2', 'name': 'second'})
        assert len(cfg.get_api_keys()) == 2

    def test_delete_api_key(self):
        cfg = _make_config()
        cfg.delete_api_key('k1')
        assert len(cfg.get_api_keys()) == 0

    def test_get_credentials(self):
        cfg = _make_config()
        creds = cfg.get_credentials()
        assert len(creds) == 1
        assert creds[0]['key'] == 'c1'

    def test_add_credential(self):
        cfg = _make_config()
        cfg.add_credential({'key': 'c2', 'service': 'gitlab'})
        assert len(cfg.get_credentials()) == 2

    def test_delete_credential(self):
        cfg = _make_config()
        cfg.delete_credential('c1')
        assert len(cfg.get_credentials()) == 0


# =====================================================================
# Module config
# =====================================================================

class TestModuleConfig:

    def test_get_module_config(self):
        mods = {'sfp_dns': {'descr': 'DNS lookups'}}
        cfg = _make_config(modules=mods)
        assert cfg.get_module_config('sfp_dns') == {'descr': 'DNS lookups'}

    def test_get_module_config_not_found(self):
        cfg = _make_config()
        assert cfg.get_module_config('sfp_nonexistent') is None

    def test_update_module_config(self):
        mods = {'sfp_dns': {'descr': 'DNS lookups'}}
        cfg = _make_config(modules=mods)
        cfg.update_module_config('sfp_dns', {'descr': 'Updated'})
        assert cfg.get_module_config('sfp_dns')['descr'] == 'Updated'

    def test_update_module_config_not_found(self):
        cfg = _make_config()
        with pytest.raises(KeyError, match="404"):
            cfg.update_module_config('sfp_missing', {})


# =====================================================================
# Config summary
# =====================================================================

class TestConfigSummary:

    def test_config_summary(self):
        cfg = _make_config()
        summary = cfg.config_summary()
        assert 'debug' in summary
        assert 'max_threads' in summary
        assert 'web' in summary
        assert 'api' in summary

    def test_config_summary_values(self):
        cfg = _make_config({'_debug': True})
        summary = cfg.config_summary()
        assert summary['debug'] is True


# =====================================================================
# Save / reload (with mocked DB)
# =====================================================================

class TestSaveReload:

    @patch('spiderfoot.api.dependencies.SpiderFootDb')
    def test_save_config_calls_db(self, mock_db_cls):
        cfg = _make_config()
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        cfg.save_config()
        mock_db.configSet.assert_called_once()

    @patch('spiderfoot.api.dependencies.SpiderFootDb')
    def test_save_config_handles_failure(self, mock_db_cls):
        cfg = _make_config()
        mock_db_cls.side_effect = Exception("DB error")
        # Should not raise, just warn
        cfg.save_config()

    @patch('spiderfoot.api.dependencies.SpiderFoot')
    @patch('spiderfoot.api.dependencies.SpiderFootDb')
    def test_reload_reads_db(self, mock_db_cls, mock_sf_cls):
        cfg = _make_config()
        mock_db = MagicMock()
        mock_db.configGet.return_value = {}
        mock_db_cls.return_value = mock_db
        mock_sf = MagicMock()
        mock_sf.configUnserialize.return_value = {'_debug': True, '__version__': '1.0'}
        mock_sf_cls.return_value = mock_sf
        cfg.reload()
        mock_db.configGet.assert_called_once()
        assert cfg.app_config.core.debug is True

    @patch('spiderfoot.api.dependencies.SpiderFootDb')
    def test_reload_handles_failure(self, mock_db_cls):
        cfg = _make_config()
        mock_db_cls.side_effect = Exception("DB error")
        # Should not raise
        cfg.reload()


# =====================================================================
# Env variable overlay
# =====================================================================

class TestEnvOverlay:

    def test_env_override_applied(self):
        from spiderfoot.api.dependencies import Config
        with patch.dict('os.environ', {'SF_DEBUG': 'true', 'SF_MAX_THREADS': '16'}):
            ac = AppConfig.from_dict({
                '__version__': '1.0',
                '__modules__': {},
            })
            ac.apply_env_overrides()
            assert ac.core.debug is True
            assert ac.core.max_threads == 16


# =====================================================================
# reset_app_config
# =====================================================================

class TestResetAppConfig:

    def test_reset_clears_singleton(self):
        from spiderfoot.api import dependencies as deps
        deps.app_config = _make_config()
        assert deps.app_config is not None
        deps.reset_app_config()
        assert deps.app_config is None


# =====================================================================
# API endpoint integration tests (via TestClient)
# =====================================================================

class TestConfigEndpoints:

    def setup_method(self):
        self.cfg = _make_config(modules={
            'sfp_dns': {'descr': 'DNS lookups', 'cats': ['Footprint'], 'labels': [], 'deps': [], 'provides': [], 'consumes': [], 'group': []},
        })
        self.client, self.deps = _make_test_client(self.cfg)

    def teardown_method(self):
        self.deps.app_config = None

    def test_get_config(self):
        resp = self.client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert 'summary' in data
        assert 'config' in data
        assert 'version' in data

    def test_get_config_no_dunder_keys(self):
        resp = self.client.get("/api/config")
        data = resp.json()
        config = data['config']
        for key in config:
            if key.startswith('__'):
                assert key in ('__version__', '__database')

    def test_patch_config_valid(self):
        resp = self.client.patch(
            "/api/config",
            json={"options": {"_debug": True}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True

    def test_patch_config_invalid(self):
        resp = self.client.patch(
            "/api/config",
            json={"options": {"_maxthreads": -5}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is False
        assert len(data['errors']) > 0

    def test_validate_config_valid(self):
        resp = self.client.post(
            "/api/config/validate",
            json={"options": {"_maxthreads": 5}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['valid'] is True
        assert data['sections_checked'] == 11

    def test_validate_config_invalid(self):
        resp = self.client.post(
            "/api/config/validate",
            json={"options": {"_maxthreads": 0, "_fetchtimeout": 0}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['valid'] is False
        assert len(data['errors']) >= 2
        err = data['errors'][0]
        assert 'field' in err
        assert 'message' in err

    def test_get_modules(self):
        resp = self.client.get("/api/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert 'modules' in data
        assert len(data['modules']) == 1
        assert data['modules'][0]['name'] == 'sfp_dns'

    def test_get_scan_defaults(self):
        resp = self.client.get("/api/config/scan-defaults")
        assert resp.status_code == 200
        assert resp.json()['scan_defaults'] == {'scope': 'full'}

    def test_get_workspace_defaults(self):
        resp = self.client.get("/api/config/workspace-defaults")
        assert resp.status_code == 200
        assert resp.json()['workspace_defaults'] == {'theme': 'dark'}

    def test_get_api_keys(self):
        resp = self.client.get("/api/config/api-keys")
        assert resp.status_code == 200
        assert len(resp.json()['api_keys']) == 1

    def test_get_credentials(self):
        resp = self.client.get("/api/config/credentials")
        assert resp.status_code == 200
        assert len(resp.json()['credentials']) == 1

    @patch('spiderfoot.api.dependencies.SpiderFootDb')
    @patch('spiderfoot.api.dependencies.SpiderFoot')
    def test_reload_endpoint(self, mock_sf_cls, mock_db_cls):
        mock_db = MagicMock()
        mock_db.configGet.return_value = {}
        mock_db_cls.return_value = mock_db
        mock_sf = MagicMock()
        mock_sf.configUnserialize.return_value = {'__version__': '1.0'}
        mock_sf_cls.return_value = mock_sf
        resp = self.client.post("/api/config/reload")
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'reloaded'
        assert 'summary' in data

    def test_export_config(self):
        resp = self.client.get("/api/config/export")
        assert resp.status_code == 200
        data = resp.json()
        assert '__modules__' in data

    @patch('spiderfoot.api.dependencies.SpiderFootDb')
    def test_import_config(self, mock_db_cls):
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        resp = self.client.post(
            "/api/config/import",
            json={"config": {"_debug": True, "__version__": "99.0", "__modules__": {}}},
        )
        assert resp.status_code == 200
        assert resp.json()['success'] is True

    def test_get_config_summary_endpoint(self):
        resp = self.client.get("/api/config/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert 'sections' in data
        assert 'core' in data['sections']
        assert 'network' in data['sections']
        assert 'database' in data['sections']
        assert 'web' in data['sections']
        assert 'api' in data['sections']
        assert 'cache' in data['sections']
        assert 'eventbus' in data['sections']
        assert 'vector' in data['sections']
        assert 'worker' in data['sections']
        assert 'redis' in data['sections']
        assert 'elasticsearch' in data['sections']
        assert data['version'] == '5.23.9-test'


# =====================================================================
# Backward compatibility
# =====================================================================

class TestBackwardCompatibility:
    """Ensure old-style access patterns still work."""

    def test_config_dict_key_access(self):
        cfg = _make_config({'_debug': True})
        flat = cfg.get_config()
        assert flat['_debug'] is True

    def test_modules_in_flat_dict(self):
        mods = {'sfp_test': {'descr': 'Test'}}
        cfg = _make_config(modules=mods)
        flat = cfg.get_config()
        assert flat['__modules__'] == mods

    def test_global_opt_descs(self):
        """Legacy consumers expect __globaloptdescs__ in flat dict."""
        cfg = _make_config()
        flat = cfg.get_config()
        assert '__globaloptdescs__' in flat

    def test_round_trip(self):
        """from_dict -> to_dict -> from_dict preserves everything."""
        original = {
            '_debug': True,
            '_maxthreads': 8,
            '_fetchtimeout': 30,
            '__version__': '1.0.0',
            '__modules__': {'sfp_x': {'a': 1}},
            '__correlationrules__': [{'name': 'r1'}],
            'custom_key': 'custom_value',
        }
        ac1 = AppConfig.from_dict(original)
        flat = ac1.to_dict()
        ac2 = AppConfig.from_dict(flat)

        assert ac2.core.debug is True
        assert ac2.core.max_threads == 8
        assert ac2.network.fetch_timeout == 30
        assert ac2.version == '1.0.0'
        assert ac2.modules == {'sfp_x': {'a': 1}}
        assert ac2.correlation_rules == [{'name': 'r1'}]
        assert ac2._extra.get('custom_key') == 'custom_value'

    def test_scan_result_delete_stub(self):
        cfg = _make_config()
        cfg.scanResultDelete("test-scan-id")  # should not raise
