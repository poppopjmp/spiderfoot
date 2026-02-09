"""
WebUI Database Provider Mixin — Centralised DB handle creation.

Provides a single ``_get_dbh()`` method that all WebUI endpoint
classes call instead of instantiating ``SpiderFootDb`` directly.

This replaces 78+ scattered ``SpiderFootDb(self.config)`` calls
with a single override point, enabling:

  - Dependency injection for testing
  - Future repository/service migration
  - Connection pooling or caching
  - Auditing of DB access patterns

Usage (any WebUI endpoint mixin)::

    class ScanEndpoints(DbProvider):
        def some_method(self):
            dbh = self._get_dbh()
            return dbh.scanInstanceGet(scan_id)
"""

import logging
from typing import Any, Dict, Optional

log = logging.getLogger("spiderfoot.webui.db_provider")


class DbProvider:
    """Mixin that centralises ``SpiderFootDb`` creation for the WebUI.

    Subclasses (or the final ``WebUiRoutes`` diamond) must have a
    ``self.config`` dict attribute — set by ``WebUiRoutes.__init__``.

    Override ``_get_dbh()`` in tests to inject a fake/mock DB handle.
    """

    def _get_dbh(self, config: Optional[Dict[str, Any]] = None) -> Any:
        """Create and return a ``SpiderFootDb`` handle.

        Args:
            config: Optional config dict override.  When ``None``
                    (the common case), ``self.config`` is used.

        Returns:
            A ``SpiderFootDb`` instance ready for queries.
        """
        from spiderfoot import SpiderFootDb
        return SpiderFootDb(config if config is not None else self.config)
