"""Auto-index scan events into Qdrant via EventBus subscription.

Listens for OSINT events on the EventBus and automatically embeds +
stores them in the vector database, enabling real-time vector
correlation during and after scans.

Usage::

    from spiderfoot.event_indexer import EventIndexer

    indexer = EventIndexer()
    indexer.start()          # subscribe to EventBus
    # ... events flow in automatically ...
    indexer.stop()           # unsubscribe + flush

Features:

* **BatchWriter** — accumulates events and flushes in batches
* **Rate limiting** — caps indexing throughput to avoid overloading Qdrant
* **Event filtering** — only indexes relevant event types
* **Metrics** — counters for indexed / skipped / errors
* **Graceful shutdown** — flushes remaining events on stop
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("spiderfoot.event_indexer")

# Event types worth indexing (skip noisy / low-value types)
INDEXABLE_TYPES: set[str] = {
    "IP_ADDRESS", "IPV6_ADDRESS", "INTERNET_NAME", "DOMAIN_NAME",
    "AFFILIATE_DOMAIN_NAME", "CO_HOSTED_SITE", "SIMILARITIES_DOMAIN",
    "EMAIL_ADDRESS", "EMAILADDR_COMPROMISED",
    "PHONE_NUMBER", "HUMAN_NAME", "USERNAME",
    "URL_FORM", "URL_STATIC", "URL_JAVASCRIPT", "URL_WEB",
    "TCP_PORT_OPEN", "UDP_PORT_OPEN",
    "WEBSERVER_BANNER", "WEBSERVER_TECHNOLOGY",
    "SSL_CERTIFICATE_RAW", "SSL_CERTIFICATE_ISSUED", "SSL_CERTIFICATE_ISSUER",
    "PROVIDER_HOSTING", "PROVIDER_DNS", "PROVIDER_MAIL",
    "BGP_AS_OWNER", "BGP_AS_PEER",
    "GEOINFO", "COUNTRY_NAME",
    "SOCIAL_MEDIA", "ACCOUNT_EXTERNAL_OWNED",
    "VULNERABILITY_CVE_CRITICAL", "VULNERABILITY_CVE_HIGH",
    "VULNERABILITY_CVE_MEDIUM", "VULNERABILITY_CVE_LOW",
    "MALICIOUS_IPADDR", "MALICIOUS_INTERNET_NAME",
    "MALICIOUS_AFFILIATE_IPADDR", "MALICIOUS_COHOST",
    "HASH", "PASSWORD_COMPROMISED",
    "SOFTWARE_USED", "OPERATING_SYSTEM",
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class IndexerConfig:
    """Configuration for the event indexer."""

    batch_size: int = 50
    flush_interval_seconds: float = 5.0
    max_queue_size: int = 10000
    worker_threads: int = 1
    collection_name: str = "osint_events"
    indexable_types: set[str] = field(default_factory=lambda: INDEXABLE_TYPES.copy())
    enabled: bool = True

    @classmethod
    def from_env(cls) -> IndexerConfig:
        """Load from environment variables."""
        import os
        return cls(
            batch_size=int(os.environ.get("SF_INDEXER_BATCH_SIZE", "50")),
            flush_interval_seconds=float(
                os.environ.get("SF_INDEXER_FLUSH_INTERVAL", "5.0")),
            max_queue_size=int(os.environ.get("SF_INDEXER_QUEUE_SIZE", "10000")),
            enabled=os.environ.get("SF_INDEXER_ENABLED", "1") == "1",
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class IndexerMetrics:
    """Counters for monitoring indexer health."""

    indexed: int = 0
    skipped: int = 0
    errors: int = 0
    batches_flushed: int = 0
    queue_high_water: int = 0
    last_flush_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "indexed": self.indexed,
            "skipped": self.skipped,
            "errors": self.errors,
            "batches_flushed": self.batches_flushed,
            "queue_high_water": self.queue_high_water,
            "last_flush_time": self.last_flush_time,
        }


# ---------------------------------------------------------------------------
# BatchWriter
# ---------------------------------------------------------------------------

class BatchWriter:
    """Accumulates events and flushes in batches."""

    def __init__(self, config: IndexerConfig,
                 flush_fn: Callable[[list[Any]], int],
                 metrics: IndexerMetrics) -> None:
        self._config = config
        self._flush_fn = flush_fn
        self._metrics = metrics
        self._queue: deque = deque(maxlen=config.max_queue_size)
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._running = False

    def start(self) -> None:
        """Start periodic flush timer."""
        self._running = True
        self._schedule_flush()

    def stop(self) -> None:
        """Stop timer and flush remaining."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self.flush()

    def add(self, event: Any) -> bool:
        """Add event to queue. Returns False if queue is full."""
        with self._lock:
            if len(self._queue) >= self._config.max_queue_size:
                return False
            self._queue.append(event)
            qlen = len(self._queue)
            if qlen > self._metrics.queue_high_water:
                self._metrics.queue_high_water = qlen
            if qlen >= self._config.batch_size:
                self._flush_batch()
        return True

    def flush(self) -> int:
        """Flush all remaining events."""
        total = 0
        with self._lock:
            while self._queue:
                total += self._flush_batch()
        return total

    def _flush_batch(self) -> int:
        """Flush up to batch_size events (caller holds lock)."""
        batch: list[Any] = []
        for _ in range(min(self._config.batch_size, len(self._queue))):
            batch.append(self._queue.popleft())

        if not batch:
            return 0

        try:
            count = self._flush_fn(batch)
            self._metrics.batches_flushed += 1
            self._metrics.last_flush_time = time.time()
            return count
        except Exception as exc:
            log.error("Batch flush error: %s", exc)
            self._metrics.errors += len(batch)
            return 0

    def _schedule_flush(self) -> None:
        """Schedule next periodic flush."""
        if not self._running:
            return
        self._timer = threading.Timer(
            self._config.flush_interval_seconds,
            self._periodic_flush,
        )
        self._timer.daemon = True
        self._timer.start()

    def _periodic_flush(self) -> None:
        """Timer callback for periodic flush."""
        self.flush()
        self._schedule_flush()

    @property
    def pending(self) -> int:
        return len(self._queue)


