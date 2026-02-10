"""
AbstractRepository — Base class for database repository pattern.

Provides a context-manager protocol and common interface that all
concrete repositories inherit.  Repositories wrap ``SpiderFootDb``
internals without exposing raw SQL, locking, or connection details.
"""
from __future__ import annotations

import logging
import sqlite3
import types
from abc import ABC, abstractmethod
from typing import Any

log = logging.getLogger("spiderfoot.db.repositories")


class AbstractRepository(ABC):
    """Base repository with context-manager lifecycle.

    Usage::

        with ScanRepository(dbh) as repo:
            scans = repo.list_scans()
    """

    def __init__(self, dbh: Any = None) -> None:
        """
        Args:
            dbh: A ``SpiderFootDb`` instance (or compatible object).
                 When None, operations will raise ``RuntimeError``.
        """
        self._dbh = dbh

    @property
    def dbh(self) -> Any:
        """The underlying database handle."""
        if self._dbh is None:
            raise RuntimeError(
                f"{type(self).__name__} has no database handle — "
                "ensure a SpiderFootDb was provided"
            )
        return self._dbh

    @property
    def is_connected(self) -> bool:
        """Whether the underlying DB handle is available."""
        return self._dbh is not None

    def __enter__(self) -> AbstractRepository:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> bool:
        self.close()
        return False

    def close(self) -> None:
        """Close the underlying database connection.

        Safe to call multiple times; no-op if already closed.
        """
        if self._dbh is not None:
            try:
                self._dbh.close()
            except (sqlite3.Error, OSError):
                pass
            self._dbh = None

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return f"<{type(self).__name__} {status}>"
