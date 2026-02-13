"""
API Client for WebUI → FastAPI API proxy layer.

Replaces direct database access (``_get_dbh()``) in the CherryPy
WebUI with HTTP calls to the FastAPI API server.  This enables
the WebUI to run as a separate process/container from the data layer.

The client provides the same method signatures as SpiderFootDb so
it can be used as a drop-in replacement via the ``_get_dbh()`` factory.

Usage::

    from spiderfoot.webui.api_client import ApiClient

    client = ApiClient(base_url="http://api:8001/api")
    scans = client.scanInstanceList()
    scan = client.scanInstanceGet("abc123")
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger("spiderfoot.webui.api_client")


class ApiClient:
    """HTTP client that mimics SpiderFootDb interface for WebUI endpoints.

    Provides backward-compatible method names (``scanInstanceGet``,
    ``scanInstanceList``, etc.) that delegate to the FastAPI REST API
    instead of direct database queries.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8001/api",
        api_key: str = "",
        timeout: float = 30.0,
    ) -> None:
        """Initialize the ApiClient."""
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._session = None
        self._service_issuer = None

        # Set up inter-service auth if available
        try:
            from spiderfoot.security.service_auth import ServiceTokenIssuer
            issuer = ServiceTokenIssuer()
            if issuer.get_token():
                self._service_issuer = issuer
                log.info("ApiClient: inter-service auth enabled")
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get_session(self):
        if self._session is None:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            retry = Retry(
                total=3,
                backoff_factor=0.2,
                status_forcelist=[502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry)
            session = requests.Session()
            session.mount("http://", adapter)
            session.mount("https://", adapter)

            if self._api_key:
                session.headers["Authorization"] = f"Bearer {self._api_key}"
            elif self._service_issuer:
                session.headers.update(self._service_issuer.auth_headers())
            session.headers["Accept"] = "application/json"

            self._session = session
        return self._session

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    def _get(self, path: str, params: dict | None = None) -> Any:
        session = self._get_session()
        resp = session.get(self._url(path), params=params, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json_data: dict | None = None) -> Any:
        session = self._get_session()
        resp = session.post(
            self._url(path), json=json_data or {}, timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> Any:
        session = self._get_session()
        resp = session.delete(self._url(path), timeout=self._timeout)
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {"success": True}

    def _put(self, path: str, json_data: dict | None = None) -> Any:
        session = self._get_session()
        resp = session.put(
            self._url(path), json=json_data or {}, timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, json_data: dict | None = None) -> Any:
        session = self._get_session()
        resp = session.patch(
            self._url(path), json=json_data or {}, timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Scan instance methods (SpiderFootDb compatibility)
    # ------------------------------------------------------------------

    def scanInstanceGet(self, scan_id: str) -> tuple | None:
        """Get scan instance as legacy tuple format.

        Returns: (name, target, created, started, ended, status) or None
        Matches SpiderFootDb.scanInstanceGet which unwraps fetchall()[0].
        """
        try:
            data = self._get(f"/scans/{scan_id}")
            scan = data.get("scan", data)
            if not scan:
                return None
            return (
                scan.get("name", ""),
                scan.get("target", ""),
                scan.get("created", 0),
                scan.get("started", 0),
                scan.get("ended", 0),
                scan.get("status", ""),
            )
        except Exception as e:
            log.error("API scanInstanceGet failed: %s", e)
            return None

    def scanInstanceList(self) -> list:
        """List all scans in legacy tuple format."""
        try:
            data = self._get("/scans")
            # API returns {"items": [...], "total": ...} or {"scans": [...]} or a plain list
            if isinstance(data, dict):
                scans = data.get("items", data.get("scans", data))
            else:
                scans = data
            return [
                (
                    s.get("scan_id", s.get("id", "")),
                    s.get("name", ""),
                    s.get("target", ""),
                    s.get("created", 0),
                    s.get("started", 0),
                    s.get("ended", 0),
                    s.get("status", ""),
                    s.get("result_count", 0),
                )
                for s in (scans if isinstance(scans, list) else [])
            ]
        except Exception as e:
            log.error("API scanInstanceList failed: %s", e)
            return []

    def scanInstanceDelete(self, scan_id: str) -> None:
        """Delete a scan."""
        try:
            self._delete(f"/scans/{scan_id}")
        except Exception as e:
            log.error("API scanInstanceDelete failed: %s", e)

    def scanInstanceSet(
        self, scan_id: str, started: int | None = None, ended: int | None = None, status: str | None = None
    ) -> None:
        """Update scan metadata."""
        try:
            payload: dict[str, Any] = {}
            if status:
                payload["status"] = status
            if started:
                payload["started"] = int(started)
            if ended:
                payload["ended"] = int(ended)
            self._patch(f"/scans/{scan_id}/metadata", payload)
        except Exception as e:
            log.error("API scanInstanceSet failed: %s", e)

    # ------------------------------------------------------------------
    # Scan config
    # ------------------------------------------------------------------

    def scanConfigGet(self, scan_id: str) -> dict[str, str]:
        """Get scan configuration."""
        try:
            data = self._get(f"/scans/{scan_id}/options")
            return data.get("config", {})
        except Exception as e:
            log.error("API scanConfigGet failed: %s", e)
            return {}

    def configGet(self) -> dict[str, str]:
        """Get global configuration."""
        try:
            data = self._get("/config")
            return data.get("config", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error("API configGet failed: %s", e)
            return {}

    def configSet(self, optMap: dict | None = None) -> None:
        """Set global configuration via PUT /config."""
        if optMap is None:
            return
        try:
            self._put("/config", optMap)
        except Exception as e:
            log.error("API configSet failed: %s", e)

    # ------------------------------------------------------------------
    # Scan results/events
    # ------------------------------------------------------------------

    def scanResultEvent(
        self, scan_id: str, eventType: str = "ALL",
        filterfp: str | bool = False, correlationId: str | None = None,
        **kwargs,
    ) -> list:
        """Get scan results in legacy tuple format."""
        try:
            params: dict[str, Any] = {}
            if eventType and eventType != "ALL":
                params["event_type"] = eventType
            data = self._get(f"/scans/{scan_id}/events", params=params)
            events = data.get("events", data) if isinstance(data, dict) else data
            return [
                (
                    e.get("generated", 0),
                    e.get("data", ""),
                    e.get("module", ""),
                    e.get("hash", ""),
                    e.get("type", ""),
                    e.get("source_event_hash", "ROOT"),
                    e.get("confidence", 100),
                    e.get("visibility", 100),
                    e.get("risk", 0),
                )
                for e in (events if isinstance(events, list) else [])
            ]
        except Exception as e:
            log.error("API scanResultEvent failed: %s", e)
            return []

    def scanResultSummary(self, scan_id: str, by: str = "type") -> list:
        """Get scan result summary."""
        try:
            data = self._get(f"/scans/{scan_id}/summary", params={"by": by})
            # Prefer 'details' which has full tuple data, fall back to 'summary' dict
            details = data.get("details", []) if isinstance(data, dict) else []
            if details:
                return [
                    (d.get("key", ""), d.get("description", ""), d.get("last_in", 0),
                     d.get("total", 0), d.get("unique_total", 0))
                    for d in details
                ]
            summary = data.get("summary", data) if isinstance(data, dict) else data
            if isinstance(summary, dict):
                return [(k, "", 0, v, 0) for k, v in summary.items()]
            return summary if isinstance(summary, list) else []
        except Exception as e:
            log.error("API scanResultSummary failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Scan events/search
    # ------------------------------------------------------------------

    def search(self, criteria: dict[str, str]) -> list:
        """Search scan results."""
        try:
            scan_id = criteria.get("scan_id", "")
            data = self._get(
                f"/scans/{scan_id}/search" if scan_id else "/search",
                params=criteria,
            )
            return data.get("results", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error("API search failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Scan logs
    # ------------------------------------------------------------------

    def scanLogs(self, scan_id: str, limit: int | None = None, fromRowId: int = 0, reverse: bool = False) -> list:
        """Get scan logs in legacy tuple format."""
        try:
            params: dict[str, Any] = {}
            if limit:
                params["limit"] = limit
            if fromRowId:
                params["offset"] = fromRowId
            data = self._get(f"/scans/{scan_id}/logs", params=params)
            logs = data.get("logs", data) if isinstance(data, dict) else data
            rows = [
                (
                    l.get("generated", 0),
                    l.get("component", ""),
                    l.get("type", ""),
                    l.get("message", ""),
                    l.get("rowid", 0),
                )
                for l in (logs if isinstance(logs, list) else [])
            ]
            if reverse:
                rows.reverse()
            return rows
        except Exception as e:
            log.error("API scanLogs failed: %s", e)
            return []

    def scanErrors(self, scan_id: str, limit: int = 0) -> list:
        """Get scan error log entries."""
        try:
            params: dict[str, Any] = {"type": "ERROR"}
            if limit:
                params["limit"] = limit
            data = self._get(f"/scans/{scan_id}/logs", params=params)
            logs = data.get("logs", data) if isinstance(data, dict) else data
            # Filter to only ERROR type and return in legacy tuple format (generated, component, message)
            errors = []
            for l in (logs if isinstance(logs, list) else []):
                if isinstance(l, dict) and l.get("type", "") == "ERROR":
                    errors.append((l.get("generated", 0), l.get("component", ""), l.get("message", "")))
                elif isinstance(l, (list, tuple)):
                    errors.append(l)
            return errors
        except Exception as e:
            log.error("API scanErrors failed: %s", e)
            return []

    def scanLogEvent(
        self, scan_id: str, classification: str, message: str, component: str | None = None
    ) -> None:
        """Log a scan event."""
        try:
            self._post(
                f"/scans/{scan_id}/logs",
                {
                    "classification": classification,
                    "message": message,
                    "component": component,
                },
            )
        except Exception as e:
            log.debug("API scanLogEvent failed: %s", e)

    # ------------------------------------------------------------------
    # Correlations
    # ------------------------------------------------------------------

    def scanCorrelations(self, scan_id: str) -> list:
        """Get scan correlations."""
        try:
            data = self._get(f"/scans/{scan_id}/correlations")
            return data.get("correlations", data) if isinstance(data, dict) else data
        except Exception as e:
            log.error("API scanCorrelations failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # False positives
    # ------------------------------------------------------------------

    def scanResultsUpdateFP(
        self, scan_id: str, result_ids: list, fp: str
    ) -> bool:
        """Update false positive flags."""
        try:
            data = self._post(
                f"/scans/{scan_id}/results/falsepositive",
                {"result_ids": result_ids, "fp": fp},
            )
            return data.get("status") == "SUCCESS"
        except Exception as e:
            log.error("API scanResultsUpdateFP failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Scan stop
    # ------------------------------------------------------------------

    def scan_stop(self, scan_id: str) -> dict[str, Any]:
        """Stop / abort a running scan."""
        try:
            return self._post(f"/scans/{scan_id}/stop")
        except Exception as e:
            log.error("API scan_stop failed: %s", e)
            return {"status": "ERROR", "message": str(e)}

    # ------------------------------------------------------------------
    # Event types / modules
    # ------------------------------------------------------------------

    def eventTypes(self) -> list:
        """List event types."""
        try:
            data = self._get("/data/entity-types")
            types = data.get("entity_types", data) if isinstance(data, dict) else data
            return types if isinstance(types, list) else []
        except Exception as e:
            log.error("API eventTypes failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Result delete
    # ------------------------------------------------------------------

    def scanResultDelete(self, scan_id: str) -> None:
        """Clear scan results."""
        try:
            self._post(f"/scans/{scan_id}/clear")
        except Exception as e:
            log.error("API scanResultDelete failed: %s", e)

    # ------------------------------------------------------------------
    # Scan control
    # ------------------------------------------------------------------

    def startScan(
        self,
        scan_name: str,
        target: str,
        modules: list[str] | None = None,
        type_filter: list[str] | None = None,
    ) -> dict:
        """Start a new scan via the API.

        Returns: {"id": scan_id, "name": ..., "status": ...} or raises.
        """
        payload: dict[str, Any] = {
            "name": scan_name,
            "target": target,
        }
        if modules:
            payload["modules"] = modules
        if type_filter:
            payload["type_filter"] = type_filter
        return self._post("/scans", payload)

    def scanInstanceStop(self, scan_id: str) -> None:
        """Stop / abort a running scan."""
        try:
            self._post(f"/scans/{scan_id}/stop")
        except Exception as e:
            log.error("API scanInstanceStop failed: %s", e)

    # ------------------------------------------------------------------
    # Correlation summaries
    # ------------------------------------------------------------------

    def scanCorrelationSummary(self, scan_id: str, by: str = "risk") -> list:
        """Get scan correlation summary."""
        try:
            data = self._get(f"/scans/{scan_id}/correlations/summary", params={"by": by})
            summary = data.get("summary", data) if isinstance(data, dict) else data
            if not isinstance(summary, list):
                return []
            # Convert dicts to tuples matching DB format
            result = []
            for item in summary:
                if isinstance(item, dict):
                    if by == "risk":
                        result.append((item.get("risk", ""), item.get("total", 0)))
                    else:
                        result.append((
                            item.get("rule_id", ""),
                            item.get("rule_name", ""),
                            item.get("risk", ""),
                            item.get("description", ""),
                            item.get("total", 0),
                        ))
                else:
                    result.append(item)
            return result
        except Exception as e:
            log.debug("API scanCorrelationSummary failed: %s", e)
            return []

    def scanCorrelationList(self, scan_id: str) -> list:
        """Get scan correlation list in legacy tuple format."""
        try:
            data = self._get(f"/scans/{scan_id}/correlations")
            correlations = data.get("correlations", data) if isinstance(data, dict) else data
            if not isinstance(correlations, list):
                return []
            # Convert dicts to tuples matching DB column order:
            # (id, title, rule_id, rule_risk, rule_name, rule_descr, rule_logic, event_count)
            result = []
            for item in correlations:
                if isinstance(item, dict):
                    result.append((
                        item.get("id", ""),
                        item.get("title", ""),
                        item.get("rule_id", ""),
                        item.get("rule_risk", ""),
                        item.get("rule_name", ""),
                        item.get("rule_descr", ""),
                        item.get("rule_logic", ""),
                        item.get("event_count", 0),
                    ))
                else:
                    result.append(item)
            return result
        except Exception as e:
            log.debug("API scanCorrelationList failed: %s", e)
            return []

    def runCorrelations(self, scan_id: str) -> dict:
        """Trigger correlation rule execution for a scan."""
        try:
            data = self._post(f"/scans/{scan_id}/correlations/run")
            return data if isinstance(data, dict) else {"results": 0}
        except Exception as e:
            log.error("API runCorrelations failed: %s", e)
            return {"error": str(e)}

    def scanResultHistory(self, scan_id: str) -> list:
        """Get scan result history in legacy tuple format."""
        try:
            data = self._get(f"/scans/{scan_id}/history")
            history = data.get("history", data) if isinstance(data, dict) else data
            if not isinstance(history, list):
                return []
            # Convert dicts to tuples matching DB column order: (hourmin, type, count)
            result = []
            for item in history:
                if isinstance(item, dict):
                    result.append((
                        item.get("hourmin", ""),
                        item.get("type", ""),
                        item.get("count", 0),
                    ))
                else:
                    result.append(item)
            return result
        except Exception as e:
            log.debug("API scanResultHistory failed: %s", e)
            return []

    def scanResultEventUnique(self, scan_id: str, eventType: str, filterfp: str | bool = False) -> list:
        """Get unique scan result events in legacy tuple format."""
        try:
            params: dict[str, Any] = {"event_type": eventType}
            if filterfp:
                params["filterfp"] = filterfp
            data = self._get(f"/scans/{scan_id}/events/unique", params=params)
            events = data.get("events", data) if isinstance(data, dict) else data
            if not isinstance(events, list):
                return []
            # Convert dicts to tuples matching DB column order: (data, type, count)
            result = []
            for item in events:
                if isinstance(item, dict):
                    result.append((
                        item.get("data", ""),
                        item.get("type", ""),
                        item.get("count", 0),
                    ))
                else:
                    result.append(item)
            return result
        except Exception as e:
            log.debug("API scanResultEventUnique failed: %s", e)
            return []

    def configClear(self) -> None:
        """Clear / reset global configuration."""
        try:
            self._post("/config/reload")
        except Exception as e:
            log.error("API configClear failed: %s", e)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def __repr__(self) -> str:
        """Return a string representation of the API client."""
        return f"ApiClient(url={self._base_url!r})"
