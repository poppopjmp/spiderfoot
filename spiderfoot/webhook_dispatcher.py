"""
Webhook Dispatcher — outbound HTTP notification delivery.

Sends JSON payloads to configured webhook endpoints with HMAC
signing, configurable retries (exponential backoff), and delivery
tracking.

Usage::

    from spiderfoot.webhook_dispatcher import WebhookDispatcher, WebhookConfig

    cfg = WebhookConfig(url="https://example.com/hook", secret="<YOUR_SECRET>")
    dispatcher = WebhookDispatcher()
    record = dispatcher.deliver(cfg, event_type="scan.complete", payload={...})
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

log = logging.getLogger("spiderfoot.webhook")

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import urllib.request
    import urllib.error

    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False


# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------

class DeliveryStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WebhookConfig:
    """Configuration for a single webhook endpoint."""
    webhook_id: str = ""
    url: str = ""
    secret: str = ""  # HMAC-SHA256 signing secret
    headers: dict[str, str] = field(default_factory=dict)
    event_types: list[str] = field(default_factory=list)  # empty = all
    enabled: bool = True
    timeout: float = 10.0
    max_retries: int = 3
    description: str = ""

    def __post_init__(self):
        if not self.webhook_id:
            self.webhook_id = str(uuid.uuid4())

    def matches_event(self, event_type: str) -> bool:
        """Check if this webhook should receive the given event type."""
        if not self.event_types:
            return True  # no filter = all events
        return any(
            event_type == et or event_type.startswith(et + ".")
            for et in self.event_types
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "webhook_id": self.webhook_id,
            "url": self.url,
            "secret": "***" if self.secret else "",
            "headers": {k: "***" for k in self.headers},
            "event_types": list(self.event_types),
            "enabled": self.enabled,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "description": self.description,
        }


@dataclass
class DeliveryRecord:
    """Tracks the outcome of a single webhook delivery attempt."""
    delivery_id: str = ""
    webhook_id: str = ""
    event_type: str = ""
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: int = 0
    status_code: int | None = None
    error: str | None = None
    created_at: float = 0.0
    completed_at: float | None = None
    payload_size: int = 0

    def __post_init__(self):
        if not self.delivery_id:
            self.delivery_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()

    @property
    def elapsed_seconds(self) -> float:
        end = self.completed_at or time.time()
        return round(end - self.created_at, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "webhook_id": self.webhook_id,
            "event_type": self.event_type,
            "status": self.status.value,
            "attempts": self.attempts,
            "status_code": self.status_code,
            "error": self.error,
            "elapsed_seconds": self.elapsed_seconds,
            "payload_size": self.payload_size,
        }


# -----------------------------------------------------------------------
# Dispatcher
# -----------------------------------------------------------------------

class WebhookDispatcher:
    """Sends HTTP POST requests to webhook endpoints.

    Handles HMAC signing, retries with exponential backoff, and
    maintains a bounded delivery history.
    """

    def __init__(self, max_history: int = 200) -> None:
        self._lock = threading.Lock()
        self._history: Deque[DeliveryRecord] = deque(maxlen=max_history)

    def deliver(
        self,
        config: WebhookConfig,
        event_type: str,
        payload: dict[str, Any],
    ) -> DeliveryRecord:
        """Synchronously deliver a payload to a webhook endpoint.

        Returns the ``DeliveryRecord`` capturing the outcome.
        """
        body = json.dumps(
            {
                "event_type": event_type,
                "timestamp": time.time(),
                "payload": payload,
            },
            default=str,
        )
        body_bytes = body.encode("utf-8")

        record = DeliveryRecord(
            webhook_id=config.webhook_id,
            event_type=event_type,
            payload_size=len(body_bytes),
        )

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SpiderFoot-Webhook/1.0",
            "X-SpiderFoot-Event": event_type,
            **config.headers,
        }

        # Propagate request ID for distributed tracing
        try:
            from spiderfoot.request_tracing import get_request_id
            rid = get_request_id()
            if rid:
                headers["X-Request-ID"] = rid
        except ImportError:
            pass

        # HMAC signing
        if config.secret:
            sig = hmac.new(
                config.secret.encode("utf-8"),
                body_bytes,
                hashlib.sha256,
            ).hexdigest()
            headers["X-SpiderFoot-Signature"] = f"sha256={sig}"

        # Retry loop
        last_error = None
        for attempt in range(1, config.max_retries + 1):
            record.attempts = attempt
            record.status = DeliveryStatus.RETRYING

            try:
                status_code = self._send(
                    config.url, body_bytes, headers, config.timeout,
                )
                record.status_code = status_code

                if 200 <= status_code < 300:
                    record.status = DeliveryStatus.SUCCESS
                    record.completed_at = time.time()
                    log.info(
                        "Webhook delivered: %s -> %s (%d)",
                        event_type, config.url, status_code,
                    )
                    break
                else:
                    last_error = f"HTTP {status_code}"
                    log.warning(
                        "Webhook non-2xx: %s -> %s (%d), attempt %d/%d",
                        event_type, config.url, status_code,
                        attempt, config.max_retries,
                    )
            except Exception as e:
                last_error = str(e)
                log.warning(
                    "Webhook error: %s -> %s (%s), attempt %d/%d",
                    event_type, config.url, e,
                    attempt, config.max_retries,
                )

            # Back off before next attempt
            if attempt < config.max_retries:
                backoff = min(2 ** (attempt - 1), 30)
                time.sleep(backoff)

        if record.status != DeliveryStatus.SUCCESS:
            record.status = DeliveryStatus.FAILED
            record.error = last_error
            record.completed_at = time.time()
            log.error(
                "Webhook delivery failed after %d attempts: %s -> %s",
                record.attempts, event_type, config.url,
            )

        with self._lock:
            self._history.append(record)

        return record

    def _send(
        self,
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> int:
        """Low-level HTTP POST.  Uses httpx if available, else urllib."""
        if HAS_HTTPX:
            resp = httpx.post(
                url,
                content=body,
                headers=headers,
                timeout=timeout,
            )
            return resp.status_code

        if HAS_URLLIB:
            req = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.status
            except urllib.error.HTTPError as e:
                return e.code

        raise RuntimeError("No HTTP client available (httpx or urllib)")

    # -- history query ----------------------------------------------------

    def get_history(
        self,
        webhook_id: str | None = None,
        limit: int = 50,
    ) -> list[DeliveryRecord]:
        """Return recent delivery records, optionally filtered."""
        with self._lock:
            records = list(self._history)
        if webhook_id:
            records = [r for r in records if r.webhook_id == webhook_id]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    def clear_history(self) -> int:
        with self._lock:
            count = len(self._history)
            self._history.clear()
        return count

    @property
    def stats(self) -> dict[str, int]:
        """Aggregate delivery stats."""
        with self._lock:
            records = list(self._history)
        total = len(records)
        success = sum(1 for r in records if r.status == DeliveryStatus.SUCCESS)
        failed = sum(1 for r in records if r.status == DeliveryStatus.FAILED)
        return {
            "total_deliveries": total,
            "successful": success,
            "failed": failed,
            "success_rate": round(success / total * 100, 1) if total else 0.0,
        }
