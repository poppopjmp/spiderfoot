"""
Factory for creating DataService instances.

Reads configuration from SpiderFoot settings or environment variables
and returns the appropriate DataService implementation.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from spiderfoot.data_service.base import DataService, DataServiceBackend, DataServiceConfig
from spiderfoot.data_service.local import LocalDataService
from spiderfoot.config.constants import DEFAULT_DATABASE_NAME

log = logging.getLogger("spiderfoot.dataservice.factory")


def create_data_service(
    config: DataServiceConfig | None = None,
    resilient: bool = True,
) -> DataService:
    """Create a DataService instance from explicit config.

    Args:
        config: DataServiceConfig specifying backend and settings
        resilient: If True, wrap remote backends (HTTP/gRPC) with a
            circuit breaker and optional local fallback.

    Returns:
        Configured DataService instance
    """
    if config is None:
        config = DataServiceConfig()

    if config.backend == DataServiceBackend.LOCAL:
        return LocalDataService(config=config, db_opts=config.db_config)

    elif config.backend == DataServiceBackend.HTTP:
        from spiderfoot.data_service.http_client import HttpDataService
        log.info("Using HTTP data service backend: %s", config.api_url)
        primary = HttpDataService(config=config)
        if resilient:
            return _wrap_resilient(primary, config)
        return primary

    elif config.backend == DataServiceBackend.GRPC:
        from spiderfoot.data_service.grpc_client import GrpcDataService
        log.info("Using gRPC data service backend: %s", config.api_url)
        primary = GrpcDataService(config=config)
        if resilient:
            return _wrap_resilient(primary, config)
        return primary

    else:
        raise ValueError(f"Unknown data service backend: {config.backend}")


def _wrap_resilient(primary: DataService, config: DataServiceConfig) -> DataService:
    """Wrap a remote DataService with circuit breaker + local fallback."""
    from spiderfoot.data_service.resilient import ResilientDataService

    fallback = None
    try:
        fallback = LocalDataService(config=config, db_opts=config.db_config)
        log.info("Resilient DataService: primary=%s, fallback=LocalDataService",
                 type(primary).__name__)
    except Exception as e:
        log.warning("Could not create local fallback DataService: %s", e)

    return ResilientDataService(
        primary=primary,
        fallback=fallback,
        failure_threshold=config.max_retries + 2,
        recovery_timeout=config.timeout,
    )


def create_data_service_from_config(sf_config: dict[str, Any]) -> DataService:
    """Create a DataService from SpiderFoot configuration dict.

    Reads _dataservice_* keys from the SpiderFoot config.

    Config keys:
        _dataservice_backend: 'local', 'http', or 'grpc'
        _dataservice_api_url: URL for remote backends
        _dataservice_api_key: Auth key for remote backends
        _dataservice_timeout: Request timeout (seconds)
        __database: Database path/URL (for local backend)
        __dbtype: Database type 'postgresql'

    Args:
        sf_config: SpiderFoot configuration dict

    Returns:
        Configured DataService instance
    """
    backend_str = sf_config.get("_dataservice_backend", "local")

    try:
        backend = DataServiceBackend(backend_str.lower())
    except ValueError:
        log.warning("Unknown backend '%s', defaulting to local", backend_str)
        backend = DataServiceBackend.LOCAL

    config = DataServiceConfig(
        backend=backend,
        api_url=sf_config.get("_dataservice_api_url", "http://localhost:8002"),
        api_key=sf_config.get("_dataservice_api_key", ""),
        timeout=float(sf_config.get("_dataservice_timeout", "30")),
        db_config={
            "__database": sf_config.get("__database", DEFAULT_DATABASE_NAME),
            "__dbtype": sf_config.get("__dbtype", "postgresql"),
        },
    )

    return create_data_service(config)


def create_data_service_from_env() -> DataService:
    """Create a DataService from environment variables.

    Environment variables:
        SF_DATASERVICE_BACKEND: 'local', 'http', or 'grpc'
        SF_DATASERVICE_API_URL: URL for remote backends
        SF_DATASERVICE_API_KEY: Auth key for remote backends
        SF_DATASERVICE_TIMEOUT: Request timeout (seconds)
        SF_DATABASE: Database path/URL
        SF_DBTYPE: Database type

    Returns:
        Configured DataService instance
    """
    backend_str = os.environ.get("SF_DATASERVICE_BACKEND", "local")

    try:
        backend = DataServiceBackend(backend_str.lower())
    except ValueError:
        log.warning("Unknown backend '%s', defaulting to local", backend_str)
        backend = DataServiceBackend.LOCAL

    config = DataServiceConfig(
        backend=backend,
        api_url=os.environ.get("SF_DATASERVICE_API_URL", "http://localhost:8002"),
        api_key=os.environ.get("SF_DATASERVICE_API_KEY", ""),
        timeout=float(os.environ.get("SF_DATASERVICE_TIMEOUT", "30")),
        db_config={
            "__database": os.environ.get("SF_DATABASE", DEFAULT_DATABASE_NAME),
            "__dbtype": os.environ.get("SF_DBTYPE", "postgresql"),
        },
    )

    return create_data_service(config)


class DataServiceBridge:
    """Bridge between the new DataService and legacy SpiderFootDb callers.

    Provides backward compatibility by exposing legacy method names
    that delegate to a DataService instance. This allows gradual
    migration of modules from direct DB access to the service layer.

    Usage:
        ds = create_data_service(config)
        bridge = DataServiceBridge(ds)

        # Legacy code can call:
        bridge.scanInstanceCreate(scan_id, name, target)
        bridge.scanEventStore(scan_id, sf_event)
    """

    def __init__(self, data_service: DataService) -> None:
        """Initialize the DataServiceBridge."""
        self._ds = data_service
        self.log = logging.getLogger("spiderfoot.dataservice.bridge")

    # --- Legacy scan methods ---

    def scanInstanceCreate(self, instanceId: str, scanName: str, scanTarget: str) -> None:
        """Legacy wrapper for scan_instance_create."""
        self._ds.scan_instance_create(instanceId, scanName, scanTarget)

    def scanInstanceGet(self, instanceId: str) -> list:
        """Legacy wrapper returning tuple format."""
        result = self._ds.scan_instance_get(instanceId)
        if result is None:
            return []
        return [(result["name"], result["target"], result["created"],
                 result["started"], result["ended"], result["status"])]

    def scanInstanceList(self) -> list:
        """Legacy wrapper returning tuple format."""
        results = self._ds.scan_instance_list()
        return [
            (r["id"], r["name"], r["target"], r["created"],
             r["started"], r["ended"], r["status"], r.get("result_count", 0))
            for r in results
        ]

    def scanInstanceDelete(self, instanceId: str) -> None:
        """Legacy wrapper for scan_instance_delete."""
        self._ds.scan_instance_delete(instanceId)

    def scanInstanceSet(
        self,
        instanceId: str,
        started: int | None = None,
        ended: int | None = None,
        status: str | None = None,
    ) -> None:
        """Legacy wrapper for scan_status_set."""
        started_int = int(started) if started else None
        ended_int = int(ended) if ended else None
        self._ds.scan_status_set(instanceId, status or "", started_int, ended_int)

    # --- Legacy event methods ---

    def scanEventStore(self, instanceId: str, sfEvent: Any) -> None:
        """Legacy wrapper - stores a SpiderFootEvent."""
        if isinstance(self._ds, LocalDataService):
            self._ds.event_store_obj(instanceId, sfEvent)
        else:
            # For remote backends, serialize the event
            self._ds.event_store(
                scan_id=instanceId,
                event_hash=sfEvent.hash,
                event_type=sfEvent.eventType,
                module=sfEvent.module,
                data=sfEvent.data,
                source_event_hash=sfEvent.sourceEventHash or "ROOT",
                confidence=sfEvent.confidence,
                visibility=sfEvent.visibility,
                risk=sfEvent.risk,
            )

    def scanResultEvent(self, instanceId: str, eventType: str = "ALL", **kwargs) -> list:
        """Legacy wrapper for event queries."""
        et = None if eventType == "ALL" else eventType
        results = self._ds.event_get_by_scan(instanceId, event_type=et)
        return [
            (r["generated"], r["data"], r["module"], r["hash"],
             r["type"], r["source_event_hash"], r["confidence"],
             r["visibility"], r["risk"])
            for r in results
        ]

    def scanResultSummary(self, instanceId: str, by: str = "type") -> list:
        """Legacy wrapper - partial support."""
        if by == "type":
            summary = self._ds.scan_result_summary(instanceId)
            return [(k, "", "", v, 0) for k, v in summary.items()]
        self.log.warning("scanResultSummary by='%s' not fully supported via bridge", by)
        return []

    # --- Legacy log methods ---

    def scanLogEvent(self, instanceId: str, classification: str, message: str, component: str | None = None) -> None:
        """Legacy wrapper for scan_log_event."""
        self._ds.scan_log_event(instanceId, classification, message, component)

    def scanLogs(self, instanceId: str, limit: int | None = None, fromRowId: int = 0, reverse: bool = False) -> list:
        """Legacy wrapper for scan_log_get."""
        lmt = limit if limit else 0
        results = self._ds.scan_log_get(instanceId, limit=lmt, offset=fromRowId)
        rows = [
            (r["generated"], r["component"], r["type"], r["message"], r["rowid"])
            for r in results
        ]
        if reverse:
            rows.reverse()
        return rows

    # --- Legacy config methods ---

    def configSet(self, optMap: dict | None = None) -> None:
        """Legacy wrapper for config_set."""
        if optMap is None:
            optMap = {}
        self._ds.config_set(optMap)

    def configGet(self) -> Any:
        """Legacy wrapper for config_get."""
        return self._ds.config_get()

    def scanConfigSet(self, scan_id: str, optMap: dict | None = None) -> None:
        """Legacy wrapper for scan_config_set."""
        if optMap is None:
            optMap = {}
        self._ds.scan_config_set(scan_id, optMap)

    # --- Legacy event type methods ---

    def eventTypes(self) -> list:
        """Legacy wrapper for event_types_list."""
        results = self._ds.event_types_list()
        return [
            (r["event_descr"], r["event"], r.get("event_raw", 0), r["event_type"])
            for r in results
        ]
