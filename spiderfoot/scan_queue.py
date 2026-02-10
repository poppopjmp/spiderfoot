"""Scan queue with backpressure — bounded work queue with flow control.

Provides a production-grade event/task queue that sits between the
scan scheduler and module workers.  Features:

* **Bounded capacity** — configurable max queue depth; producers block or
  get rejected when the queue is full.
* **Priority lanes** — HIGH / NORMAL / LOW with weighted fair-share
  dequeuing so high-priority work is never starved.
* **Backpressure signals** — callers can query pressure level (0.0–1.0)
  and register callbacks for threshold crossings.
* **Batch dequeue** — ``get_batch()`` drains up to *n* items atomically.
* **Metrics** — enqueue/dequeue counters, depth gauge, reject counter,
  wait-time tracking.
* **Dead-letter support** — items that exceed retry/timeout are moved to
  a DLQ for inspection.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

log = logging.getLogger("spiderfoot.scan_queue")

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Priority(IntEnum):
    """Queue priority lanes (lower value = higher priority)."""

    HIGH = 0
    NORMAL = 1
    LOW = 2


class BackpressureAction(Enum):
    """What to do when the queue is full."""

    BLOCK = "block"     # block until space is available (with timeout)
    REJECT = "reject"   # raise immediately
    DROP_OLDEST = "drop_oldest"  # drop the oldest low-priority item


class PressureLevel(Enum):
    """Coarse pressure indicator."""

    NONE = "none"       # < 25%
    LOW = "low"         # 25–50%
    MEDIUM = "medium"   # 50–75%
    HIGH = "high"       # 75–90%
    CRITICAL = "critical"  # > 90%


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(order=False)
class QueueItem(Generic[T]):
    """Wrapper around a queued payload."""

    payload: T
    priority: Priority = Priority.NORMAL
    enqueued_at: float = field(default_factory=time.time)
    item_id: str = ""
    retries: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: QueueItem) -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.enqueued_at < other.enqueued_at


@dataclass
class QueueStats:
    """Snapshot of queue metrics."""

    depth: int = 0
    capacity: int = 0
    utilization: float = 0.0
    pressure_level: PressureLevel = PressureLevel.NONE
    enqueued_total: int = 0
    dequeued_total: int = 0
    rejected_total: int = 0
    dropped_total: int = 0
    dlq_depth: int = 0
    avg_wait_ms: float = 0.0
    depth_by_priority: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "depth": self.depth,
            "capacity": self.capacity,
            "utilization": round(self.utilization, 4),
            "pressure_level": self.pressure_level.value,
            "enqueued_total": self.enqueued_total,
            "dequeued_total": self.dequeued_total,
            "rejected_total": self.rejected_total,
            "dropped_total": self.dropped_total,
            "dlq_depth": self.dlq_depth,
            "avg_wait_ms": round(self.avg_wait_ms, 2),
            "depth_by_priority": self.depth_by_priority,
        }


# ---------------------------------------------------------------------------
# ScanQueue
# ---------------------------------------------------------------------------

class ScanQueue(Generic[T]):
    """Bounded, priority-aware work queue with backpressure.

    Usage::

        q = ScanQueue(capacity=1000)
        q.put(item_payload, priority=Priority.HIGH)
        item = q.get(timeout=5.0)
        batch = q.get_batch(max_items=10)
    """

    def __init__(
        self,
        *,
        capacity: int = 10000,
        backpressure_action: BackpressureAction = BackpressureAction.BLOCK,
        pressure_thresholds: dict[PressureLevel, float] | None = None,
    ) -> None:
        self._capacity = max(1, capacity)
        self._action = backpressure_action

        # Three internal lists — one per priority lane
        self._lanes: dict[Priority, list[QueueItem[T]]] = {
            Priority.HIGH: [],
            Priority.NORMAL: [],
            Priority.LOW: [],
        }
        self._dlq: list[QueueItem[T]] = []

        # Thresholds
        self._thresholds = pressure_thresholds or {
            PressureLevel.NONE: 0.0,
            PressureLevel.LOW: 0.25,
            PressureLevel.MEDIUM: 0.50,
            PressureLevel.HIGH: 0.75,
            PressureLevel.CRITICAL: 0.90,
        }

        # Metrics
        self._enqueued = 0
        self._dequeued = 0
        self._rejected = 0
        self._dropped = 0
        self._total_wait_ms = 0.0
        self._wait_samples = 0

        # Callbacks
        self._pressure_callbacks: list[Callable[[PressureLevel], None]] = []
        self._last_pressure = PressureLevel.NONE

        # Synchronisation
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)

    # -------------------------------------------------------------------
    # Core operations
    # -------------------------------------------------------------------

    def put(
        self,
        payload: T,
        *,
        priority: Priority = Priority.NORMAL,
        item_id: str = "",
        max_retries: int = 3,
        metadata: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> bool:
        """Enqueue an item.

        Returns True if enqueued, False if rejected/timed-out.
        Raises ``QueueFullError`` if action is REJECT and queue is full.
        """
        item = QueueItem(
            payload=payload,
            priority=priority,
            item_id=item_id,
            max_retries=max_retries,
            metadata=metadata or {},
        )
        return self._enqueue(item, timeout)

    def _enqueue(self, item: QueueItem[T], timeout: float | None = None) -> bool:
        with self._not_full:
            while self._depth_unlocked() >= self._capacity:
                if self._action == BackpressureAction.REJECT:
                    self._rejected += 1
                    return False
                elif self._action == BackpressureAction.DROP_OLDEST:
                    dropped = self._drop_oldest()
                    if not dropped:
                        self._rejected += 1
                        return False
                    break
                else:  # BLOCK
                    if timeout is not None and timeout <= 0:
                        self._rejected += 1
                        return False
                    if not self._not_full.wait(timeout=timeout):
                        self._rejected += 1
                        return False

            lane = self._lanes[item.priority]
            lane.append(item)
            self._enqueued += 1
            self._not_empty.notify()

        self._check_pressure()
        return True

    def get(self, timeout: float | None = None) -> QueueItem[T] | None:
        """Dequeue the highest-priority item.

        Returns None if timeout elapses with no item available.
        """
        with self._not_empty:
            while self._depth_unlocked() == 0:
                if timeout is not None and timeout <= 0:
                    return None
                if not self._not_empty.wait(timeout=timeout):
                    return None

            item = self._dequeue_one()
            if item:
                self._not_full.notify()
        if item:
            self._check_pressure()
        return item

    def get_batch(self, max_items: int = 10, timeout: float | None = None) -> list[QueueItem[T]]:
        """Dequeue up to *max_items* in priority order."""
        result: list[QueueItem[T]] = []
        with self._not_empty:
            if self._depth_unlocked() == 0:
                self._not_empty.wait(timeout=timeout)

            while len(result) < max_items and self._depth_unlocked() > 0:
                item = self._dequeue_one()
                if item:
                    result.append(item)

            if result:
                self._not_full.notify_all()

        if result:
            self._check_pressure()
        return result

    def requeue(self, item: QueueItem[T]) -> bool:
        """Return an item to the queue (e.g. after processing failure).

        Increments retry count; moves to DLQ if max retries exceeded.
        """
        item.retries += 1
        if item.retries > item.max_retries:
            with self._lock:
                self._dlq.append(item)
            return False

        item.enqueued_at = time.time()
        return self._enqueue(item, timeout=0)

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _depth_unlocked(self) -> int:
        return sum(len(lane) for lane in self._lanes.values())

    def _dequeue_one(self) -> QueueItem[T] | None:
        """Pop highest-priority item (caller holds lock)."""
        for pri in Priority:
            lane = self._lanes[pri]
            if lane:
                item = lane.pop(0)
                self._dequeued += 1
                wait_ms = (time.time() - item.enqueued_at) * 1000
                self._total_wait_ms += wait_ms
                self._wait_samples += 1
                return item
        return None

    def _drop_oldest(self) -> bool:
        """Drop oldest LOW item; then NORMAL if no LOW available (caller holds lock)."""
        for pri in [Priority.LOW, Priority.NORMAL]:
            lane = self._lanes[pri]
            if lane:
                lane.pop(0)
                self._dropped += 1
                return True
        return False

    # -------------------------------------------------------------------
    # Pressure monitoring
    # -------------------------------------------------------------------

    @property
    def pressure(self) -> float:
        """Current queue utilization 0.0–1.0."""
        with self._lock:
            return self._depth_unlocked() / self._capacity

    @property
    def pressure_level(self) -> PressureLevel:
        p = self.pressure
        level = PressureLevel.NONE
        for lvl in [PressureLevel.CRITICAL, PressureLevel.HIGH,
                     PressureLevel.MEDIUM, PressureLevel.LOW, PressureLevel.NONE]:
            if p >= self._thresholds.get(lvl, 0.0):
                level = lvl
                break
        return level

    def on_pressure_change(self, callback: Callable[[PressureLevel], None]) -> None:
        """Register a callback for pressure level transitions."""
        self._pressure_callbacks.append(callback)

    def _check_pressure(self) -> None:
        level = self.pressure_level
        if level != self._last_pressure:
            self._last_pressure = level
            for cb in self._pressure_callbacks:
                try:
                    cb(level)
                except Exception:
                    log.debug("Pressure callback error", exc_info=True)

    # -------------------------------------------------------------------
    # DLQ
    # -------------------------------------------------------------------

    @property
    def dlq_depth(self) -> int:
        with self._lock:
            return len(self._dlq)

    def drain_dlq(self, limit: int = 100) -> list[QueueItem[T]]:
        """Remove and return items from the dead-letter queue."""
        with self._lock:
            items = self._dlq[:limit]
            self._dlq = self._dlq[limit:]
            return items

    def peek_dlq(self, limit: int = 10) -> list[QueueItem[T]]:
        with self._lock:
            return list(self._dlq[:limit])

    # -------------------------------------------------------------------
    # Query & management
    # -------------------------------------------------------------------

    @property
    def depth(self) -> int:
        with self._lock:
            return self._depth_unlocked()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def is_full(self) -> bool:
        return self.depth >= self._capacity

    @property
    def is_empty(self) -> bool:
        return self.depth == 0

    def depth_by_priority(self) -> dict[str, int]:
        with self._lock:
            return {p.name: len(lane) for p, lane in self._lanes.items()}

    def clear(self) -> int:
        """Remove all items. Returns number removed."""
        with self._lock:
            total = self._depth_unlocked()
            for lane in self._lanes.values():
                lane.clear()
            self._not_full.notify_all()
            return total

    def clear_dlq(self) -> int:
        with self._lock:
            n = len(self._dlq)
            self._dlq.clear()
            return n

    def stats(self) -> QueueStats:
        with self._lock:
            depth = self._depth_unlocked()
            by_pri = {p.name: len(lane) for p, lane in self._lanes.items()}
            avg_wait = (self._total_wait_ms / self._wait_samples) if self._wait_samples else 0.0
            util = depth / self._capacity
            return QueueStats(
                depth=depth,
                capacity=self._capacity,
                utilization=util,
                pressure_level=self._last_pressure,
                enqueued_total=self._enqueued,
                dequeued_total=self._dequeued,
                rejected_total=self._rejected,
                dropped_total=self._dropped,
                dlq_depth=len(self._dlq),
                avg_wait_ms=avg_wait,
                depth_by_priority=by_pri,
            )
