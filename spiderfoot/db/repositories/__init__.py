"""Database repository package — clean abstraction over SpiderFootDb."""

from __future__ import annotations

from spiderfoot.db.repositories.base import AbstractRepository
from spiderfoot.db.repositories.scan_repository import ScanRepository
from spiderfoot.db.repositories.event_repository import EventRepository
from spiderfoot.db.repositories.config_repository import ConfigRepository
from spiderfoot.db.repositories.factory import (
    RepositoryFactory,
    get_repository_factory,
    init_repository_factory,
    reset_repository_factory,
)

__all__ = [
    "AbstractRepository",
    "ScanRepository",
    "EventRepository",
    "ConfigRepository",
    "RepositoryFactory",
    "get_repository_factory",
    "init_repository_factory",
    "reset_repository_factory",
]
