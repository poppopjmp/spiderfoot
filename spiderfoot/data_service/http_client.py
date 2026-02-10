"""
HTTP-based DataService client for microservice mode.

Communicates with the SpiderFoot API server over HTTP/REST to perform
all data operations. This enables the scanner to run as a separate
process/container from the data layer.

Usage::

    config = DataServiceConfig(
        backend=DataServiceBackend.HTTP,
        api_url="http://data-api:8001/api",
        api_key="<API_KEY>",
    )
    ds = HttpDataService(config)
    scans = ds.scan_instance_list()
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

from spiderfoot.data_service.base import DataService, DataServiceConfig

log = logging.getLogger("spiderfoot.dataservice.http")


class HttpDataService(DataService):
    """DataService backed by HTTP calls to the SpiderFoot API.

    All persistence goes through the FastAPI REST endpoints, allowing
    the scanner to be fully decoupled from the database.
    """

    def __init__(self, config: DataServiceConfig | None = None, **kwargs) -> None:
        """Initialize the HttpDataService."""
        super().__init__(config)
        self._base_url = self.config.api_url.rstrip("/")
        self._api_key = self.config.api_key
        self._timeout = self.config.timeout
        self._max_retries = self.config.max_retries
        self._session = None
        self._service_issuer = None

        # Set up inter-service auth if available
        try:
            from spiderfoot.service_auth import ServiceTokenIssuer
            issuer = ServiceTokenIssuer()
            if issuer.get_token():
                self._service_issuer = issuer
                log.info("HttpDataService: inter-service auth enabled")
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get_session(self):
        """Lazy-init a requests.Session with retry support."""
        if self._session is None:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            retry = Retry(
                total=self._max_retries,
                backoff_factor=0.3,
                status_forcelist=[500, 502, 503, 504],
                allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
            )
            adapter = HTTPAdapter(max_retries=retry)
            session = requests.Session()
            session.mount("http://", adapter)
            session.mount("https://", adapter)

            if self._api_key:
                session.headers["Authorization"] = f"Bearer {self._api_key}"
            elif self._service_issuer:
                # Use inter-service auth tokens
                session.headers.update(self._service_issuer.auth_headers())
            session.headers["Content-Type"] = "application/json"
            session.headers["Accept"] = "application/json"

            self._session = session
        # Propagate request ID for distributed tracing
        try:
            from spiderfoot.request_tracing import get_request_id
            rid = get_request_id()
            if rid:
                self._session.headers["X-Request-ID"] = rid
        except ImportError:
            pass
        return self._session

    def _url(self, path: str) -> str:
        """Build full URL from a relative API path."""
        return f"{self._base_url}/{path.lstrip('/')}"

    def _get(self, path: str, params: dict | None = None) -> Any:
        """HTTP GET returning parsed JSON."""
        session = self._get_session()
        resp = session.get(
            self._url(path), params=params, timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json_data: dict | None = None) -> Any:
        """HTTP POST returning parsed JSON."""
        session = self._get_session()
        resp = session.post(
            self._url(path), json=json_data or {}, timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, json_data: dict | None = None) -> Any:
        """HTTP PUT returning parsed JSON."""
        session = self._get_session()
        resp = session.put(
            self._url(path), json=json_data or {}, timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, json_data: dict | None = None) -> Any:
        """HTTP PATCH returning parsed JSON."""
        session = self._get_session()
        resp = session.patch(
            self._url(path), json=json_data or {}, timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> Any:
        """HTTP DELETE returning parsed JSON."""
        session = self._get_session()
        resp = session.delete(self._url(path), timeout=self._timeout)
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {"success": True}

    # ------------------------------------------------------------------
    # Scan Instance Operations
    # ------------------------------------------------------------------

    def scan_instance_create(
        self, scan_id: str, scan_name: str, target: str
    ) -> bool:
        """Create a new scan instance via HTTP."""
        try:
            self._post(
                "/scans",
                {
                    "scan_id": scan_id,
                    "scan_name": scan_name,
                    "scan_target": target,
                },
            )
            return True
        except Exception as e:
            log.error("Failed to create scan via HTTP: %s", e)
            return False

    def scan_instance_get(self, scan_id: str) -> dict[str, Any] | None:
        """Retrieve a scan instance by ID via HTTP."""
        try:
            data = self._get(f"/scans/{scan_id}")
            return data.get("scan") or data
        except Exception as e:
            log.error("Failed to get scan %s via HTTP: %s", scan_id, e)
            return None

    def scan_instance_list(self) -> list[dict[str, Any]]:
        """List all scan instances via HTTP."""
        try:
            data = self._get("/scans")
            return data.get("scans", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error("Failed to list scans via HTTP: %s", e)
            return []

    def scan_instance_delete(self, scan_id: str) -> bool:
        """Delete a scan instance via HTTP."""
        try:
            self._delete(f"/scans/{scan_id}")
            return True
        except Exception as e:
            log.error("Failed to delete scan %s via HTTP: %s", scan_id, e)
            return False

    def scan_status_set(
        self,
        scan_id: str,
        status: str,
        started: int | None = None,
        ended: int | None = None,
    ) -> bool:
        """Set the status of a scan instance via HTTP."""
        try:
            self._patch(
                f"/scans/{scan_id}/metadata",
                {
                    "status": status,
                    "started": started,
                    "ended": ended,
                },
            )
            return True
        except Exception as e:
            log.error("Failed to set scan status via HTTP: %s", e)
            return False

    # ------------------------------------------------------------------
    # Event Operations
    # ------------------------------------------------------------------

    def event_store(
        self,
        scan_id: str,
        event_hash: str,
        event_type: str,
        module: str,
        data: str,
        source_event_hash: str = "ROOT",
        confidence: int = 100,
        visibility: int = 100,
        risk: int = 0,
    ) -> bool:
        """Store a scan event via HTTP."""
        try:
            self._post(
                f"/scans/{scan_id}/events",
                {
                    "event_hash": event_hash,
                    "event_type": event_type,
                    "module": module,
                    "data": data,
                    "source_event_hash": source_event_hash,
                    "confidence": confidence,
                    "visibility": visibility,
                    "risk": risk,
                },
            )
            return True
        except Exception as e:
            log.debug("Failed to store event via HTTP: %s", e)
            return False

    def event_get_by_scan(
        self,
        scan_id: str,
        event_type: str | None = None,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        """Retrieve events for a scan via HTTP."""
        try:
            params: dict[str, Any] = {}
            if event_type:
                params["event_type"] = event_type
            if limit > 0:
                params["limit"] = limit
            data = self._get(f"/scans/{scan_id}/events", params=params)
            return data.get("events", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error("Failed to get events via HTTP: %s", e)
            return []

    def event_get_unique(
        self,
        scan_id: str,
        event_type: str,
    ) -> list[str]:
        """Retrieve unique event values for a scan via HTTP."""
        try:
            data = self._get(
                f"/scans/{scan_id}/events/unique",
                params={"event_type": event_type},
            )
            return data.get("values", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error("Failed to get unique events via HTTP: %s", e)
            return []

    def event_exists(
        self,
        scan_id: str,
        event_type: str,
        data: str,
    ) -> bool:
        """Check if an event exists for a scan via HTTP."""
        try:
            resp = self._get(
                f"/scans/{scan_id}/events/exists",
                params={"event_type": event_type, "data": data},
            )
            return resp.get("exists", False) if isinstance(resp, dict) else bool(resp)
        except Exception as e:
            return False

    # ------------------------------------------------------------------
    # Log Operations
    # ------------------------------------------------------------------

    def scan_log_event(
        self,
        scan_id: str,
        classification: str,
        message: str,
        component: str | None = None,
    ) -> bool:
        """Log a scan event via HTTP."""
        try:
            self._post(
                f"/scans/{scan_id}/logs",
                {
                    "classification": classification,
                    "message": message,
                    "component": component,
                },
            )
            return True
        except Exception as e:
            log.debug("Failed to log event via HTTP: %s", e)
            return False

    def scan_log_get(
        self,
        scan_id: str,
        limit: int = 0,
        offset: int = 0,
        log_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve scan log entries via HTTP."""
        try:
            params: dict[str, Any] = {}
            if limit > 0:
                params["limit"] = limit
            if offset > 0:
                params["offset"] = offset
            if log_type:
                params["log_type"] = log_type
            data = self._get(f"/scans/{scan_id}/logs", params=params)
            return data.get("logs", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error("Failed to get scan logs via HTTP: %s", e)
            return []

    # ------------------------------------------------------------------
    # Config Operations
    # ------------------------------------------------------------------

    def config_set(
        self, config_data: dict[str, str], scope: str = "GLOBAL"
    ) -> bool:
        """Set configuration values via HTTP."""
        try:
            self._post(
                "/config",
                {"config": config_data, "scope": scope},
            )
            return True
        except Exception as e:
            log.error("Failed to set config via HTTP: %s", e)
            return False

    def config_get(self, scope: str = "GLOBAL") -> dict[str, str]:
        """Retrieve configuration values via HTTP."""
        try:
            data = self._get("/config", params={"scope": scope})
            return data.get("config", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error("Failed to get config via HTTP: %s", e)
            return {}

    def scan_config_set(
        self, scan_id: str, config_data: dict[str, str]
    ) -> bool:
        """Set scan-specific configuration via HTTP."""
        try:
            self._post(
                f"/scans/{scan_id}/config",
                {"config": config_data},
            )
            return True
        except Exception as e:
            log.error("Failed to set scan config via HTTP: %s", e)
            return False

    # ------------------------------------------------------------------
    # Correlation Operations
    # ------------------------------------------------------------------

    def correlation_store(
        self,
        correlation_id: str,
        scan_id: str,
        title: str,
        rule_id: str,
        rule_name: str,
        rule_risk: str,
        rule_descr: str,
        rule_logic: str,
        event_hashes: list[str],
    ) -> bool:
        """Store a correlation result via HTTP."""
        try:
            self._post(
                f"/scans/{scan_id}/correlations",
                {
                    "correlation_id": correlation_id,
                    "title": title,
                    "rule_id": rule_id,
                    "rule_name": rule_name,
                    "rule_risk": rule_risk,
                    "rule_descr": rule_descr,
                    "rule_logic": rule_logic,
                    "event_hashes": event_hashes,
                },
            )
            return True
        except Exception as e:
            log.error("Failed to store correlation via HTTP: %s", e)
            return False

    def correlation_get_by_scan(
        self, scan_id: str
    ) -> list[dict[str, Any]]:
        """Retrieve correlation results for a scan via HTTP."""
        try:
            data = self._get(f"/scans/{scan_id}/correlations")
            return data.get("correlations", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error("Failed to get correlations via HTTP: %s", e)
            return []

    # ------------------------------------------------------------------
    # Aggregate / Summary Operations
    # ------------------------------------------------------------------

    def scan_result_summary(self, scan_id: str) -> dict[str, int]:
        """Retrieve a summary of scan results via HTTP."""
        try:
            data = self._get(f"/scans/{scan_id}/summary")
            return data.get("summary", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error("Failed to get scan summary via HTTP: %s", e)
            return {}

    def event_types_list(self) -> list[dict[str, str]]:
        """List all known event types via HTTP."""
        try:
            data = self._get("/data/entity-types")
            return data.get("entity_types", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error("Failed to list event types via HTTP: %s", e)
            return []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def __del__(self) -> None:
        """Clean up the HTTP session on garbage collection."""
        self.close()

    def __repr__(self) -> str:
        """Return a string representation of the HttpDataService."""
        return f"HttpDataService(url={self._base_url!r})"
