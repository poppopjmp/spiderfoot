"""
EventBus Hardening — resilient middleware for the SpiderFoot EventBus.

Wraps any ``EventBus`` implementation with production-grade concerns:

* **Circuit breaker** — stops publish attempts when the backend is
  consistently failing, reopening after a recovery timeout.
* **Dead-letter queue** — events that fail after all retries are
  captured for later inspection / replay.
* **Metrics instrumentation** — publishes/consumes/failures counted.
* **Health probing** — periodic liveness check with configurable
  interval and callback notification.
* **Publish retry with backoff** — configurable retry count and
  exponential backoff.

Usage::

    from spiderfoot.eventbus.memory import InMemoryEventBus
    from spiderfoot.eventbus_hardening import ResilientEventBus

    inner = InMemoryEventBus()
    bus = ResilientEventBus(inner)
    await bus.connect()
    await bus.publish(envelope)

    # Check health / metrics
    print(bus.health_status())
    print(bus.metrics())
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from spiderfoot.eventbus.base import EventBus, EventBusConfig, EventEnvelope

log = logging.getLogger("spiderfoot.eventbus.hardening")


# ---------------------------------------------------------------------------
# Circuit breaker (async-compatible)
# ---------------------------------------------------------------------------


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AsyncCircuitBreaker:
    """Async-aware circuit breaker for EventBus backends.

    State transitions::

        CLOSED  —(failures >= threshold)→  OPEN
        OPEN    —(timeout elapsed)→        HALF_OPEN
        HALF_OPEN —(probe succeeds)→       CLOSED
        HALF_OPEN —(probe fails)→          OPEN
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._lock = asyncio.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        self._state_change_callbacks: list[Callable] = []

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def allow_request(self) -> bool:
        """Check whether a request should be allowed through."""
        async with self._lock:
            current = self.state
            if current == CircuitState.CLOSED:
                return True
            if current == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max:
                    self._half_open_calls += 1
                    self._state = CircuitState.HALF_OPEN
                    return True
                return False
            return False  # OPEN

    async def record_success(self) -> None:
        async with self._lock:
            self._success_count += 1
            old = self._state
            if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                self._state = CircuitState.CLOSED
                self._half_open_calls = 0
                log.info("Circuit breaker closed (recovered)")
                await self._notify(old, CircuitState.CLOSED)
            # Always reset failure count on success so consecutive
            # failures start fresh.
            self._failure_count = 0

    async def record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._state == CircuitState.HALF_OPEN:
                old = self._state
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                log.warning("Circuit breaker re-opened from half-open")
                await self._notify(old, CircuitState.OPEN)
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                old = self._state
                self._state = CircuitState.OPEN
                log.warning(
                    "Circuit breaker opened (failures=%d, threshold=%d)",
                    self._failure_count,
                    self.failure_threshold,
                )
                await self._notify(old, CircuitState.OPEN)

    async def _notify(self, old: CircuitState, new: CircuitState) -> None:
        for cb in self._state_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(old, new)
                else:
                    cb(old, new)
            except Exception as e:
                log.debug("lifecycle callback cb(old, new) failed: %s", e)

    def on_state_change(self, callback: Callable) -> None:
        """Register a callback ``(old_state, new_state)``."""
        self._state_change_callbacks.append(callback)

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


# ---------------------------------------------------------------------------
# Dead-letter queue (async)
# ---------------------------------------------------------------------------


@dataclass
class DeadLetterEntry:
    """A failed publish attempt stored for later replay."""

    envelope: EventEnvelope
    error: str
    timestamp: float = field(default_factory=time.time)
    attempts: int = 0


class AsyncDeadLetterQueue:
    """Bounded async-safe dead-letter queue."""

    def __init__(self, max_size: int = 1000):
        self._max_size = max_size
        self._items: list[DeadLetterEntry] = []
        self._lock = asyncio.Lock()
        self._total_added = 0

    async def add(self, entry: DeadLetterEntry) -> None:
        async with self._lock:
            if len(self._items) >= self._max_size:
                self._items.pop(0)  # drop oldest
            self._items.append(entry)
            self._total_added += 1

    async def pop(self) -> Optional[DeadLetterEntry]:
        async with self._lock:
            return self._items.pop(0) if self._items else None

    async def peek(self, n: int = 10) -> list[DeadLetterEntry]:
        async with self._lock:
            return list(self._items[-n:])

    async def clear(self) -> int:
        async with self._lock:
            count = len(self._items)
            self._items.clear()
            return count

    @property
    def size(self) -> int:
        return len(self._items)

    @property
    def total_added(self) -> int:
        return self._total_added

    async def replay(self, publish_fn: Callable) -> int:
        """Attempt to republish all DLQ entries.

        Returns the number of successfully replayed events.
        """
        replayed = 0
        remaining: list[DeadLetterEntry] = []

        async with self._lock:
            items = list(self._items)
            self._items.clear()

        for entry in items:
            try:
                result = await publish_fn(entry.envelope)
                if result:
                    replayed += 1
                else:
                    remaining.append(entry)
            except Exception:
                remaining.append(entry)

        if remaining:
            async with self._lock:
                self._items = remaining + self._items

        return replayed


