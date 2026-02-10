"""
Abstract base class for the SpiderFoot Data Service.

Defines the interface that all data service implementations must provide.
Modules interact with this interface instead of directly with SpiderFootDb.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DataServiceBackend(str, Enum):
    """Supported data service backends."""
    LOCAL = "local"        # Direct DB access (same process)
    HTTP = "http"          # REST API client (microservice)
    GRPC = "grpc"          # gRPC client (high-performance microservice)


@dataclass
class DataServiceConfig:
    """Configuration for the data service.

    Attributes:
        backend: Which backend to use
        api_url: URL for HTTP/gRPC backend
        api_key: Authentication key for remote backends
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        db_config: Database config (for local backend)
    """
    backend: DataServiceBackend = DataServiceBackend.LOCAL
    api_url: str = "http://localhost:8002"
    api_key: str = ""
    timeout: float = 30.0
    max_retries: int = 3
    db_config: dict[str, Any] = field(default_factory=dict)


class DataService(ABC):
    """Abstract data service interface.

    Provides CRUD operations for scans, events, configs, and correlations.
    All methods are synchronous for compatibility with the existing module
    system, but implementations may use async internally.
    """

    def __init__(self, config: DataServiceConfig | None = None) -> None:
        """Initialize the DataService."""
        self.config = config or DataServiceConfig()
        self.log = logging.getLogger(f"spiderfoot.dataservice.{self.config.backend.value}")

    # --- Scan Instance Operations ---

    @abstractmethod
    def scan_instance_create(self, scan_id: str, scan_name: str, target: str) -> bool:
        """Create a new scan instance.

        Args:
            scan_id: Unique scan identifier
            scan_name: Human-readable scan name
            target: Scan target

        Returns:
            True if created successfully
        """
        ...

    @abstractmethod
    def scan_instance_get(self, scan_id: str) -> dict[str, Any] | None:
        """Get a scan instance by ID.

        Args:
            scan_id: Scan identifier

        Returns:
            Scan instance data or None
        """
        ...

    @abstractmethod
    def scan_instance_list(self) -> list[dict[str, Any]]:
        """List all scan instances.

        Returns:
            List of scan instance dicts
        """
        ...

    @abstractmethod
    def scan_instance_delete(self, scan_id: str) -> bool:
        """Delete a scan instance and all associated data.

        Args:
            scan_id: Scan identifier

        Returns:
            True if deleted successfully
        """
        ...

    @abstractmethod
    def scan_status_set(self, scan_id: str, status: str,
                        started: int | None = None,
                        ended: int | None = None) -> bool:
        """Update scan status.

        Args:
            scan_id: Scan identifier
            status: New status string
            started: Optional start timestamp (ms)
            ended: Optional end timestamp (ms)

        Returns:
            True if updated
        """
        ...

    # --- Event Operations ---

    @abstractmethod
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
        """Store a scan event/result.

        Args:
            scan_id: Scan identifier
            event_hash: Unique event hash
            event_type: Event type string
            module: Source module name
            data: Event data
            source_event_hash: Parent event hash
            confidence: Confidence score 0-100
            visibility: Visibility score 0-100
            risk: Risk score 0-100

        Returns:
            True if stored successfully
        """
        ...

    @abstractmethod
    def event_get_by_scan(
        self,
        scan_id: str,
        event_type: str | None = None,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        """Get events for a scan, optionally filtered by type.

        Args:
            scan_id: Scan identifier
            event_type: Optional filter by event type
            limit: Maximum results (0 = no limit)

        Returns:
            List of event dicts
        """
        ...

    @abstractmethod
    def event_get_unique(
        self,
        scan_id: str,
        event_type: str,
    ) -> list[str]:
        """Get unique event data values for a scan and type.

        Args:
            scan_id: Scan identifier
            event_type: Event type filter

        Returns:
            List of unique data values
        """
        ...

    @abstractmethod
    def event_exists(
        self,
        scan_id: str,
        event_type: str,
        data: str,
    ) -> bool:
        """Check if an event already exists.

        Args:
            scan_id: Scan identifier
            event_type: Event type
            data: Event data

        Returns:
            True if event exists
        """
        ...

    # --- Log Operations ---

    @abstractmethod
    def scan_log_event(
        self,
        scan_id: str,
        classification: str,
        message: str,
        component: str | None = None,
    ) -> bool:
        """Log a scan event.

        Args:
            scan_id: Scan identifier
            classification: Log classification (STATUS, ERROR, etc.)
            message: Log message
            component: Source component

        Returns:
            True if logged
        """
        ...

    @abstractmethod
    def scan_log_get(
        self,
        scan_id: str,
        limit: int = 0,
        offset: int = 0,
        log_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get scan log entries.

        Args:
            scan_id: Scan identifier
            limit: Max results
            offset: Result offset
            log_type: Optional filter by log type

        Returns:
            List of log entry dicts
        """
        ...

    # --- Config Operations ---

    @abstractmethod
    def config_set(self, config_data: dict[str, str], scope: str = "GLOBAL") -> bool:
        """Set configuration values.

        Args:
            config_data: Dict of option name → value
            scope: Config scope (GLOBAL or scan_id)

        Returns:
            True if saved
        """
        ...

    @abstractmethod
    def config_get(self, scope: str = "GLOBAL") -> dict[str, str]:
        """Get configuration values for a scope.

        Args:
            scope: Config scope

        Returns:
            Dict of option name → value
        """
        ...

    @abstractmethod
    def scan_config_set(self, scan_id: str, config_data: dict[str, str]) -> bool:
        """Save scan-specific configuration.

        Args:
            scan_id: Scan identifier
            config_data: Configuration key-value pairs

        Returns:
            True if saved
        """
        ...

    # --- Correlation Operations ---

    @abstractmethod
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
        """Store a correlation result.

        Args:
            correlation_id: Unique correlation ID
            scan_id: Scan identifier
            title: Correlation title
            rule_id: Rule identifier
            rule_name: Rule name
            rule_risk: Risk level
            rule_descr: Rule description
            rule_logic: Rule logic
            event_hashes: List of related event hashes

        Returns:
            True if stored
        """
        ...

    @abstractmethod
    def correlation_get_by_scan(self, scan_id: str) -> list[dict[str, Any]]:
        """Get all correlations for a scan.

        Args:
            scan_id: Scan identifier

        Returns:
            List of correlation result dicts
        """
        ...

    # --- Aggregate / Summary Operations ---

    @abstractmethod
    def scan_result_summary(
        self,
        scan_id: str,
    ) -> dict[str, int]:
        """Get event type counts for a scan.

        Args:
            scan_id: Scan identifier

        Returns:
            Dict mapping event_type → count
        """
        ...

    @abstractmethod
    def event_types_list(self) -> list[dict[str, str]]:
        """List all registered event types.

        Returns:
            List of event type dicts with 'event', 'event_descr', 'event_type'
        """
        ...
