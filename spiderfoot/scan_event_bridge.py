"""
Scan Event Bridge — routes live scan events to the EventRelay.

Provides a lightweight, synchronous adapter that sits in the
scanner's ``waitForThreads()`` dispatch loop and forwards each
``SpiderFootEvent`` to the ``EventRelay`` for real-time WebSocket
delivery, without requiring EventBus or async machinery.

Architecture::

    Scanner.waitForThreads()
        │
        ├─ mod.incomingEventQueue.put(sfEvent)   ← existing module dispatch
        │
        └─ ScanEventBridge.forward(sfEvent)      ← NEW real-time relay
                │
                EventRelay.push_event(scan_id, {...})
                        │
                    asyncio.Queue per WebSocket consumer

Usage::

    from spiderfoot.scan_event_bridge import ScanEventBridge

    bridge = ScanEventBridge(scan_id)
    bridge.start()          # push scan_started via relay

    # In waitForThreads() loop, after dispatching to modules:
    bridge.forward(sfEvent)

    bridge.stop("FINISHED")  # push scan_completed + stats

Features:
  - Zero-dependency on EventBus / async (uses EventRelay.push_event directly)
  - Configurable throttle: batches rapid-fire events (default: 50ms window)
  - Per-event-type counters for scan analytics
  - Graceful: if EventRelay has no consumers nothing is wasted
  - Thread-safe: called from scanner thread, relay is thread-safe
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any

log = logging.getLogger("spiderfoot.scan_event_bridge")


class ScanEventBridge:
    """Bridges live scan events to the EventRelay for real-time delivery.

    Args:
        scan_id: The scan instance ID.
        relay: Optional EventRelay instance (uses singleton if None).
        throttle_ms: Minimum interval (ms) between relay pushes for
            the *same* event type.  Set to 0 to disable throttling.
    """

    def __init__(
        self,
        scan_id: str,
        relay: Any = None,
        throttle_ms: int = 50,
    ) -> None:
        """Initialize the ScanEventBridge."""
        self.scan_id = scan_id
        self._relay = relay
        self._throttle_s = throttle_ms / 1000.0
        self._started = False
        self._stopped = False
        self._lock = threading.Lock()

        # Stats
        self._events_forwarded = 0
        self._events_throttled = 0
        self._events_by_type: dict[str, int] = defaultdict(int)
        self._last_push: dict[str, float] = {}  # event_type -> timestamp
        self._start_time: float = 0.0

    # ------------------------------------------------------------------
    # Lazy relay access
    # ------------------------------------------------------------------

    @property
    def relay(self) -> EventRelay:
        """Return the event relay instance, creating it lazily if needed."""
        if self._relay is None:
            from spiderfoot.event_relay import get_event_relay
            self._relay = get_event_relay()
        return self._relay

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, target: str = "") -> None:
        """Signal scan started — push initial event to relay."""
        with self._lock:
            if self._started:
                return
            self._started = True
            self._start_time = time.time()

        self.relay.push_scan_started(self.scan_id, target=target)
        log.info("ScanEventBridge started for scan %s", self.scan_id)

    def stop(self, status: str = "FINISHED") -> None:
        """Signal scan ended — push completion event with stats."""
        with self._lock:
            if self._stopped:
                return
            self._stopped = True

        duration = time.time() - self._start_time if self._start_time else 0

        self.relay.push_scan_completed(
            self.scan_id,
            status=status,
            event_count=self._events_forwarded,
        )

        # Push a final stats event
        self.relay.push_event(
            self.scan_id,
            {
                "scan_id": self.scan_id,
                "status": status,
                "duration": round(duration, 2),
                "events_forwarded": self._events_forwarded,
                "events_throttled": self._events_throttled,
                "events_by_type": dict(self._events_by_type),
            },
            event_type="scan_stats",
        )

        log.info(
            "ScanEventBridge stopped for scan %s: %d events forwarded, %d throttled",
            self.scan_id, self._events_forwarded, self._events_throttled,
        )

    # ------------------------------------------------------------------
    # Event forwarding
    # ------------------------------------------------------------------

    def forward(self, sf_event: Any) -> bool:
        """Forward a SpiderFootEvent to the EventRelay.

        Converts the event to a dict suitable for JSON serialization
        and pushes it through the relay to all WebSocket consumers.

        Args:
            sf_event: A ``SpiderFootEvent`` instance.

        Returns:
            True if the event was forwarded, False if throttled or
            the bridge is stopped.
        """
        if self._stopped:
            return False

        event_type = getattr(sf_event, 'eventType', 'UNKNOWN')

        # Throttle check
        if self._throttle_s > 0:
            now = time.time()
            last = self._last_push.get(event_type, 0)
            if (now - last) < self._throttle_s:
                with self._lock:
                    self._events_throttled += 1
                    self._events_by_type[event_type] += 1
                return False
            self._last_push[event_type] = now

        # Serialize the SpiderFootEvent to a relay-friendly dict
        event_data = self._serialize_event(sf_event)

        # Push to relay
        self.relay.push_event(
            self.scan_id,
            event_data,
            event_type="new_event",
        )

        with self._lock:
            self._events_forwarded += 1
            self._events_by_type[event_type] += 1

        return True

    def push_status(self, status: str, event_count: int = 0) -> None:
        """Push a scan status update through the relay."""
        if self._stopped:
            return
        self.relay.push_status_update(self.scan_id, status, event_count)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_event(sf_event: Any) -> dict[str, Any]:
        """Convert a SpiderFootEvent to a JSON-safe dict.

        Extracts relevant attributes, truncating large data values
        to prevent WebSocket payload bloat.
        """
        data = getattr(sf_event, 'data', '')
        if isinstance(data, str) and len(data) > 4096:
            data = data[:4096] + '... [truncated]'

        return {
            "event_type": getattr(sf_event, 'eventType', 'UNKNOWN'),
            "module": getattr(sf_event, 'module', ''),
            "data": data,
            "source_event": getattr(sf_event, 'sourceEvent', None) and str(
                getattr(sf_event.sourceEvent, 'eventType', '')),
            "confidence": getattr(sf_event, 'confidence', 100),
            "visibility": getattr(sf_event, 'visibility', 100),
            "risk": getattr(sf_event, 'risk', 0),
            "generated": getattr(sf_event, 'generated', 0),
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
        """Return bridge statistics."""
        with self._lock:
            return {
                "scan_id": self.scan_id,
                "started": self._started,
                "stopped": self._stopped,
                "events_forwarded": self._events_forwarded,
                "events_throttled": self._events_throttled,
                "events_by_type": dict(self._events_by_type),
                "duration": round(time.time() - self._start_time, 2) if self._start_time else 0,
            }


# -----------------------------------------------------------------------
# Per-scan bridge registry
# -----------------------------------------------------------------------

_bridges: dict[str, ScanEventBridge] = {}
_bridges_lock = threading.Lock()


def create_scan_bridge(
    scan_id: str,
    relay: Any = None,
    throttle_ms: int = 50,
) -> ScanEventBridge:
    """Create and register a ScanEventBridge for a scan.

    If a bridge already exists for the scan_id, it is returned as-is.
    """
    with _bridges_lock:
        if scan_id in _bridges:
            return _bridges[scan_id]
        bridge = ScanEventBridge(scan_id, relay=relay, throttle_ms=throttle_ms)
        _bridges[scan_id] = bridge
        log.debug("Bridge created for scan %s", scan_id)
        return bridge


def get_scan_bridge(scan_id: str) -> ScanEventBridge | None:
    """Get the bridge for a scan, or None."""
    with _bridges_lock:
        return _bridges.get(scan_id)


def teardown_scan_bridge(scan_id: str, status: str = "FINISHED") -> None:
    """Stop and remove the bridge for a scan."""
    with _bridges_lock:
        bridge = _bridges.pop(scan_id, None)
    if bridge:
        if not bridge._stopped:
            bridge.stop(status)
        log.debug("Bridge torn down for scan %s", scan_id)


def list_active_bridges() -> list[str]:
    """List scan IDs with active bridges."""
    with _bridges_lock:
        return list(_bridges.keys())


def reset_bridges() -> None:
    """Reset all bridges (for testing)."""
    with _bridges_lock:
        _bridges.clear()
