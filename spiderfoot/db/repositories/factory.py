"""
RepositoryFactory — Creates repository instances from configuration.

Provides a centralized place to create ``ScanRepository``,
``EventRepository``, and ``ConfigRepository`` instances backed
by ``SpiderFootDb``.  Includes FastAPI ``Depends`` providers
and a thread-safe singleton.
"""

import logging
import threading
from typing import Any, Dict, Optional

from spiderfoot.db.repositories.scan_repository import ScanRepository
from spiderfoot.db.repositories.event_repository import EventRepository
from spiderfoot.db.repositories.config_repository import ConfigRepository

log = logging.getLogger("spiderfoot.db.repositories.factory")


class RepositoryFactory:
    """Creates repository instances with shared or per-request DB handles.

    Usage::

        factory = RepositoryFactory(config)
        with factory.scan_repo() as repo:
            scans = repo.list_scans()
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Args:
            config: SpiderFoot config dict (passed to ``SpiderFootDb``).
                    When None, ``create_dbh()`` must be called manually.
        """
        self._config = config or {}
        self._lock = threading.Lock()

    def create_dbh(self) -> Any:
        """Create a new ``SpiderFootDb`` handle.

        Returns:
            A fresh ``SpiderFootDb`` instance.

        Raises:
            RuntimeError: When config is not available or DB init fails.
        """
        try:
            from spiderfoot.db import SpiderFootDb
            return SpiderFootDb(self._config)
        except Exception as exc:
            raise RuntimeError(f"Failed to create DB handle: {exc}") from exc

    def scan_repo(self, dbh: Any = None) -> ScanRepository:
        """Create a ``ScanRepository``.

        Args:
            dbh: Optional pre-existing DB handle.  If None, a new one
                 is created.
        """
        if dbh is None:
            dbh = self.create_dbh()
        return ScanRepository(dbh)

    def event_repo(self, dbh: Any = None) -> EventRepository:
        """Create an ``EventRepository``."""
        if dbh is None:
            dbh = self.create_dbh()
        return EventRepository(dbh)

    def config_repo(self, dbh: Any = None) -> ConfigRepository:
        """Create a ``ConfigRepository``."""
        if dbh is None:
            dbh = self.create_dbh()
        return ConfigRepository(dbh)

    def __repr__(self) -> str:
        has_config = bool(self._config)
        return f"<RepositoryFactory config={'yes' if has_config else 'no'}>"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_global_factory: Optional[RepositoryFactory] = None
_global_lock = threading.Lock()


def get_repository_factory() -> Optional[RepositoryFactory]:
    """Return the global ``RepositoryFactory`` (or None)."""
    return _global_factory


def init_repository_factory(
    config: Optional[Dict[str, Any]] = None,
) -> RepositoryFactory:
    """Initialize the global ``RepositoryFactory``.

    Thread-safe; subsequent calls return the same instance.
    """
    global _global_factory
    with _global_lock:
        if _global_factory is None:
            _global_factory = RepositoryFactory(config)
            log.info("RepositoryFactory initialized")
        return _global_factory


def reset_repository_factory() -> None:
    """Reset the global factory (for testing)."""
    global _global_factory
    with _global_lock:
        _global_factory = None
