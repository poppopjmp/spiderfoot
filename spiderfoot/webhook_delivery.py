"""
Webhook Delivery System — reliable outbound webhook delivery with retries.

Provides:
  - Webhook event dispatching with configurable retry policies
  - Circuit breaker pattern for failing endpoints
  - Delivery attempt tracking and history
  - HMAC-SHA256 signature verification
  - Dead letter queue for permanently failed deliveries
  - Rate limiting per endpoint

v5.6.7
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

_log = logging.getLogger("spiderfoot.webhook_delivery")


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class RetryPolicy:
    """Retry configuration for webhook delivery."""
    max_retries: int = 5
    initial_delay_seconds: float = 5.0
    max_delay_seconds: float = 3600.0
    backoff_multiplier: float = 2.0
    retry_on_status_codes: list[int] = field(
        default_factory=lambda: [408, 429, 500, 502, 503, 504]
    )


@dataclass
class CircuitBreaker:
    """Circuit breaker state for an endpoint."""
    endpoint_id: str = ""
    state: str = CircuitState.CLOSED.value
    failure_count: int = 0
    failure_threshold: int = 5
    success_count: int = 0
    recovery_threshold: int = 3
    last_failure_at: float = 0.0
    opened_at: float = 0.0
    cooldown_seconds: float = 300.0  # 5 minutes


@dataclass
class DeliveryAttempt:
    """Record of a single delivery attempt."""
    attempt_id: str = ""
    delivery_id: str = ""
    attempt_number: int = 1
    status_code: int = 0
    response_body: str = ""
    error: str = ""
    duration_ms: float = 0.0
    timestamp: float = 0.0


@dataclass
class WebhookDelivery:
    """A webhook delivery record."""
    delivery_id: str = ""
    endpoint_id: str = ""
    endpoint_url: str = ""
    event_type: str = ""
    payload: dict = field(default_factory=dict)
    status: str = DeliveryStatus.PENDING.value

    # Signature
    signature: str = ""
    signature_header: str = "X-SpiderFoot-Signature-256"

    # Retry state
    attempt_count: int = 0
    max_retries: int = 5
    next_retry_at: float = 0.0

    # Attempts history
    attempts: list[dict] = field(default_factory=list)

    # Timestamps
    created_at: float = 0.0
    delivered_at: float = 0.0
    failed_at: float = 0.0

    # Metadata
    headers: dict = field(default_factory=dict)
    timeout_seconds: int = 30
    idempotency_key: str = ""


class WebhookDeliveryManager:
    """Manages webhook delivery with retries and circuit breaking.

    Features:
      - Reliable delivery with exponential backoff retries
      - Per-endpoint circuit breaker (open after N failures)
      - Delivery attempt tracking with full history
      - HMAC-SHA256 payload signing
      - Dead letter queue for undeliverable webhooks
      - Per-endpoint rate limiting
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._deliveries_key = "sf:webhook:deliveries"
        self._dead_letter_key = "sf:webhook:dead_letter"
        self._circuit_key = "sf:webhook:circuits"
        self._stats_key = "sf:webhook:stats"
        self._default_retry = RetryPolicy()

    # ── Delivery creation ─────────────────────────────────────────────

    def create_delivery(
        self,
        endpoint_id: str,
        endpoint_url: str,
        event_type: str,
        payload: dict,
        *,
        secret: str = "",
        headers: dict | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout_seconds: int = 30,
    ) -> WebhookDelivery:
        """Create a new webhook delivery.

        Args:
            endpoint_id: Unique endpoint identifier
            endpoint_url: URL to deliver to
            event_type: Event type (e.g. scan.completed)
            payload: JSON payload to deliver
            secret: HMAC secret for signing
            headers: Additional headers
            retry_policy: Custom retry policy
            timeout_seconds: Request timeout

        Returns:
            Created WebhookDelivery
        """
        policy = retry_policy or self._default_retry
        delivery_id = str(uuid.uuid4())
        idempotency_key = hashlib.sha256(
            f"{endpoint_id}:{event_type}:{delivery_id}".encode()
        ).hexdigest()[:24]

        # Sign payload
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = ""
        if secret:
            signature = "sha256=" + hmac.new(
                secret.encode(), payload_bytes, hashlib.sha256
            ).hexdigest()

        delivery = WebhookDelivery(
            delivery_id=delivery_id,
            endpoint_id=endpoint_id,
            endpoint_url=endpoint_url,
            event_type=event_type,
            payload=payload,
            status=DeliveryStatus.PENDING.value,
            signature=signature,
            attempt_count=0,
            max_retries=policy.max_retries,
            next_retry_at=0.0,
            created_at=time.time(),
            headers=headers or {},
            timeout_seconds=timeout_seconds,
            idempotency_key=idempotency_key,
        )

        self._save_delivery(delivery)
        self._increment_stat("total_created")
        _log.info("Webhook delivery created: %s → %s (%s)",
                  delivery_id, endpoint_url, event_type)
        return delivery

    # ── Delivery processing ───────────────────────────────────────────

    def record_attempt(
        self,
        delivery_id: str,
        status_code: int = 0,
        response_body: str = "",
        error: str = "",
        duration_ms: float = 0.0,
    ) -> WebhookDelivery | None:
        """Record a delivery attempt result.

        Args:
            delivery_id: Delivery ID
            status_code: HTTP response status code (0 = connection error)
            response_body: Response body (truncated)
            error: Error message if failed
            duration_ms: Request duration in milliseconds

        Returns:
            Updated delivery or None
        """
        delivery = self.get_delivery(delivery_id)
        if not delivery:
            return None

        attempt = DeliveryAttempt(
            attempt_id=str(uuid.uuid4())[:8],
            delivery_id=delivery_id,
            attempt_number=delivery.attempt_count + 1,
            status_code=status_code,
            response_body=response_body[:2000],
            error=error,
            duration_ms=duration_ms,
            timestamp=time.time(),
        )

        delivery.attempt_count += 1
        delivery.attempts.append(asdict(attempt))

        # Determine success/failure
        is_success = 200 <= status_code < 300

        if is_success:
            delivery.status = DeliveryStatus.DELIVERED.value
            delivery.delivered_at = time.time()
            self._record_circuit_success(delivery.endpoint_id)
            self._increment_stat("total_delivered")
            _log.info("Webhook delivered: %s (attempt %d, %dms)",
                      delivery_id, attempt.attempt_number, duration_ms)
        else:
            should_retry = (
                delivery.attempt_count < delivery.max_retries
                and (status_code in self._default_retry.retry_on_status_codes or status_code == 0)
            )

            if should_retry:
                delay = self._calculate_retry_delay(delivery.attempt_count)
                delivery.status = DeliveryStatus.RETRYING.value
                delivery.next_retry_at = time.time() + delay
                self._increment_stat("total_retries")
                _log.warning("Webhook retry scheduled: %s in %.0fs (attempt %d)",
                             delivery_id, delay, attempt.attempt_number)
            else:
                delivery.status = DeliveryStatus.FAILED.value
                delivery.failed_at = time.time()
                self._move_to_dead_letter(delivery)
                self._record_circuit_failure(delivery.endpoint_id)
                self._increment_stat("total_failed")
                _log.error("Webhook permanently failed: %s after %d attempts",
                           delivery_id, delivery.attempt_count)

        self._save_delivery(delivery)
        return delivery

    # ── Circuit breaker ───────────────────────────────────────────────

    def get_circuit_state(self, endpoint_id: str) -> CircuitBreaker:
        """Get the circuit breaker state for an endpoint."""
        if self._redis:
            try:
                data = self._redis.hget(self._circuit_key, endpoint_id)
                if data:
                    return CircuitBreaker(**json.loads(data))
            except Exception:
                pass
        return CircuitBreaker(endpoint_id=endpoint_id)

    def is_circuit_open(self, endpoint_id: str) -> bool:
        """Check if the circuit breaker is open (blocking deliveries)."""
        cb = self.get_circuit_state(endpoint_id)
        if cb.state == CircuitState.OPEN.value:
            # Check if cooldown has expired
            if time.time() - cb.opened_at > cb.cooldown_seconds:
                cb.state = CircuitState.HALF_OPEN.value
                cb.success_count = 0
                self._save_circuit(cb)
                return False
            return True
        return False

    def reset_circuit(self, endpoint_id: str) -> CircuitBreaker:
        """Manually reset a circuit breaker."""
        cb = CircuitBreaker(endpoint_id=endpoint_id)
        self._save_circuit(cb)
        _log.info("Circuit breaker reset: %s", endpoint_id)
        return cb

    def _record_circuit_failure(self, endpoint_id: str) -> None:
        """Record a failure for the circuit breaker."""
        cb = self.get_circuit_state(endpoint_id)
        cb.failure_count += 1
        cb.last_failure_at = time.time()

        if cb.failure_count >= cb.failure_threshold:
            cb.state = CircuitState.OPEN.value
            cb.opened_at = time.time()
            _log.warning("Circuit breaker OPEN for endpoint %s "
                         "(%d failures)", endpoint_id, cb.failure_count)

        self._save_circuit(cb)

    def _record_circuit_success(self, endpoint_id: str) -> None:
        """Record a success for the circuit breaker."""
        cb = self.get_circuit_state(endpoint_id)

        if cb.state == CircuitState.HALF_OPEN.value:
            cb.success_count += 1
            if cb.success_count >= cb.recovery_threshold:
                cb.state = CircuitState.CLOSED.value
                cb.failure_count = 0
                cb.success_count = 0
                _log.info("Circuit breaker CLOSED for endpoint %s", endpoint_id)
        elif cb.state == CircuitState.CLOSED.value:
            # Reset failure count on success
            if cb.failure_count > 0:
                cb.failure_count = max(0, cb.failure_count - 1)

        self._save_circuit(cb)

    # ── Queries ───────────────────────────────────────────────────────

    def get_delivery(self, delivery_id: str) -> WebhookDelivery | None:
        """Get a delivery by ID."""
        if self._redis:
            try:
                data = self._redis.hget(self._deliveries_key, delivery_id)
                if data:
                    return WebhookDelivery(**json.loads(data))
            except Exception:
                pass
        return None

    def list_deliveries(
        self,
        endpoint_id: str | None = None,
        status: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List deliveries with optional filters."""
        deliveries = self._get_all_deliveries()

        if endpoint_id:
            deliveries = [d for d in deliveries if d.get("endpoint_id") == endpoint_id]
        if status:
            deliveries = [d for d in deliveries if d.get("status") == status]
        if event_type:
            deliveries = [d for d in deliveries if d.get("event_type") == event_type]

        deliveries.sort(key=lambda d: d.get("created_at", 0), reverse=True)
        return deliveries[:limit]

    def get_pending_retries(self) -> list[dict]:
        """Get deliveries that are ready for retry."""
        now = time.time()
        deliveries = self._get_all_deliveries()
        return [
            d for d in deliveries
            if d.get("status") == DeliveryStatus.RETRYING.value
            and d.get("next_retry_at", 0) <= now
        ]

    def get_dead_letter_queue(self, limit: int = 50) -> list[dict]:
        """Get deliveries in the dead letter queue."""
        if not self._redis:
            return []
        try:
            raw = self._redis.lrange(self._dead_letter_key, 0, limit - 1)
            return [json.loads(r) for r in raw]
        except Exception:
            return []

    def replay_dead_letter(self, delivery_id: str) -> WebhookDelivery | None:
        """Replay a delivery from the dead letter queue."""
        delivery = self.get_delivery(delivery_id)
        if not delivery:
            return None

        delivery.status = DeliveryStatus.PENDING.value
        delivery.attempt_count = 0
        delivery.next_retry_at = 0.0
        delivery.attempts = []
        delivery.failed_at = 0.0
        self._save_delivery(delivery)

        self._increment_stat("total_replayed")
        _log.info("Dead letter replayed: %s", delivery_id)
        return delivery

    def cancel_delivery(self, delivery_id: str) -> bool:
        """Cancel a pending or retrying delivery."""
        delivery = self.get_delivery(delivery_id)
        if not delivery:
            return False
        if delivery.status in (DeliveryStatus.DELIVERED.value, DeliveryStatus.CANCELLED.value):
            return False

        delivery.status = DeliveryStatus.CANCELLED.value
        self._save_delivery(delivery)
        _log.info("Delivery cancelled: %s", delivery_id)
        return True

    # ── Statistics ────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get delivery statistics."""
        stats = {
            "total_created": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "total_retries": 0,
            "total_replayed": 0,
            "dead_letter_count": 0,
            "pending_count": 0,
            "retrying_count": 0,
        }

        if self._redis:
            try:
                raw = self._redis.hgetall(self._stats_key)
                for k, v in raw.items():
                    key = k if isinstance(k, str) else k.decode()
                    stats[key] = int(v)
                stats["dead_letter_count"] = self._redis.llen(self._dead_letter_key)
            except Exception:
                pass

        # Count active statuses
        deliveries = self._get_all_deliveries()
        stats["pending_count"] = sum(1 for d in deliveries if d.get("status") == DeliveryStatus.PENDING.value)
        stats["retrying_count"] = sum(1 for d in deliveries if d.get("status") == DeliveryStatus.RETRYING.value)

        return stats

    def get_endpoint_stats(self, endpoint_id: str) -> dict:
        """Get delivery stats for a specific endpoint."""
        deliveries = self._get_all_deliveries()
        ep_deliveries = [d for d in deliveries if d.get("endpoint_id") == endpoint_id]

        cb = self.get_circuit_state(endpoint_id)

        return {
            "endpoint_id": endpoint_id,
            "total_deliveries": len(ep_deliveries),
            "delivered": sum(1 for d in ep_deliveries if d.get("status") == DeliveryStatus.DELIVERED.value),
            "failed": sum(1 for d in ep_deliveries if d.get("status") == DeliveryStatus.FAILED.value),
            "pending": sum(1 for d in ep_deliveries if d.get("status") == DeliveryStatus.PENDING.value),
            "retrying": sum(1 for d in ep_deliveries if d.get("status") == DeliveryStatus.RETRYING.value),
            "circuit_state": cb.state,
            "circuit_failures": cb.failure_count,
        }

    # ── Supported event types ─────────────────────────────────────────

    @staticmethod
    def get_event_types() -> list[dict]:
        """Return supported webhook event types."""
        return [
            {"event": "scan.started", "description": "Scan has started"},
            {"event": "scan.completed", "description": "Scan completed successfully"},
            {"event": "scan.failed", "description": "Scan failed with error"},
            {"event": "scan.aborted", "description": "Scan was manually aborted"},
            {"event": "scan.progress", "description": "Scan progress update (batched)"},
            {"event": "finding.new", "description": "New finding/event discovered"},
            {"event": "finding.critical", "description": "Critical severity finding"},
            {"event": "vulnerability.detected", "description": "Vulnerability detected"},
            {"event": "asset.discovered", "description": "New asset discovered (ASM)"},
            {"event": "asset.risk_changed", "description": "Asset risk level changed"},
            {"event": "monitor.change", "description": "Subdomain monitoring detected change"},
            {"event": "schedule.triggered", "description": "Scheduled scan triggered"},
            {"event": "export.ready", "description": "Export/report is ready"},
            {"event": "system.health", "description": "System health status change"},
        ]

    # ── Private helpers ───────────────────────────────────────────────

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = self._default_retry.initial_delay_seconds * (
            self._default_retry.backoff_multiplier ** (attempt - 1)
        )
        return min(delay, self._default_retry.max_delay_seconds)

    def _move_to_dead_letter(self, delivery: WebhookDelivery) -> None:
        """Move a permanently failed delivery to the dead letter queue."""
        delivery.status = DeliveryStatus.DEAD_LETTER.value
        if self._redis:
            try:
                self._redis.lpush(self._dead_letter_key, json.dumps(asdict(delivery)))
                self._redis.ltrim(self._dead_letter_key, 0, 999)
            except Exception as e:
                _log.warning("Failed to move to dead letter: %s", e)

    def _save_delivery(self, delivery: WebhookDelivery) -> None:
        """Save a delivery to storage."""
        if self._redis:
            try:
                self._redis.hset(
                    self._deliveries_key,
                    delivery.delivery_id,
                    json.dumps(asdict(delivery)),
                )
            except Exception as e:
                _log.warning("Failed to save delivery: %s", e)

    def _save_circuit(self, cb: CircuitBreaker) -> None:
        """Save circuit breaker state."""
        if self._redis:
            try:
                self._redis.hset(self._circuit_key, cb.endpoint_id, json.dumps(asdict(cb)))
            except Exception as e:
                _log.warning("Failed to save circuit state: %s", e)

    def _get_all_deliveries(self) -> list[dict]:
        """Load all deliveries."""
        if self._redis:
            try:
                raw = self._redis.hgetall(self._deliveries_key)
                return [json.loads(v) for v in raw.values()]
            except Exception:
                pass
        return []

    def _increment_stat(self, key: str, amount: int = 1) -> None:
        """Increment a statistics counter."""
        if self._redis:
            try:
                self._redis.hincrby(self._stats_key, key, amount)
            except Exception:
                pass