# ---------------------------------------------------------------------------
# Metrics collector
# ---------------------------------------------------------------------------


class EventBusMetrics:
    """Thread-safe metrics collector for EventBus operations."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {
            "published": 0,
            "publish_failed": 0,
            "consumed": 0,
            "consume_errors": 0,
            "circuit_opened": 0,
            "circuit_closed": 0,
            "dlq_added": 0,
            "dlq_replayed": 0,
            "retries": 0,
        }
        self._topic_counts: dict[str, int] = {}
        self._start_time = time.monotonic()

    def inc(self, counter: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[counter] = self._counters.get(counter, 0) + amount

    def inc_topic(self, topic: str) -> None:
        with self._lock:
            self._topic_counts[topic] = self._topic_counts.get(topic, 0) + 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            uptime = time.monotonic() - self._start_time
            rate = (
                self._counters["published"] / uptime if uptime > 0 else 0
            )
            return {
                **dict(self._counters),
                "uptime_seconds": round(uptime, 2),
                "publish_rate_per_sec": round(rate, 4),
                "top_topics": dict(
                    sorted(
                        self._topic_counts.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:10]
                ),
            }

    def reset(self) -> None:
        with self._lock:
            for k in self._counters:
                self._counters[k] = 0
            self._topic_counts.clear()
            self._start_time = time.monotonic()


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health probe."""
    status: HealthStatus
    backend: str
    connected: bool
    circuit_state: str
    dlq_size: int
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "backend": self.backend,
            "connected": self.connected,
            "circuit_state": self.circuit_state,
            "dlq_size": self.dlq_size,
            "details": self.details,
            "checked_at": self.checked_at,
        }


# ---------------------------------------------------------------------------
# Resilient EventBus wrapper
# ---------------------------------------------------------------------------


@dataclass
class ResilientConfig:
    """Configuration for the resilient EventBus wrapper."""

    max_publish_retries: int = 3
    """Maximum retry attempts per publish."""

    retry_backoff_base: float = 0.5
    """Base delay in seconds (doubles each retry)."""

    circuit_failure_threshold: int = 5
    """Failures before opening the circuit."""

    circuit_recovery_timeout: float = 30.0
    """Seconds before moving from OPEN → HALF_OPEN."""

    dlq_max_size: int = 1000
    """Maximum dead-letter queue entries."""

    health_check_interval: float = 60.0
    """Seconds between automatic health probes (0 = disabled)."""


