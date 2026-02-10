"""
Scan lifecycle event hooks.

Automatically fires EventBus events when scans transition between
lifecycle states (created → starting → running → finished/aborted/error).
This enables downstream consumers (webhooks, notifications, metrics,
audit logging) to react to scan state changes without polling.

Events published on the ``scan.lifecycle`` topic:
    - ``scan.created``      — new scan instance registered
    - ``scan.started``      — scan execution begins
    - ``scan.completed``    — scan finished successfully
    - ``scan.aborted``      — scan was manually stopped
    - ``scan.failed``       — scan terminated with error
    - ``scan.deleted``      — scan and/or data removed
    - ``scan.archived``     — scan moved to archive
    - ``scan.unarchived``   — scan restored from archive

Usage:
    from spiderfoot.scan_hooks import ScanLifecycleHooks, get_scan_hooks

    hooks = get_scan_hooks()
    hooks.on_created(scan_id, name, target)
    hooks.on_completed(scan_id)

    # Custom listener
    hooks.add_listener(my_callback)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger(__name__)


class ScanEvent(str, Enum):
    """Scan lifecycle event types."""
    CREATED = "scan.created"
    STARTED = "scan.started"
    COMPLETED = "scan.completed"
    ABORTED = "scan.aborted"
    FAILED = "scan.failed"
    DELETED = "scan.deleted"
    ARCHIVED = "scan.archived"
    UNARCHIVED = "scan.unarchived"


@dataclass
class ScanLifecycleEvent:
    """Payload for a scan lifecycle event."""
    event: ScanEvent
    scan_id: str
    timestamp: float = field(default_factory=time.time)
    name: str | None = None
    target: str | None = None
    status: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event.value,
            "scan_id": self.scan_id,
            "timestamp": self.timestamp,
            "name": self.name,
            "target": self.target,
            "status": self.status,
            "reason": self.reason,
            "metadata": self.metadata,
        }


# Type alias for listeners
ScanLifecycleListener = Callable[[ScanLifecycleEvent], None]

# Topic for EventBus publishing
LIFECYCLE_TOPIC = "scan.lifecycle"


class ScanLifecycleHooks:
    """Fires events when scan state transitions occur.

    Supports two delivery mechanisms:
    1. **EventBus** — publishes to ``scan.lifecycle`` topic (if available)
    2. **Local listeners** — synchronous callbacks registered via ``add_listener()``
    """

    def __init__(self) -> None:
        self._listeners: list[ScanLifecycleListener] = []
        self._event_log: list[ScanLifecycleEvent] = []
        self._max_log_size = 500

    # ── Listener management ──────────────────────────────────────
    def add_listener(self, listener: ScanLifecycleListener) -> None:
        """Register a callback for all scan lifecycle events."""
        self._listeners.append(listener)

    def remove_listener(self, listener: ScanLifecycleListener) -> None:
        """Unregister a previously added listener."""
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    # ── Event firing ─────────────────────────────────────────────
    def _fire(self, event: ScanLifecycleEvent) -> None:
        """Dispatch an event to EventBus and local listeners."""
        # Log internally
        self._event_log.append(event)
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]

        log.info("Scan lifecycle: %s scan_id=%s", event.event.value, event.scan_id)

        # Publish to EventBus
        self._publish_to_eventbus(event)

        # Notify local listeners
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as exc:
                log.warning(
                    "Scan lifecycle listener %s failed: %s",
                    getattr(listener, "__name__", listener),
                    exc,
                )

    def _publish_to_eventbus(self, event: ScanLifecycleEvent) -> None:
        """Best-effort publish to the EventBus."""
        try:
            from spiderfoot.service_registry import ServiceRegistry
            registry = ServiceRegistry()
            bus = registry.get_optional("event_bus")
            if bus is None:
                return
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # Already in async context — schedule
                loop.create_task(bus.publish(LIFECYCLE_TOPIC, event.to_dict()))
            except RuntimeError:
                asyncio.run(bus.publish(LIFECYCLE_TOPIC, event.to_dict()))
        except Exception as exc:
            log.debug("EventBus publish skipped: %s", exc)

    # ── Convenience methods ──────────────────────────────────────
    def on_created(
        self, scan_id: str, name: str = "", target: str = "", **metadata: Any
    ) -> None:
        self._fire(ScanLifecycleEvent(
            event=ScanEvent.CREATED,
            scan_id=scan_id,
            name=name,
            target=target,
            status="CREATED",
            metadata=metadata,
        ))

    def on_started(self, scan_id: str, **metadata: Any) -> None:
        self._fire(ScanLifecycleEvent(
            event=ScanEvent.STARTED,
            scan_id=scan_id,
            status=DB_STATUS_STARTED,
            metadata=metadata,
        ))

    def on_completed(self, scan_id: str, **metadata: Any) -> None:
        self._fire(ScanLifecycleEvent(
            event=ScanEvent.COMPLETED,
            scan_id=scan_id,
            status=DB_STATUS_FINISHED,
            metadata=metadata,
        ))

    def on_aborted(self, scan_id: str, reason: str = "", **metadata: Any) -> None:
        self._fire(ScanLifecycleEvent(
            event=ScanEvent.ABORTED,
            scan_id=scan_id,
            status=DB_STATUS_ABORTED,
            reason=reason,
            metadata=metadata,
        ))

    def on_failed(self, scan_id: str, reason: str = "", **metadata: Any) -> None:
        self._fire(ScanLifecycleEvent(
            event=ScanEvent.FAILED,
            scan_id=scan_id,
            status=DB_STATUS_ERROR_FAILED,
            reason=reason,
            metadata=metadata,
        ))

    def on_deleted(self, scan_id: str, **metadata: Any) -> None:
        self._fire(ScanLifecycleEvent(
            event=ScanEvent.DELETED,
            scan_id=scan_id,
            status="DELETED",
            metadata=metadata,
        ))

    def on_archived(self, scan_id: str, **metadata: Any) -> None:
        self._fire(ScanLifecycleEvent(
            event=ScanEvent.ARCHIVED,
            scan_id=scan_id,
            status="ARCHIVED",
            metadata=metadata,
        ))

    def on_unarchived(self, scan_id: str, **metadata: Any) -> None:
        self._fire(ScanLifecycleEvent(
            event=ScanEvent.UNARCHIVED,
            scan_id=scan_id,
            status="UNARCHIVED",
            metadata=metadata,
        ))
from spiderfoot.scan_state_map import (
    DB_STATUS_ABORTED,
    DB_STATUS_ERROR_FAILED,
    DB_STATUS_FINISHED,
    DB_STATUS_STARTED,
)


    # ── Query ────────────────────────────────────────────────────
    def get_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent lifecycle events."""
        return [e.to_dict() for e in self._event_log[-limit:]]

    def get_events_for_scan(self, scan_id: str) -> list[dict[str, Any]]:
        """Return all lifecycle events for a specific scan."""
        return [e.to_dict() for e in self._event_log if e.scan_id == scan_id]

    def stats(self) -> dict[str, Any]:
        """Summary statistics."""
        counts: dict[str, int] = {}
        for e in self._event_log:
            counts[e.event.value] = counts.get(e.event.value, 0) + 1
        return {
            "total_events": len(self._event_log),
            "listeners": len(self._listeners),
            "event_counts": counts,
        }


# ── Singleton ────────────────────────────────────────────────────────

_instance: ScanLifecycleHooks | None = None


def get_scan_hooks() -> ScanLifecycleHooks:
    """Get or create the global ScanLifecycleHooks instance."""
    global _instance
    if _instance is None:
        _instance = ScanLifecycleHooks()
    return _instance
