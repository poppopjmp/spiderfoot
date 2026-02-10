"""
Event Relay — bridges the EventBus to WebSocket/SSE consumers.

Subscribes to EventBus topics and fans out events to registered
consumer queues.  Each WebSocket or SSE endpoint registers a queue
for a specific scan_id, and the relay pushes events into those
queues in real-time.

Architecture::

    EventBus  ─publish─>  EventRelay  ─push─>  asyncio.Queue per consumer
                                                      │
                                               WebSocket handler
                                               SSE generator
                                               (reads from queue)

Usage::

    from spiderfoot.event_relay import get_event_relay

    relay = get_event_relay()

    # In a WebSocket handler:
    queue = relay.register_consumer(scan_id)
    try:
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=30)
            await websocket.send_text(json.dumps(event))
    finally:
        relay.unregister_consumer(scan_id, queue)

    # Pushing events manually (for testing or service_integration):
    relay.push_event(scan_id, {"type": "status_update", ...})
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("spiderfoot.event_relay")


@dataclass
class RelayEvent:
    """A normalized event for delivery to consumers."""
    event_type: str  # e.g. "scan.started", "new_event", "status_update"
    scan_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type,
            "scan_id": self.scan_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class EventRelay:
    """Central relay distributing events to per-scan consumer queues.

    Thread-safe.  Consumer queues are bounded asyncio.Queues with
    configurable max size and overflow policy.

    Args:
        max_queue_size: Maximum items per consumer queue.
            When full, the oldest item is dropped.
    """

    def __init__(self, max_queue_size: int = 500):
        self._lock = threading.Lock()
        self._consumers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._max_queue_size = max_queue_size
        self._eventbus_sub_ids: Dict[str, str] = {}  # scan_id -> subscription_id
        self._eventbus = None
        self._stats = {
            "events_relayed": 0,
            "events_dropped": 0,
            "consumers_registered": 0,
            "consumers_active": 0,
        }

    # -- Consumer management ----------------------------------------------

    def register_consumer(self, scan_id: str) -> asyncio.Queue:
        """Register a consumer queue for a scan.

        Returns an ``asyncio.Queue`` that will receive
        :class:`RelayEvent` dicts.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue_size)
        with self._lock:
            self._consumers[scan_id].add(queue)
            self._stats["consumers_registered"] += 1
            self._stats["consumers_active"] = self._count_active()
        log.info(
            "Consumer registered for scan %s (active=%d)",
            scan_id, self._stats["consumers_active"],
        )
        return queue

    def unregister_consumer(self, scan_id: str, queue: asyncio.Queue) -> None:
        """Remove a consumer queue for a scan."""
        with self._lock:
            consumers = self._consumers.get(scan_id)
            if consumers:
                consumers.discard(queue)
                if not consumers:
                    del self._consumers[scan_id]
            self._stats["consumers_active"] = self._count_active()
        log.info("Consumer unregistered for scan %s", scan_id)

    def _count_active(self) -> int:
        return sum(len(qs) for qs in self._consumers.values())

    # -- Event push -------------------------------------------------------

    def push_event(
        self,
        scan_id: str,
        event: Dict[str, Any],
        event_type: str = "event",
    ) -> int:
        """Push an event to all consumers registered for a scan.

        Args:
            scan_id: The scan to send the event to.
            event: Event data dict.
            event_type: Event classification string.

        Returns:
            Number of consumers that received the event.
        """
        relay_event = RelayEvent(
            event_type=event_type,
            scan_id=scan_id,
            data=event,
        )
        msg = relay_event.to_dict()

        with self._lock:
            queues = list(self._consumers.get(scan_id, set()))

        delivered = 0
        for q in queues:
            try:
                q.put_nowait(msg)
                delivered += 1
            except asyncio.QueueFull:
                # Drop oldest to make room
                try:
                    q.get_nowait()
                    q.put_nowait(msg)
                    delivered += 1
                    self._stats["events_dropped"] += 1
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    self._stats["events_dropped"] += 1

        if delivered > 0:
            self._stats["events_relayed"] += 1

        return delivered

    def push_event_all(self, event: Dict[str, Any], event_type: str = "broadcast") -> int:
        """Push an event to ALL consumers regardless of scan_id."""
        with self._lock:
            all_scan_ids = list(self._consumers.keys())

        total = 0
        for sid in all_scan_ids:
            total += self.push_event(sid, event, event_type)
        return total

    # -- EventBus integration ---------------------------------------------

    def wire_eventbus(self, eventbus) -> None:
        """Connect to an EventBus instance for automatic forwarding.

        Subscribes to all scan events and relays them to consumers.

        Args:
            eventbus: An :class:`EventBus` instance (from spiderfoot.eventbus.base).
        """
        self._eventbus = eventbus
        log.info("EventRelay wired to EventBus")

    async def _on_eventbus_event(self, envelope) -> None:
        """EventBus callback — converts envelope to relay event."""
        try:
            event_data = {
                "event_type": envelope.event_type,
                "module": envelope.module,
                "data": envelope.data if isinstance(envelope.data, (str, dict, list)) else str(envelope.data),
                "confidence": getattr(envelope, "confidence", 100),
                "risk": getattr(envelope, "risk", 0),
            }
            self.push_event(
                scan_id=envelope.scan_id,
                event=event_data,
                event_type="new_event",
            )
        except Exception as e:
            log.error("Error relaying EventBus event: %s", e)

    async def subscribe_scan(self, scan_id: str) -> Optional[str]:
        """Subscribe to EventBus events for a specific scan.

        Only subscribes if not already subscribed and EventBus is wired.
        Returns the subscription ID, or None if not wired.
        """
        if not self._eventbus:
            return None

        with self._lock:
            if scan_id in self._eventbus_sub_ids:
                return self._eventbus_sub_ids[scan_id]

        try:
            topic = f"{self._eventbus.config.channel_prefix}.{scan_id}.>"
            sub_id = await self._eventbus.subscribe(
                topic, self._on_eventbus_event,
            )
            with self._lock:
                self._eventbus_sub_ids[scan_id] = sub_id
            log.info("Subscribed to EventBus for scan %s", scan_id)
            return sub_id
        except Exception as e:
            log.warning("Failed to subscribe to EventBus for scan %s: %s", scan_id, e)
            return None

    async def unsubscribe_scan(self, scan_id: str) -> None:
        """Unsubscribe from EventBus events for a scan."""
        if not self._eventbus:
            return

        with self._lock:
            sub_id = self._eventbus_sub_ids.pop(scan_id, None)

        if sub_id:
            try:
                await self._eventbus.unsubscribe(sub_id)
                log.info("Unsubscribed from EventBus for scan %s", scan_id)
            except Exception as e:
                log.warning("Failed to unsubscribe: %s", e)

    # -- Scan lifecycle helpers -------------------------------------------

    def push_scan_started(self, scan_id: str, target: str = "") -> int:
        """Convenience: push a scan.started event."""
        return self.push_event(
            scan_id,
            {"scan_id": scan_id, "target": target, "status": DB_STATUS_STARTED},
            event_type="scan_started",
        )

    def push_scan_completed(
        self, scan_id: str, status: str = DB_STATUS_FINISHED, event_count: int = 0,
    ) -> int:
        """Convenience: push a scan completed/error event."""
        return self.push_event(
            scan_id,
            {"scan_id": scan_id, "status": status, "event_count": event_count},
            event_type="scan_completed",
        )

    def push_status_update(
        self, scan_id: str, status: str, event_count: int = 0,
    ) -> int:
        """Convenience: push a status update."""
        return self.push_event(
            scan_id,
            {"scan_id": scan_id, "status": status, "event_count": event_count},
            event_type="status_update",
        )
