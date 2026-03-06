"""Persistent event storage for SpiderFoot scan events.

Provides an in-memory event store with querying, indexing, retention
policies and serialization support. Designed for future backend swapping
(PostgreSQL, Redis, etc.) without API changes.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventPriority(Enum):
    """Priority levels for stored events."""
    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1
    INFO = 0


@dataclass
class StoredEvent:
    """An event persisted in the store."""
    event_id: str
    scan_id: str
    event_type: str
    module: str
    data: Any
    source_event_id: str = ""
    priority: EventPriority = EventPriority.INFO
    timestamp: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_tag(self, tag: str) -> "StoredEvent":
        """Add a tag to the event if not already present."""
        if tag not in self.tags:
            self.tags.append(tag)
        return self

    def set_meta(self, key: str, value: Any) -> "StoredEvent":
        """Set a metadata key-value pair on the event."""
        self.metadata[key] = value
        return self

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "event_id": self.event_id,
            "scan_id": self.scan_id,
            "event_type": self.event_type,
            "module": self.module,
            "data": str(self.data) if not isinstance(self.data, (str, int, float, bool, type(None))) else self.data,
            "source_event_id": self.source_event_id,
            "priority": self.priority.name,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class EventQuery:
    """Query parameters for searching events."""
    scan_id: str | None = None
    event_type: str | None = None
    module: str | None = None
    min_priority: EventPriority | None = None
    tag: str | None = None
    since: float | None = None
    until: float | None = None
    limit: int = 0  # 0 = no limit
    offset: int = 0


class RetentionPolicy:
    """Policy for automatic event cleanup.

    Args:
        max_events: Maximum events to retain (0=unlimited).
        max_age_seconds: Maximum event age in seconds (0=unlimited).
        min_priority: Minimum priority to retain (events below are purged first).
    """

    def __init__(
        self,
        max_events: int = 0,
        max_age_seconds: float = 0,
        min_priority: EventPriority = EventPriority.INFO,
    ) -> None:
        """Initialize the RetentionPolicy."""
        self.max_events = max_events
        self.max_age_seconds = max_age_seconds
        self.min_priority = min_priority

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "max_events": self.max_events,
            "max_age_seconds": self.max_age_seconds,
            "min_priority": self.min_priority.name,
        }


class EventStore:
    """In-memory event store with indexing and retention.

    Args:
        retention: Retention policy for automatic cleanup.
    """

    def __init__(self, retention: RetentionPolicy | None = None) -> None:
        """Initialize the EventStore."""
        self._events: dict[str, StoredEvent] = {}  # event_id -> event
        self._scan_index: dict[str, list[str]] = {}  # scan_id -> [event_ids]
        self._type_index: dict[str, list[str]] = {}  # event_type -> [event_ids]
        self._module_index: dict[str, list[str]] = {}  # module -> [event_ids]
        self._retention = retention or RetentionPolicy()
        self._lock = threading.RLock()
        self._event_counter = 0

    def store(self, event: StoredEvent) -> str:
        """Store an event. Returns the event_id."""
        with self._lock:
            self._events[event.event_id] = event

            # Update indexes
            self._scan_index.setdefault(event.scan_id, []).append(event.event_id)
            self._type_index.setdefault(event.event_type, []).append(event.event_id)
            self._module_index.setdefault(event.module, []).append(event.event_id)
            self._event_counter += 1

            # Apply retention
            self._apply_retention()

            return event.event_id

    def get(self, event_id: str) -> StoredEvent | None:
        """Get a single event by ID."""
        return self._events.get(event_id)

    def query(self, q: EventQuery) -> list[StoredEvent]:
        """Query events with filters."""
        with self._lock:
            # Start with candidate set
            if q.scan_id and q.scan_id in self._scan_index:
                candidates = [self._events[eid] for eid in self._scan_index[q.scan_id] if eid in self._events]
            elif q.event_type and q.event_type in self._type_index:
                candidates = [self._events[eid] for eid in self._type_index[q.event_type] if eid in self._events]
            elif q.module and q.module in self._module_index:
                candidates = [self._events[eid] for eid in self._module_index[q.module] if eid in self._events]
            else:
                candidates = list(self._events.values())

            # Apply filters
            results = []
            for e in candidates:
                if q.scan_id and e.scan_id != q.scan_id:
                    continue
                if q.event_type and e.event_type != q.event_type:
                    continue
                if q.module and e.module != q.module:
                    continue
                if q.min_priority and e.priority.value < q.min_priority.value:
                    continue
                if q.tag and q.tag not in e.tags:
                    continue
                if q.since and e.timestamp < q.since:
                    continue
                if q.until and e.timestamp > q.until:
                    continue
                results.append(e)

            # Sort by timestamp
            results.sort(key=lambda e: e.timestamp)

            # Apply offset and limit
            if q.offset > 0:
                results = results[q.offset:]
            if q.limit > 0:
                results = results[:q.limit]

            return results

    def delete(self, event_id: str) -> bool:
        """Delete a single event."""
        with self._lock:
            event = self._events.pop(event_id, None)
            if event is None:
                return False
            self._remove_from_index(self._scan_index, event.scan_id, event_id)
            self._remove_from_index(self._type_index, event.event_type, event_id)
            self._remove_from_index(self._module_index, event.module, event_id)
            return True

    def delete_scan(self, scan_id: str) -> int:
        """Delete all events for a scan. Returns count deleted."""
        with self._lock:
            event_ids = self._scan_index.pop(scan_id, [])
            count = 0
            for eid in event_ids:
                event = self._events.pop(eid, None)
                if event:
                    self._remove_from_index(self._type_index, event.event_type, eid)
                    self._remove_from_index(self._module_index, event.module, eid)
                    count += 1
            return count

    def count(self, scan_id: str | None = None) -> int:
        """Count events, optionally filtered by scan."""
        if scan_id:
            return len(self._scan_index.get(scan_id, []))
        return len(self._events)

    def clear(self) -> None:
        """Remove all events."""
        with self._lock:
            self._events.clear()
            self._scan_index.clear()
            self._type_index.clear()
            self._module_index.clear()

    def get_event_types(self, scan_id: str | None = None) -> list[str]:
        """Get distinct event types, optionally for a scan."""
        if scan_id:
            events = self.query(EventQuery(scan_id=scan_id))
            return sorted({e.event_type for e in events})
        return sorted(self._type_index.keys())

    def get_modules(self, scan_id: str | None = None) -> list[str]:
        """Get distinct modules, optionally for a scan."""
        if scan_id:
            events = self.query(EventQuery(scan_id=scan_id))
            return sorted({e.module for e in events})
        return sorted(self._module_index.keys())

    def _remove_from_index(self, index: dict, key: str, event_id: str):
        if key in index:
            try:
                index[key].remove(event_id)
            except ValueError:
                pass
            if not index[key]:
                del index[key]

    def _apply_retention(self):
        """Apply retention policy."""
        now = time.time()

        # Remove expired events
        if self._retention.max_age_seconds > 0:
            expired = [
                eid for eid, e in self._events.items()
                if (now - e.timestamp) > self._retention.max_age_seconds
            ]
            for eid in expired:
                self.delete(eid)

        # Remove excess events (lowest priority first)
        if self._retention.max_events > 0 and len(self._events) > self._retention.max_events:
            sorted_events = sorted(
                self._events.values(),
                key=lambda e: (e.priority.value, e.timestamp),
            )
            excess = len(self._events) - self._retention.max_events
            for e in sorted_events[:excess]:
                self.delete(e.event_id)

    def summary(self) -> dict:
        """Return summary statistics of the event store."""
        return {
            "total_events": len(self._events),
            "total_stored": self._event_counter,
            "scans": len(self._scan_index),
            "event_types": len(self._type_index),
            "modules": len(self._module_index),
        }

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "summary": self.summary(),
            "retention": self._retention.to_dict(),
            "events": [e.to_dict() for e in sorted(self._events.values(), key=lambda e: e.timestamp)],
        }