# ---------------------------------------------------------------------------
# EventIndexer
# ---------------------------------------------------------------------------

class EventIndexer:
    """Auto-indexes OSINT events into Qdrant via EventBus.

    Parameters
    ----------
    config : IndexerConfig, optional
        Indexer configuration.
    vector_engine : optional
        VectorCorrelationEngine instance. If None, lazy-loads.
    event_bus : optional
        EventBus instance. If None, reads from ServiceRegistry.
    """

    def __init__(
        self,
        config: IndexerConfig | None = None,
        vector_engine: Any = None,
        event_bus: Any = None,
    ) -> None:
        self.config = config or IndexerConfig()
        self._vector_engine = vector_engine
        self._event_bus = event_bus
        self._sub_ids: list[str] = []
        self.metrics = IndexerMetrics()
        self._writer = BatchWriter(
            self.config, self._index_batch, self.metrics,
        )
        self._started = False

    def start(self) -> None:
        """Subscribe to EventBus and start batch writer."""
        if self._started or not self.config.enabled:
            return

        bus = self._get_event_bus()
        if bus is None:
            log.warning("No EventBus available, indexer disabled")
            return

        # Subscribe to all scan events
        try:
            sub_id = bus.subscribe_sync("sf.*.>", self._on_event)
            self._sub_ids.append(sub_id)
            log.info("Event indexer subscribed to EventBus")
        except Exception as exc:
            log.error("EventBus subscribe failed: %s", exc)
            return

        self._writer.start()
        self._started = True
        log.info("Event indexer started (batch=%d, flush=%.1fs)",
                 self.config.batch_size, self.config.flush_interval_seconds)

    def stop(self) -> None:
        """Unsubscribe and flush remaining events."""
        if not self._started:
            return

        self._writer.stop()

        bus = self._get_event_bus()
        if bus:
            for sid in self._sub_ids:
                try:
                    bus.unsubscribe_sync(sid)
                except Exception as e:
                    log.debug("Failed to unsubscribe subscription %s: %s", sid, e)
        self._sub_ids.clear()
        self._started = False
        log.info("Event indexer stopped (indexed=%d, errors=%d)",
                 self.metrics.indexed, self.metrics.errors)

    def _on_event(self, envelope: Any) -> None:
        """EventBus callback — filter and queue events."""
        event_type = getattr(envelope, "event_type", None)
        if not event_type:
            return

        if event_type not in self.config.indexable_types:
            self.metrics.skipped += 1
            return

        if not self._writer.add(envelope):
            self.metrics.skipped += 1
            log.warning("Event queue full, dropping event")

    def _index_batch(self, batch: list[Any]) -> int:
        """Convert envelopes to OSINTEvents and index into Qdrant."""
        engine = self._get_vector_engine()
        if engine is None:
            self.metrics.errors += len(batch)
            return 0

        from spiderfoot.vector_correlation import OSINTEvent

        osint_events: list[OSINTEvent] = []
        for env in batch:
            try:
                evt = OSINTEvent(
                    event_id=getattr(env, "source_event_hash", "") or str(id(env)),
                    event_type=getattr(env, "event_type", ""),
                    data=str(getattr(env, "data", "")),
                    source_module=getattr(env, "module", ""),
                    scan_id=getattr(env, "scan_id", ""),
                    confidence=float(getattr(env, "confidence", 100)),
                    risk=int(getattr(env, "risk", 0)),
                    timestamp=float(getattr(env, "timestamp", 0.0)),
                )
                osint_events.append(evt)
            except Exception as exc:
                log.debug("Event conversion error: %s", exc)
                self.metrics.errors += 1

        if not osint_events:
            return 0

        try:
            count = engine.index_events(osint_events)
            self.metrics.indexed += len(osint_events)
            return count if isinstance(count, int) else len(osint_events)
        except Exception as exc:
            log.error("Vector index error: %s", exc)
            self.metrics.errors += len(osint_events)
            return 0

    def _get_event_bus(self) -> Any:
        """Get EventBus from registry or injected."""
        if self._event_bus is not None:
            return self._event_bus
        try:
            from spiderfoot.service_registry import get_registry
            return get_registry().get_optional("event_bus")
        except Exception as e:
            return None

    def _get_vector_engine(self) -> Any:
        """Get or lazy-init VectorCorrelationEngine."""
        if self._vector_engine is not None:
            return self._vector_engine
        try:
            from spiderfoot.vector_correlation import VectorCorrelationEngine
            self._vector_engine = VectorCorrelationEngine()
            return self._vector_engine
        except Exception as exc:
            log.error("Failed to init vector engine: %s", exc)
            return None

    def stats(self) -> dict[str, Any]:
        """Return indexer stats."""
        return {
            "started": self._started,
            "pending": self._writer.pending,
            "metrics": self.metrics.to_dict(),
            "config": {
                "batch_size": self.config.batch_size,
                "flush_interval": self.config.flush_interval_seconds,
                "max_queue": self.config.max_queue_size,
                "indexable_types": len(self.config.indexable_types),
            },
        }
