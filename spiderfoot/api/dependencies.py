"""
Dependencies and helpers for SpiderFoot API.

The ``Config`` class wraps the typed ``AppConfig`` (Cycle 13)
internally while exposing a backward-compatible ``get_config()``
that returns a flat dict — so every legacy consumer
(``SpiderFootDb(config.get_config())``, templates, etc.) keeps
working without changes.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from spiderfoot.db import SpiderFootDb
from spiderfoot.sflib.core import SpiderFoot
from spiderfoot.helpers import SpiderFootHelpers
from spiderfoot.app_config import AppConfig
import multiprocessing as mp
import logging
from typing import Any, Dict, List, Optional, Tuple

security = HTTPBearer(auto_error=False)


class Config:
    """API configuration facade backed by typed ``AppConfig``.

    ``get_config()`` returns a flat dict for backward compatibility.
    ``app_config`` property exposes the typed ``AppConfig`` instance.
    ``validate_config()`` delegates to ``AppConfig.validate()`` for
    real validation instead of the former no-op stub.
    """

    def __init__(self, *, _skip_db: bool = False, _app_config: AppConfig | None = None) -> None:
        """Initialise configuration.

        Args:
            _skip_db: If True, skip DB/SF initialisation (for testing).
            _app_config: Inject a pre-built AppConfig (for testing).
        """
        from spiderfoot import __version__

        self.log = logging.getLogger("spiderfoot.api")
        self.loggingQueue = mp.Queue()

        if _app_config is not None:
            self._app_config = _app_config
            if not self._app_config.version:
                self._app_config.version = __version__
            return

        # Build legacy default dict
        default_config: dict[str, Any] = {
            '__modules__': {},
            '__correlationrules__': [],
            '_debug': False,
            '__webaddr': '127.0.0.1',
            '__webport': '8001',
            '__webaddr_apikey': None,
            '__database': f"{SpiderFootHelpers.dataPath()}/spiderfoot.db",
            '__loglevel': 'INFO',
            '__logfile': '',
            '__version__': __version__,
            'scan_defaults': {},
            'workspace_defaults': {},
            'api_keys': [],
            'credentials': []
        }

        if _skip_db:
            self._app_config = AppConfig.from_dict(default_config)
            self._app_config.apply_env_overrides()
            return

        # Normal flow: read from DB, merge, wrap in AppConfig
        self.defaultConfig = default_config.copy()
        dbh = SpiderFootDb(self.defaultConfig, init=True)
        sf = SpiderFoot(self.defaultConfig)
        merged = sf.configUnserialize(dbh.configGet(), self.defaultConfig)

        self._app_config = AppConfig.from_dict(merged)
        self._app_config.apply_env_overrides()

    # ------------------------------------------------------------------
    # Typed access
    # ------------------------------------------------------------------

    @property
    def app_config(self) -> AppConfig:
        """Typed configuration object (preferred for new code)."""
        return self._app_config

    # ------------------------------------------------------------------
    # Backward-compatible flat dict access
    # ------------------------------------------------------------------

    def get_config(self) -> dict[str, Any]:
        """Return the flat dict expected by legacy consumers."""
        return self._app_config.to_dict()

    @property
    def config(self) -> dict[str, Any]:
        """Property alias for ``get_config()`` — some callers access
        ``config.config`` directly."""
        return self.get_config()

    @config.setter
    def config(self, value: dict[str, Any]) -> None:
        """Reassign config from a flat dict (e.g. ``replace_config``)."""
        self._app_config = AppConfig.from_dict(value)

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def update_config(self, updates: dict) -> dict[str, Any]:
        self._app_config.merge(updates)
        return self.get_config()

    def set_config_option(self, key: str, value: Any) -> None:
        self._app_config.merge({key: value})

    def save_config(self) -> None:
        """Persist current config to the database."""
        try:
            flat = self.get_config()
            dbh = SpiderFootDb(flat)
            dbh.configSet(flat)
            self.log.info("Configuration saved to database")
        except Exception as exc:
            self.log.warning("Failed to save config to DB: %s", exc)

    def reload(self) -> None:
        """Re-read config from DB and apply env overrides."""
        try:
            flat = self.get_config()
            dbh = SpiderFootDb(flat)
            sf = SpiderFoot(flat)
            merged = sf.configUnserialize(dbh.configGet(), flat)
            self._app_config = AppConfig.from_dict(merged)
            self._app_config.apply_env_overrides()
            self.log.info("Configuration reloaded from database")
        except Exception as exc:
            self.log.warning("Failed to reload config from DB: %s", exc)

    # ------------------------------------------------------------------
    # Validation (real implementation via AppConfig)
    # ------------------------------------------------------------------

    def validate_config(self, options: dict | None = None) -> tuple[bool, list[dict[str, Any]]]:
        """Validate config options.

        If *options* is provided, a temporary AppConfig is built from
        the merged state (current + options) and validated.  Otherwise
        the current config is validated.

        Returns:
            (is_valid, errors) where errors is a list of dicts with
            ``field``, ``message``, and ``value`` keys.
        """
        if options:
            merged = self.get_config()
            merged.update(options)
            tmp = AppConfig.from_dict(merged)
            validation_errors = tmp.validate()
        else:
            validation_errors = self._app_config.validate()

        error_dicts = [
            {"field": e.field, "message": e.message, "value": e.value}
            for e in validation_errors
        ]
        return len(error_dicts) == 0, error_dicts

    # ------------------------------------------------------------------
    # Scan / workspace defaults
    # ------------------------------------------------------------------

    def get_scan_defaults(self) -> dict:
        return self._app_config._extra.get('scan_defaults', {})

    def set_scan_defaults(self, options: dict) -> None:
        self._app_config._extra['scan_defaults'] = options

    def get_workspace_defaults(self) -> dict:
        return self._app_config._extra.get('workspace_defaults', {})

    def set_workspace_defaults(self, options: dict) -> None:
        self._app_config._extra['workspace_defaults'] = options

    # ------------------------------------------------------------------
    # API key management
    # ------------------------------------------------------------------

    def get_api_keys(self) -> list:
        return self._app_config._extra.get('api_keys', [])

    def add_api_key(self, key_data: dict) -> None:
        self._app_config._extra.setdefault('api_keys', []).append(key_data)

    def delete_api_key(self, key_id: str) -> None:
        keys = self._app_config._extra.get('api_keys', [])
        self._app_config._extra['api_keys'] = [
            k for k in keys if k.get('key') != key_id
        ]

    # ------------------------------------------------------------------
    # Credential management
    # ------------------------------------------------------------------

    def get_credentials(self) -> list:
        return self._app_config._extra.get('credentials', [])

    def add_credential(self, cred_data: dict) -> None:
        self._app_config._extra.setdefault('credentials', []).append(cred_data)

    def delete_credential(self, cred_id: str) -> None:
        creds = self._app_config._extra.get('credentials', [])
        self._app_config._extra['credentials'] = [
            c for c in creds if c.get('key') != cred_id
        ]

    # ------------------------------------------------------------------
    # Full replace / import
    # ------------------------------------------------------------------

    def replace_config(self, new_config: dict) -> None:
        """Replace the entire config (e.g. import)."""
        self._app_config = AppConfig.from_dict(new_config)

    # ------------------------------------------------------------------
    # Module config helpers
    # ------------------------------------------------------------------

    def get_module_config(self, module_name: str) -> dict | None:
        modules = self._app_config.modules or {}
        return modules.get(module_name)

    def update_module_config(self, module_name: str, new_config: dict) -> None:
        modules = self._app_config.modules or {}
        if module_name not in modules:
            raise KeyError("404: Module not found")
        modules[module_name] = new_config
        self._app_config.modules = modules

    # ------------------------------------------------------------------
    # Misc stubs kept for interface compatibility
    # ------------------------------------------------------------------

    def scanResultDelete(self, scan_id: str) -> None:
        """Stub for test/compat."""
        pass

    # ------------------------------------------------------------------
    # Summary / introspection
    # ------------------------------------------------------------------

    def config_summary(self) -> dict[str, Any]:
        """Return a concise typed config summary."""
        return self._app_config.summary()


app_config = None


def get_app_config() -> Config:
    global app_config
    if app_config is None:
        app_config = Config()
    return app_config


def reset_app_config() -> None:
    """Reset the singleton — for testing."""
    global app_config
    app_config = None


async def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        return None
    config = get_app_config()
    api_key = config.get_config().get('__webaddr_apikey')
    if api_key and credentials.credentials != api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return credentials.credentials


async def optional_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        return None
    return await get_api_key(credentials)


# ------------------------------------------------------------------
# Repository Depends providers  (Cycle 23)
# ------------------------------------------------------------------

def get_scan_repository():
    """FastAPI ``Depends`` provider for ``ScanRepository``.

    Creates a fresh DB handle per request and yields a repository.
    The handle is closed when the request completes.
    """
    from spiderfoot.db.repositories import (
        get_repository_factory,
        RepositoryFactory,
    )
    factory = get_repository_factory()
    if factory is None:
        config = get_app_config().get_config()
        factory = RepositoryFactory(config)
    repo = factory.scan_repo()
    try:
        yield repo
    finally:
        repo.close()


def get_event_repository():
    """FastAPI ``Depends`` provider for ``EventRepository``."""
    from spiderfoot.db.repositories import (
        get_repository_factory,
        RepositoryFactory,
    )
    factory = get_repository_factory()
    if factory is None:
        config = get_app_config().get_config()
        factory = RepositoryFactory(config)
    repo = factory.event_repo()
    try:
        yield repo
    finally:
        repo.close()


def get_config_repository():
    """FastAPI ``Depends`` provider for ``ConfigRepository``."""
    from spiderfoot.db.repositories import (
        get_repository_factory,
        RepositoryFactory,
    )
    factory = get_repository_factory()
    if factory is None:
        config = get_app_config().get_config()
        factory = RepositoryFactory(config)
    repo = factory.config_repo()
    try:
        yield repo
    finally:
        repo.close()


# ------------------------------------------------------------------
# Correlation Service provider  (Cycle 26)
# ------------------------------------------------------------------

def get_correlation_svc():
    """FastAPI ``Depends`` provider for ``CorrelationService``.

    Returns the module-level singleton.  The service is lazily
    created from the current app config if it doesn't exist yet.
    """
    from spiderfoot.correlation_service import (
        get_correlation_service as _get_svc,
    )
    config = get_app_config().get_config()
    return _get_svc(config)


# ------------------------------------------------------------------
# Scan Service provider  (Cycle 27)
# ------------------------------------------------------------------

def get_scan_service():
    """FastAPI ``Depends`` provider for ``ScanService``.

    Creates a fresh DB handle via the repository factory, wraps it in
    a ``ScanService``, and tears down on request completion.
    """
    from spiderfoot.db.repositories import (
        get_repository_factory,
        RepositoryFactory,
    )
    from spiderfoot.scan_service_facade import ScanService

    factory = get_repository_factory()
    if factory is None:
        config = get_app_config().get_config()
        factory = RepositoryFactory(config)

    repo = factory.scan_repo()
    svc = ScanService(repo, dbh=repo._dbh)
    try:
        yield svc
    finally:
        svc.close()


# ------------------------------------------------------------------
# Visualization Service provider  (Cycle 28)
# ------------------------------------------------------------------

def get_visualization_service():
    """FastAPI ``Depends`` provider for ``VisualizationService``.

    Composes ``ScanRepository`` (for existence checks) and a raw
    ``dbh`` (for result queries not yet on the repository) into a
    single service with automatic cleanup.
    """
    from spiderfoot.db.repositories import (
        get_repository_factory,
        RepositoryFactory,
    )
    from spiderfoot.visualization_service import VisualizationService

    factory = get_repository_factory()
    if factory is None:
        config = get_app_config().get_config()
        factory = RepositoryFactory(config)

    scan_repo = factory.scan_repo()
    svc = VisualizationService(scan_repo=scan_repo, dbh=scan_repo._dbh)
    try:
        yield svc
    finally:
        svc.close()
