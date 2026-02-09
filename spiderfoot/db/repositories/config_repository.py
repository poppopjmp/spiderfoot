"""
ConfigRepository — Clean interface for global configuration storage.

Wraps ``SpiderFootDb`` config methods: ``configSet``, ``configGet``,
``configClear``.
"""

import logging
from typing import Any, Dict, Optional

from spiderfoot.db.repositories.base import AbstractRepository

log = logging.getLogger("spiderfoot.db.repositories.config")


class ConfigRepository(AbstractRepository):
    """Global/scoped configuration persistence."""

    def set_config(self, config_data: Dict[str, Any]) -> None:
        """Persist configuration dict."""
        self.dbh.configSet(config_data)

    def get_config(self) -> Dict[str, Any]:
        """Retrieve the stored configuration."""
        return self.dbh.configGet() or {}

    def clear_config(self) -> None:
        """Remove all stored configuration."""
        self.dbh.configClear()