from spiderfoot.scan_state_map import (
    DB_STATUS_FINISHED,
    DB_STATUS_STARTED,
)


    # -- Query ------------------------------------------------------------

    def has_consumers(self, scan_id: str) -> bool:
        """Check if any consumers are registered for a scan."""
        with self._lock:
            return bool(self._consumers.get(scan_id))

    def active_scans(self) -> List[str]:
        """List scan IDs with active consumers."""
        with self._lock:
            return list(self._consumers.keys())

    def consumer_count(self, scan_id: Optional[str] = None) -> int:
        """Count active consumers, optionally for a specific scan."""
        with self._lock:
            if scan_id:
                return len(self._consumers.get(scan_id, set()))
            return self._count_active()

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            s = dict(self._stats)
            s["active_scans"] = list(self._consumers.keys())
            s["eventbus_wired"] = self._eventbus is not None
        return s


# -----------------------------------------------------------------------
# Singleton
# -----------------------------------------------------------------------

_relay: Optional[EventRelay] = None
_relay_lock = threading.Lock()


def get_event_relay() -> EventRelay:
    """Get or create the global EventRelay singleton."""
    global _relay
    if _relay is None:
        with _relay_lock:
            if _relay is None:
                _relay = EventRelay()
    return _relay


def reset_event_relay() -> None:
    """Reset the singleton (for testing)."""
    global _relay
    with _relay_lock:
        _relay = None