class ResilientEventBus:
    """Production-hardened EventBus wrapper.

    Decorates any ``EventBus`` implementation with:

    - Circuit breaker
    - Dead-letter queue
    - Retry with exponential backoff
    - Metrics instrumentation
    - Health probing

    The wrapper delegates all calls to the inner bus, adding resilience
    concerns transparently.
    """

    def __init__(
        self,
        inner: EventBus,
        config: Optional[ResilientConfig] = None,
    ):
        self._inner = inner
        self._config = config or ResilientConfig()

        self.circuit = AsyncCircuitBreaker(
            failure_threshold=self._config.circuit_failure_threshold,
            recovery_timeout=self._config.circuit_recovery_timeout,
        )
        self.dlq = AsyncDeadLetterQueue(
            max_size=self._config.dlq_max_size,
        )
        self.metrics = EventBusMetrics()

        self._health_task: Optional[asyncio.Task] = None
        self._last_health: Optional[HealthCheckResult] = None

        # Wire circuit state changes into metrics
        self.circuit.on_state_change(self._on_circuit_change)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect the underlying EventBus and start health probing."""
        await self._inner.connect()
        if self._config.health_check_interval > 0:
            self._health_task = asyncio.create_task(self._health_loop())

    async def disconnect(self) -> None:
        """Gracefully shut down the bus and health loop."""
        if self._health_task is not None:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None
        await self._inner.disconnect()

    @property
    def is_connected(self) -> bool:
        return self._inner.is_connected

    @property
    def inner(self) -> EventBus:
        return self._inner

    # ------------------------------------------------------------------
    # Publish (with retry + circuit breaker + DLQ)
    # ------------------------------------------------------------------

    async def publish(self, envelope: EventEnvelope) -> bool:
        """Publish with retry, circuit breaker, and DLQ fallback.

        Returns True if the event was successfully delivered.
        """
        # Circuit breaker check
        if not await self.circuit.allow_request():
            log.warning(
                "Circuit open — rejecting publish for topic %s",
                envelope.topic,
            )
            self.metrics.inc("publish_failed")
            await self._send_to_dlq(envelope, "circuit_open", attempts=0)
            return False

        last_error = ""
        for attempt in range(1, self._config.max_publish_retries + 1):
            try:
                result = await self._inner.publish(envelope)
                if result:
                    await self.circuit.record_success()
                    self.metrics.inc("published")
                    self.metrics.inc_topic(envelope.topic)
                    return True
                else:
                    # Publish returned False (no subscribers) — not a failure
                    self.metrics.inc("published")
                    return False
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < self._config.max_publish_retries:
                    self.metrics.inc("retries")
                    delay = self._config.retry_backoff_base * (2 ** (attempt - 1))
                    log.debug(
                        "Publish retry %d/%d for topic %s (delay=%.2fs)",
                        attempt,
                        self._config.max_publish_retries,
                        envelope.topic,
                        delay,
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        await self.circuit.record_failure()
        self.metrics.inc("publish_failed")
        await self._send_to_dlq(envelope, last_error, attempts=self._config.max_publish_retries)
        return False

    async def _send_to_dlq(
        self, envelope: EventEnvelope, error: str, attempts: int
    ) -> None:
        entry = DeadLetterEntry(
            envelope=envelope, error=error, attempts=attempts
        )
        await self.dlq.add(entry)
        self.metrics.inc("dlq_added")
        log.warning(
            "Event sent to DLQ: topic=%s error=%s",
            envelope.topic,
            error,
        )

    # ------------------------------------------------------------------
    # Subscribe / unsubscribe (pass-through with metrics)
    # ------------------------------------------------------------------

    async def subscribe(
        self,
        topic: str,
        callback: Callable[[EventEnvelope], Any],
    ) -> str:
        """Subscribe with metrics-instrumented callback wrapper."""

        async def _instrumented(env: EventEnvelope) -> Any:
            try:
                if asyncio.iscoroutinefunction(callback):
                    result = await callback(env)
                else:
                    result = callback(env)
                self.metrics.inc("consumed")
                return result
            except Exception as exc:
                self.metrics.inc("consume_errors")
                log.error(
                    "Subscriber error on topic %s: %s",
                    topic,
                    exc,
                )
                raise

        return await self._inner.subscribe(topic, _instrumented)

    async def unsubscribe(self, subscription_id: str) -> None:
        await self._inner.unsubscribe(subscription_id)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        """Run a health probe against the backend."""
        connected = self._inner.is_connected
        circuit_state = self.circuit.state.value
        dlq_size = self.dlq.size

        if not connected:
            status = HealthStatus.UNHEALTHY
        elif circuit_state == CircuitState.OPEN.value:
            status = HealthStatus.UNHEALTHY
        elif circuit_state == CircuitState.HALF_OPEN.value:
            status = HealthStatus.DEGRADED
        elif dlq_size > 100:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        result = HealthCheckResult(
            status=status,
            backend=self._inner.config.backend.value,
            connected=connected,
            circuit_state=circuit_state,
            dlq_size=dlq_size,
            details=self.metrics.snapshot(),
        )
        self._last_health = result
        return result

    async def _health_loop(self) -> None:
        """Periodic health probe."""
        try:
            while True:
                await asyncio.sleep(self._config.health_check_interval)
                try:
                    await self.health_check()
                except Exception as exc:
                    log.debug("Health check error: %s", exc)
        except asyncio.CancelledError:
            pass

    def health_status(self) -> Optional[HealthCheckResult]:
        """Return the last cached health check result."""
        return self._last_health

    # ------------------------------------------------------------------
    # DLQ replay
    # ------------------------------------------------------------------

    async def replay_dlq(self) -> int:
        """Attempt to republish all DLQ entries through the inner bus.

        Returns the count of successfully replayed events.
        """
        replayed = await self.dlq.replay(self._inner.publish)
        self.metrics.inc("dlq_replayed", replayed)
        return replayed

    # ------------------------------------------------------------------
    # Metrics / introspection
    # ------------------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        """Return a snapshot of all metrics."""
        return self.metrics.snapshot()

    # ------------------------------------------------------------------
    # Circuit breaker callback
    # ------------------------------------------------------------------

    async def _on_circuit_change(
        self, old: CircuitState, new: CircuitState
    ) -> None:
        if new == CircuitState.OPEN:
            self.metrics.inc("circuit_opened")
        elif new == CircuitState.CLOSED:
            self.metrics.inc("circuit_closed")

    # ------------------------------------------------------------------
    # Convenience sync wrappers
    # ------------------------------------------------------------------

    def publish_sync(self, envelope: EventEnvelope) -> bool:
        """Synchronous wrapper for publish — mirrors EventBus API."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.publish(envelope))
                return future.result(timeout=30)
        else:
            return asyncio.run(self.publish(envelope))

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<ResilientEventBus inner={type(self._inner).__name__} "
            f"circuit={self.circuit.state.value} dlq={self.dlq.size}>"
        )
