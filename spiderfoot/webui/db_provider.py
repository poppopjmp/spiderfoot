"""
WebUI Database Provider Mixin — Centralised DB handle creation.

Provides a single ``_get_dbh()`` method that all WebUI endpoint
classes call instead of instantiating ``SpiderFootDb`` directly.

This replaces 78+ scattered ``SpiderFootDb(self.config)`` calls
with a single override point, enabling:

  - Dependency injection for testing
  - API proxy mode for microservice deployment
  - Connection pooling or caching
  - Auditing of DB access patterns

Usage (any WebUI endpoint mixin)::

    class ScanEndpoints(DbProvider):
        def some_method(self):
            dbh = self._get_dbh()
            return dbh.scanInstanceGet(scan_id)

API Proxy Mode:

    When ``SF_WEBUI_API_MODE=true`` is set, ``_get_dbh()`` returns an
    ``ApiClient`` instead of ``SpiderFootDb``.  The ``ApiClient``
    provides the same method signatures, routing all operations through
    the FastAPI REST API.  This enables the WebUI to run in a separate
    container without database access.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

log = logging.getLogger("spiderfoot.webui.db_provider")

# Module-level flag for API proxy mode — evaluated once at import time
_API_MODE = os.environ.get("SF_WEBUI_API_MODE", "").lower() in ("1", "true", "yes")
_API_URL = os.environ.get("SF_WEBUI_API_URL", "http://localhost:8001/api")
_API_KEY = os.environ.get("SF_WEBUI_API_KEY", "")


class DbProvider:
    """Mixin that centralises data access for the WebUI.

    In local mode (default): creates ``SpiderFootDb`` handles.
    In API proxy mode (``SF_WEBUI_API_MODE=true``): returns an
    ``ApiClient`` that proxies all DB calls through the FastAPI API.

    Subclasses (or the final ``WebUiRoutes`` diamond) must have a
    ``self.config`` dict attribute — set by ``WebUiRoutes.__init__``.

    Override ``_get_dbh()`` in tests to inject a fake/mock DB handle.
    """

    # Cached ApiClient singleton (shared across requests in proxy mode)
    _api_client_instance = None

    def _get_dbh(self, config: dict[str, Any] | None = None) -> Any:
        """Create and return a data access handle.

        In local mode: returns a ``SpiderFootDb`` instance.
        In API proxy mode: returns a shared ``ApiClient`` instance.

        Args:
            config: Optional config dict override.  When ``None``
                    (the common case), ``self.config`` is used.

        Returns:
            A data access handle ready for queries.
        """
        if _API_MODE:
            return self._get_api_client()

        from spiderfoot import SpiderFootDb
        return SpiderFootDb(config if config is not None else self.config)

    def _get_api_client(self) -> Any:
        """Get or create a shared ApiClient for proxy mode."""
        if DbProvider._api_client_instance is None:
            from spiderfoot.webui.api_client import ApiClient

            api_url = _API_URL
            api_key = _API_KEY

            # Allow config override if available
            if hasattr(self, "config") and self.config:
                api_url = self.config.get("_apiurl", api_url)
                api_key = self.config.get("_apikey", api_key)

            DbProvider._api_client_instance = ApiClient(
                base_url=api_url,
                api_key=api_key,
            )
            log.info(
                "WebUI API proxy mode enabled — routing DB calls to %s",
                api_url,
            )

        return DbProvider._api_client_instance

    @classmethod
    def reset_api_client(cls) -> None:
        """Reset the cached API client (for testing)."""
        if cls._api_client_instance is not None:
            cls._api_client_instance.close()
            cls._api_client_instance = None
