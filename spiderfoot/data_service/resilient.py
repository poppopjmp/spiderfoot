"""
Resilient DataService wrapper with circuit breaker and fallback.

Wraps any remote DataService backend (HTTP, gRPC) with:
- Circuit breaker to prevent cascading failures
- Optional local fallback when the remote is unavailable
- Request metrics (success/failure counts, latency)

Usage::

    from spiderfoot.data_service.resilient import ResilientDataService

    primary = HttpDataService(config)
    fallback = LocalDataService(config)

    ds = ResilientDataService(primary, fallback=fallback)
    scans = ds.scan_instance_list()  # uses primary, falls back on failure
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional, TypeVar

from spiderfoot.data_service.base import DataService, DataServiceConfig

log = logging.getLogger("spiderfoot.dataservice.resilient")

T = TypeVar("T")


class CircuitState:
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class DataServiceCircuitBreaker:
    """Synchronous circuit breaker for DataService calls.

    Re-uses the pattern from spiderfoot.api_gateway.CircuitBreaker
    but is DataService-specific with integrated metrics.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        self._total_trips = 0

    @property
    def state(self) -> str:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def allow_request(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max:
                self._half_open_calls += 1
                return True
            return False
        return False

    def record_success(self) -> None:
        self._failure_count = 0
        self._success_count += 1
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._total_trips += 1
            log.warning(
                "DataService circuit breaker OPEN (failures=%d, trips=%d)",
                self._failure_count,
                self._total_trips,
            )

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_trips": self._total_trips,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


class ResilientDataService(DataService):
    """DataService proxy that wraps a primary backend with resilience.

    Features:
      - Circuit breaker prevents calls to an unhealthy backend
      - Optional fallback DataService used when primary is unavailable
      - Per-call latency and success/failure tracking
      - Health info exposed via health_info()
    """

    def __init__(
        self,
        primary: DataService,
        fallback: DataService | None = None,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        super().__init__(primary.config)
        self._primary = primary
        self._fallback = fallback
        self._cb = DataServiceCircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
        self._call_count = 0
        self._fallback_count = 0

    def _call(self, method_name: str, *args, default: Any = None, **kwargs) -> Any:
        """Execute a method through the circuit breaker with fallback."""
        self._call_count += 1

        # Try primary if circuit allows
        if self._cb.allow_request():
            try:
                method = getattr(self._primary, method_name)
                result = method(*args, **kwargs)
                self._cb.record_success()
                return result
            except Exception as e:
                self._cb.record_failure()
                log.warning(
                    "Primary DataService.%s failed: %s",
                    method_name,
                    e,
                )
        else:
            log.debug(
                "Circuit breaker OPEN — skipping primary for %s",
                method_name,
            )

        # Try fallback
        if self._fallback is not None:
            try:
                self._fallback_count += 1
                method = getattr(self._fallback, method_name)
                return method(*args, **kwargs)
            except Exception as e:
                log.error(
                    "Fallback DataService.%s also failed: %s",
                    method_name,
                    e,
                )

        return default

    def health_info(self) -> dict:
        """Return health/resilience metrics."""
        return {
            "circuit_breaker": self._cb.to_dict(),
            "total_calls": self._call_count,
            "fallback_calls": self._fallback_count,
            "primary_backend": type(self._primary).__name__,
            "fallback_backend": type(self._fallback).__name__ if self._fallback else None,
        }

    # ------------------------------------------------------------------
    # DataService interface — delegate through _call()
    # ------------------------------------------------------------------

    def scan_instance_create(self, scan_id: str, scan_name: str, target: str) -> bool:
        return self._call("scan_instance_create", scan_id, scan_name, target, default=False)

    def scan_instance_get(self, scan_id: str) -> dict[str, Any] | None:
        return self._call("scan_instance_get", scan_id, default=None)

    def scan_instance_list(self) -> list[dict[str, Any]]:
        return self._call("scan_instance_list", default=[])

    def scan_instance_delete(self, scan_id: str) -> bool:
        return self._call("scan_instance_delete", scan_id, default=False)

    def scan_status_set(self, scan_id: str, status: str,
                        started: int | None = None,
                        ended: int | None = None) -> bool:
        return self._call("scan_status_set", scan_id, status,
                          started=started, ended=ended, default=False)

    def event_store(self, scan_id: str, event_hash: str, event_type: str,
                    module: str, data: str, source_event_hash: str = "ROOT",
                    confidence: int = 100, visibility: int = 100,
                    risk: int = 0) -> bool:
        return self._call(
            "event_store", scan_id, event_hash, event_type, module, data,
            source_event_hash=source_event_hash, confidence=confidence,
            visibility=visibility, risk=risk, default=False,
        )

    def event_get_by_scan(self, scan_id: str,
                          event_type: str | None = None,
                          limit: int = 0) -> list[dict[str, Any]]:
        return self._call("event_get_by_scan", scan_id,
                          event_type=event_type, limit=limit, default=[])

    def event_get_unique(self, scan_id: str, event_type: str) -> list[str]:
        return self._call("event_get_unique", scan_id, event_type, default=[])

    def event_exists(self, scan_id: str, event_type: str,
                     data: str) -> bool:
        return self._call("event_exists", scan_id, event_type, data, default=False)

    def scan_log_event(self, scan_id: str, classification: str,
                       message: str, component: str | None = None) -> bool:
        return self._call("scan_log_event", scan_id, classification,
                          message, component=component, default=False)

    def scan_log_get(self, scan_id: str, limit: int = 0,
                     offset: int = 0,
                     log_type: str | None = None) -> list[dict[str, Any]]:
        return self._call("scan_log_get", scan_id, limit=limit,
                          offset=offset, log_type=log_type, default=[])

    def config_set(self, config_data: dict[str, str],
                   scope: str = "GLOBAL") -> bool:
        return self._call("config_set", config_data, scope=scope, default=False)

    def config_get(self, scope: str = "GLOBAL") -> dict[str, str]:
        return self._call("config_get", scope=scope, default={})

    def scan_config_set(self, scan_id: str,
                        config_data: dict[str, str]) -> bool:
        return self._call("scan_config_set", scan_id, config_data, default=False)

    def correlation_store(self, correlation_id: str, scan_id: str,
                          title: str, rule_id: str, rule_name: str,
                          rule_risk: str, rule_descr: str,
                          rule_logic: str,
                          event_hashes: list[str]) -> bool:
        return self._call(
            "correlation_store", correlation_id, scan_id, title,
            rule_id, rule_name, rule_risk, rule_descr, rule_logic,
            event_hashes, default=False,
        )

    def correlation_get_by_scan(self, scan_id: str) -> list[dict[str, Any]]:
        return self._call("correlation_get_by_scan", scan_id, default=[])

    def scan_result_summary(self, scan_id: str) -> dict[str, int]:
        return self._call("scan_result_summary", scan_id, default={})

    def event_types_list(self) -> list[dict[str, str]]:
        return self._call("event_types_list", default=[])
