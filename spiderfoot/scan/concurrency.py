# -------------------------------------------------------------------------------
# Name:         Concurrency Utilities
# Purpose:      Concurrency and worker performance utilities for Cycles 91-110.
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2025-07-16
# Copyright:    (c) Agostino Panico 2025
# Licence:      MIT
# -------------------------------------------------------------------------------
"""
Concurrency and worker performance utilities.

Cycle 91:  WorkStealingScheduler — idle workers steal tasks from busy queues
Cycle 92:  ModulePriorityScheduler — schedule modules by declared priority
Cycle 93:  ModulePreloader — eager module import at scan start
Cycle 94:  EventDeduplicator — suppress duplicate events within a time window
Cycle 95:  BackpressureController — rate-limit EventBus when queue depth high
Cycle 96:  WorkerAutoScaler — emit scale-up/down signals based on queue depth
Cycle 97:  TracingMiddleware — OpenTelemetry-compatible span wrapper
Cycle 98:  celery_retry_config — wire retry.py to Celery task autoretry
Cycle 99:  ModuleTimeoutEnforcer — enforce per-module execution timeouts
Cycles 100-110: ScanSplitter — partition large targets for horizontal scaling
"""

from __future__ import annotations

import hashlib
import importlib
import ipaddress
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.scan.concurrency")


# ====================================================================== #
# Cycle 91: Work-Stealing Scheduler                                      #
# ====================================================================== #

class WorkStealingScheduler:
    """Scheduler that lets idle workers steal tasks from busy workers' queues.

    Each registered worker has its own local deque.  When a worker runs
    out of work it iterates over other workers' deques and steals from
    the tail (lock-free on CPython due to the GIL, but we use a lock
    for safety).

    Usage::

        scheduler = WorkStealingScheduler()
        scheduler.register_worker("w1")
        scheduler.register_worker("w2")
        scheduler.submit("w1", task_callable, arg1, arg2)
        task = scheduler.steal("w2")  # w2 steals from w1
    """

    @dataclass
    class _WorkerQueue:
        name: str
        tasks: list = field(default_factory=list)
        lock: threading.Lock = field(default_factory=threading.Lock)
        completed: int = 0
        stolen_from: int = 0
        stolen_to: int = 0

    def __init__(self) -> None:
        self._workers: dict[str, WorkStealingScheduler._WorkerQueue] = {}
        self._lock = threading.Lock()

    def register_worker(self, name: str) -> None:
        """Register a named worker queue."""
        with self._lock:
            if name not in self._workers:
                self._workers[name] = self._WorkerQueue(name=name)

    def unregister_worker(self, name: str) -> None:
        """Remove a worker queue."""
        with self._lock:
            self._workers.pop(name, None)

    @property
    def worker_count(self) -> int:
        return len(self._workers)

    def submit(self, worker_name: str, task: Any) -> bool:
        """Submit a task to a specific worker's queue.

        Args:
            worker_name: Target worker name
            task: Any callable or task object

        Returns:
            True if submitted, False if worker not found
        """
        wq = self._workers.get(worker_name)
        if not wq:
            return False
        with wq.lock:
            wq.tasks.append(task)
        return True

    def get(self, worker_name: str) -> Any | None:
        """Get the next task from a worker's own queue (FIFO).

        Returns:
            The task, or None if the queue is empty
        """
        wq = self._workers.get(worker_name)
        if not wq:
            return None
        with wq.lock:
            if wq.tasks:
                task = wq.tasks.pop(0)
                wq.completed += 1
                return task
        return None

    def steal(self, thief_name: str) -> Any | None:
        """Steal a task from the busiest other worker's queue.

        Steals from the tail (LIFO) of the victim's queue to minimize
        contention with the victim's own FIFO consumption.

        Args:
            thief_name: The worker looking for work

        Returns:
            A stolen task, or None if nothing to steal
        """
        # Find the busiest victim
        victim = None
        max_len = 0
        with self._lock:
            for name, wq in self._workers.items():
                if name == thief_name:
                    continue
                qlen = len(wq.tasks)
                if qlen > max_len:
                    max_len = qlen
                    victim = wq

        if victim is None or max_len == 0:
            return None

        with victim.lock:
            if victim.tasks:
                task = victim.tasks.pop()  # steal from tail
                victim.stolen_from += 1
                thief = self._workers.get(thief_name)
                if thief:
                    thief.stolen_to += 1
                return task
        return None

    def queue_depth(self, worker_name: str) -> int:
        """Return current queue depth for a worker."""
        wq = self._workers.get(worker_name)
        if not wq:
            return 0
        return len(wq.tasks)

    def total_pending(self) -> int:
        """Total tasks pending across all workers."""
        return sum(len(wq.tasks) for wq in self._workers.values())

    def stats(self) -> dict[str, Any]:
        """Return scheduling statistics."""
        result = {}
        for name, wq in self._workers.items():
            result[name] = {
                "pending": len(wq.tasks),
                "completed": wq.completed,
                "stolen_from": wq.stolen_from,
                "stolen_to": wq.stolen_to,
            }
        return result


# ====================================================================== #
# Cycle 92: Module Priority Scheduler                                    #
# ====================================================================== #

class ModulePriorityScheduler:
    """Schedule module execution based on declared priority.

    Lower priority value = higher priority (runs first).  Modules with
    ``priority=1`` run before ``priority=10``.  Equal-priority modules
    are scheduled in registration order.

    Usage::

        sched = ModulePriorityScheduler()
        sched.register("sfp_dnsresolve", priority=1)
        sched.register("sfp_hackertarget", priority=5)
        sched.register("sfp_spider", priority=10)
        order = sched.get_execution_order()
        # ["sfp_dnsresolve", "sfp_hackertarget", "sfp_spider"]
    """

    @dataclass
    class _ModuleEntry:
        name: str
        priority: int
        order: int  # registration order for stable sort

    def __init__(self) -> None:
        self._modules: dict[str, ModulePriorityScheduler._ModuleEntry] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def register(self, module_name: str, priority: int = 5) -> None:
        """Register a module with a priority level (1=highest, 10=lowest)."""
        with self._lock:
            self._modules[module_name] = self._ModuleEntry(
                name=module_name,
                priority=max(1, min(priority, 10)),
                order=self._counter,
            )
            self._counter += 1

    def unregister(self, module_name: str) -> None:
        """Remove a module from the scheduler."""
        with self._lock:
            self._modules.pop(module_name, None)

    def set_priority(self, module_name: str, priority: int) -> bool:
        """Update a module's priority."""
        with self._lock:
            entry = self._modules.get(module_name)
            if entry:
                entry.priority = max(1, min(priority, 10))
                return True
            return False

    def get_execution_order(self) -> list[str]:
        """Return module names sorted by priority (ascending), then by registration order."""
        with self._lock:
            sorted_entries = sorted(
                self._modules.values(),
                key=lambda e: (e.priority, e.order),
            )
            return [e.name for e in sorted_entries]

    def get_priority_groups(self) -> dict[int, list[str]]:
        """Return modules grouped by priority level."""
        groups: dict[int, list[str]] = defaultdict(list)
        with self._lock:
            for entry in sorted(self._modules.values(), key=lambda e: e.order):
                groups[entry.priority].append(entry.name)
        return dict(groups)

    @property
    def module_count(self) -> int:
        return len(self._modules)


# ====================================================================== #
# Cycle 93: Module Preloader                                             #
# ====================================================================== #

class ModulePreloader:
    """Pre-import enabled modules at scan start for faster first-event handling.

    Instead of lazy-loading modules when the first event arrives, this
    preloader imports all enabled modules in parallel.

    Usage::

        preloader = ModulePreloader()
        results = preloader.preload(["sfp_dnsresolve", "sfp_spider", "sfp_whois"])
        # results = {"sfp_dnsresolve": True, "sfp_spider": True, ...}
    """

    def __init__(self, module_dir: str = "spiderfoot.modules") -> None:
        self._module_dir = module_dir
        self._loaded: dict[str, Any] = {}
        self._lock = threading.Lock()

    def preload(self, module_names: list[str]) -> dict[str, bool]:
        """Import all modules, returning success status per module.

        Args:
            module_names: List of module names (e.g. ["sfp_dnsresolve"])

        Returns:
            Dict mapping module name to True (success) or False (failed)
        """
        results = {}
        threads = []

        for name in module_names:
            t = threading.Thread(
                target=self._import_module,
                args=(name, results),
                name=f"preload-{name}",
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10.0)

        return results

    def _import_module(self, name: str, results: dict) -> None:
        """Import a single module."""
        try:
            fqn = f"{self._module_dir}.{name}"
            mod = importlib.import_module(fqn)
            with self._lock:
                self._loaded[name] = mod
                results[name] = True
            log.debug("Preloaded module: %s", name)
        except Exception as e:
            log.warning("Failed to preload %s: %s", name, e)
            with self._lock:
                results[name] = False

    def get_module(self, name: str) -> Any | None:
        """Get a preloaded module, or None if not loaded."""
        return self._loaded.get(name)

    @property
    def loaded_count(self) -> int:
        return len(self._loaded)

    def clear(self) -> None:
        """Clear all loaded modules."""
        with self._lock:
            self._loaded.clear()


# ====================================================================== #
# Cycle 94: Event Deduplicator                                          #
# ====================================================================== #

class EventDeduplicator:
    """Suppress duplicate events within a configurable time window.

    When two modules produce the same ``(event_type, data)`` pair within
    ``window_ms`` milliseconds, only the first is forwarded.

    Thread-safe.  A background reaper cleans expired entries every
    ``reap_interval`` seconds.

    Usage::

        dedup = EventDeduplicator(window_ms=100)
        dedup.start()
        if dedup.is_duplicate("IP_ADDRESS", "192.168.1.1", "scan-1"):
            pass  # skip
        dedup.stop()
    """

    def __init__(self, window_ms: int = 100, max_entries: int = 100_000,
                 reap_interval: float = 5.0) -> None:
        self._window_s = window_ms / 1000.0
        self._max_entries = max_entries
        self._reap_interval = reap_interval
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._reaper: threading.Thread | None = None
        self._stats = {"checked": 0, "duplicates": 0, "reaped": 0}

    def start(self) -> None:
        """Start the background reaper thread."""
        if self._reaper and self._reaper.is_alive():
            return
        self._stop.clear()
        self._reaper = threading.Thread(
            target=self._reap_loop, daemon=True, name="event-dedup-reaper"
        )
        self._reaper.start()

    def stop(self) -> None:
        """Stop the reaper and clear state."""
        self._stop.set()
        if self._reaper:
            self._reaper.join(timeout=2.0)
        with self._lock:
            self._seen.clear()

    def is_duplicate(self, event_type: str, data: str, scan_id: str = "") -> bool:
        """Check if an event is a duplicate within the time window.

        Args:
            event_type: Event type string
            data: Event data
            scan_id: Optional scan ID for scoping

        Returns:
            True if this is a duplicate (should be suppressed)
        """
        key = self._make_key(event_type, data, scan_id)
        now = time.time()

        with self._lock:
            self._stats["checked"] += 1
            prev = self._seen.get(key)
            if prev is not None and (now - prev) < self._window_s:
                self._stats["duplicates"] += 1
                return True
            self._seen[key] = now
            # Evict oldest if over capacity
            if len(self._seen) > self._max_entries:
                oldest_key = min(self._seen, key=self._seen.get)
                del self._seen[oldest_key]
            return False

    def _make_key(self, event_type: str, data: str, scan_id: str) -> str:
        """Create a dedup key from event attributes."""
        raw = f"{scan_id}:{event_type}:{data}"
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()

    def _reap_loop(self) -> None:
        """Background thread that removes expired entries."""
        while not self._stop.wait(self._reap_interval):
            cutoff = time.time() - self._window_s
            with self._lock:
                expired = [k for k, ts in self._seen.items() if ts < cutoff]
                for k in expired:
                    del self._seen[k]
                self._stats["reaped"] += len(expired)

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    @property
    def active_entries(self) -> int:
        return len(self._seen)


# ====================================================================== #
# Cycle 95: Backpressure Controller                                      #
# ====================================================================== #

class PressureState(str, Enum):
    """Backpressure states."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    BLOCKED = "blocked"


class BackpressureController:
    """Rate-limit event emission when queue depth is too high.

    Monitors a queue depth callable and applies progressive backpressure:
    - NORMAL: no delay
    - WARNING (50%): 10ms delay between events
    - CRITICAL (75%): 100ms delay
    - BLOCKED (90%): reject new events

    Usage::

        def get_depth():
            return redis_client.llen("sf:events")

        bp = BackpressureController(
            depth_fn=get_depth,
            capacity=10000,
        )
        if bp.should_accept():
            bp.apply_delay()
            publish_event(...)
    """

    DEFAULT_THRESHOLDS = {
        PressureState.WARNING: 0.50,
        PressureState.CRITICAL: 0.75,
        PressureState.BLOCKED: 0.90,
    }

    DEFAULT_DELAYS = {
        PressureState.NORMAL: 0.0,
        PressureState.WARNING: 0.01,
        PressureState.CRITICAL: 0.1,
        PressureState.BLOCKED: 0.0,  # no delay — rejected
    }

    def __init__(
        self,
        depth_fn: Callable[[], int],
        capacity: int = 10_000,
        thresholds: dict[PressureState, float] | None = None,
        delays: dict[PressureState, float] | None = None,
    ) -> None:
        if not callable(depth_fn):
            raise ValueError("depth_fn must be callable")
        self._depth_fn = depth_fn
        self._capacity = max(1, capacity)
        self._thresholds = thresholds or dict(self.DEFAULT_THRESHOLDS)
        self._delays = delays or dict(self.DEFAULT_DELAYS)
        self._state = PressureState.NORMAL
        self._rejected = 0
        self._accepted = 0
        self._callbacks: list[Callable[[PressureState], None]] = []

    def get_state(self) -> PressureState:
        """Evaluate current pressure state."""
        depth = self._depth_fn()
        ratio = depth / self._capacity

        if ratio >= self._thresholds.get(PressureState.BLOCKED, 0.90):
            new_state = PressureState.BLOCKED
        elif ratio >= self._thresholds.get(PressureState.CRITICAL, 0.75):
            new_state = PressureState.CRITICAL
        elif ratio >= self._thresholds.get(PressureState.WARNING, 0.50):
            new_state = PressureState.WARNING
        else:
            new_state = PressureState.NORMAL

        if new_state != self._state:
            old_state = self._state
            self._state = new_state
            log.info("Backpressure state: %s -> %s (depth=%d/%d)",
                     old_state.value, new_state.value, depth, self._capacity)
            for cb in self._callbacks:
                try:
                    cb(new_state)
                except Exception:
                    pass

        return new_state

    def should_accept(self) -> bool:
        """Return True if a new event should be accepted."""
        state = self.get_state()
        if state == PressureState.BLOCKED:
            self._rejected += 1
            return False
        self._accepted += 1
        return True

    def apply_delay(self) -> None:
        """Apply the appropriate delay for the current pressure state."""
        delay = self._delays.get(self._state, 0.0)
        if delay > 0:
            time.sleep(delay)

    def on_state_change(self, callback: Callable[[PressureState], None]) -> None:
        """Register a callback for pressure state changes."""
        self._callbacks.append(callback)

    @property
    def utilization(self) -> float:
        """Current queue utilization (0.0 - 1.0)."""
        return self._depth_fn() / self._capacity

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "state": self._state.value,
            "accepted": self._accepted,
            "rejected": self._rejected,
            "utilization": round(self.utilization, 4),
        }


# ====================================================================== #
# Cycle 96: Worker Auto-Scaler                                          #
# ====================================================================== #

@dataclass
class ScaleSignal:
    """A scaling recommendation."""
    action: str  # "scale_up", "scale_down", "no_change"
    current_workers: int
    recommended_workers: int
    reason: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "current_workers": self.current_workers,
            "recommended_workers": self.recommended_workers,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class WorkerAutoScaler:
    """Emit scale-up/down signals based on Celery queue depth.

    Monitors queue depth and emits scaling recommendations. Does NOT
    actually scale workers — the signal consumer (e.g., Docker Compose,
    Kubernetes HPA, or a Flower plugin) acts on the signal.

    Usage::

        def get_queue_depth():
            return redis_client.llen("scan")

        scaler = WorkerAutoScaler(
            depth_fn=get_queue_depth,
            min_workers=1,
            max_workers=10,
        )
        signal = scaler.evaluate(current_workers=3)
        # ScaleSignal(action="scale_up", recommended_workers=5, ...)
    """

    def __init__(
        self,
        depth_fn: Callable[[], int],
        min_workers: int = 1,
        max_workers: int = 10,
        scale_up_threshold: int = 1000,
        scale_down_threshold: int = 10,
        tasks_per_worker: int = 200,
        cooldown_seconds: float = 60.0,
    ) -> None:
        if not callable(depth_fn):
            raise ValueError("depth_fn must be callable")
        self._depth_fn = depth_fn
        self._min_workers = max(1, min_workers)
        self._max_workers = max(self._min_workers, max_workers)
        self._scale_up_threshold = scale_up_threshold
        self._scale_down_threshold = scale_down_threshold
        self._tasks_per_worker = max(1, tasks_per_worker)
        self._cooldown = cooldown_seconds
        self._last_signal_time = 0.0
        self._history: list[ScaleSignal] = []

    def evaluate(self, current_workers: int) -> ScaleSignal:
        """Evaluate whether to scale up, down, or hold.

        Args:
            current_workers: Number of currently running workers

        Returns:
            ScaleSignal with recommendation
        """
        depth = self._depth_fn()
        now = time.time()

        # Cooldown check
        if (now - self._last_signal_time) < self._cooldown:
            signal = ScaleSignal(
                action="no_change",
                current_workers=current_workers,
                recommended_workers=current_workers,
                reason=f"Cooldown period ({self._cooldown}s)",
            )
            return signal

        # Calculate needed workers
        needed = max(self._min_workers, -(-depth // self._tasks_per_worker))  # ceil div
        needed = min(needed, self._max_workers)

        if depth >= self._scale_up_threshold and needed > current_workers:
            signal = ScaleSignal(
                action="scale_up",
                current_workers=current_workers,
                recommended_workers=needed,
                reason=f"Queue depth {depth} >= threshold {self._scale_up_threshold}",
            )
        elif depth <= self._scale_down_threshold and current_workers > self._min_workers:
            signal = ScaleSignal(
                action="scale_down",
                current_workers=current_workers,
                recommended_workers=max(self._min_workers, current_workers - 1),
                reason=f"Queue depth {depth} <= threshold {self._scale_down_threshold}",
            )
        else:
            signal = ScaleSignal(
                action="no_change",
                current_workers=current_workers,
                recommended_workers=current_workers,
                reason=f"Queue depth {depth} within normal range",
            )

        if signal.action != "no_change":
            self._last_signal_time = now

        self._history.append(signal)
        if len(self._history) > 100:
            self._history = self._history[-50:]

        return signal

    @property
    def history(self) -> list[dict]:
        return [s.to_dict() for s in self._history]


# ====================================================================== #
# Cycle 97: Tracing Middleware                                           #
# ====================================================================== #

@dataclass
class SpanRecord:
    """Lightweight tracing span record.

    Compatible with OpenTelemetry span attributes but does not require
    the library to be installed.
    """
    trace_id: str
    span_id: str
    operation: str
    module_name: str
    scan_id: str
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    status: str = "ok"
    error: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def finish(self, error: str | None = None) -> None:
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        if error:
            self.error = error
            self.status = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "operation": self.operation,
            "module_name": self.module_name,
            "scan_id": self.scan_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 3),
            "status": self.status,
            "error": self.error,
            "attributes": self.attributes,
        }


class TracingMiddleware:
    """OpenTelemetry-compatible tracing for module ``handleEvent()`` calls.

    Creates a span per event handling call with timing, module name,
    event type, and error capture.

    If ``opentelemetry`` is installed, exports spans to the configured
    exporter (Jaeger, OTLP, etc.).  Otherwise, stores spans in memory
    for local inspection.

    Usage::

        tracer = TracingMiddleware(scan_id="abc")
        span = tracer.start_span("handleEvent", "sfp_dnsresolve")
        try:
            module.handleEvent(event)
            span.finish()
        except Exception as e:
            span.finish(error=str(e))
    """

    def __init__(self, scan_id: str, max_spans: int = 10_000) -> None:
        self._scan_id = scan_id
        self._max_spans = max_spans
        self._spans: list[SpanRecord] = []
        self._lock = threading.Lock()
        self._otel_tracer = self._try_otel_tracer()

    def _try_otel_tracer(self):
        """Try to get an OpenTelemetry tracer."""
        try:
            from opentelemetry import trace
            return trace.get_tracer("spiderfoot.modules")
        except ImportError:
            return None

    def start_span(self, operation: str, module_name: str,
                   attributes: dict[str, Any] | None = None) -> SpanRecord:
        """Start a new tracing span.

        Args:
            operation: Operation name (e.g., "handleEvent")
            module_name: Module name
            attributes: Optional span attributes

        Returns:
            SpanRecord to be finished later
        """
        span = SpanRecord(
            trace_id=hashlib.md5(
                f"{self._scan_id}:{time.time()}".encode(),
                usedforsecurity=False,
            ).hexdigest(),
            span_id=hashlib.md5(
                f"{module_name}:{operation}:{time.time()}".encode(),
                usedforsecurity=False,
            ).hexdigest(),
            operation=operation,
            module_name=module_name,
            scan_id=self._scan_id,
            start_time=time.time(),
            attributes=attributes or {},
        )

        # If OTel is available, start a real span too
        if self._otel_tracer:
            try:
                from opentelemetry import trace
                otel_span = self._otel_tracer.start_span(
                    f"{module_name}.{operation}",
                    attributes={
                        "sf.scan_id": self._scan_id,
                        "sf.module": module_name,
                        **(attributes or {}),
                    },
                )
                span.attributes["_otel_span"] = otel_span
            except Exception:
                pass

        return span

    def finish_span(self, span: SpanRecord, error: str | None = None) -> None:
        """Finish a span and record it.

        Args:
            span: The span to finish
            error: Optional error message
        """
        span.finish(error)

        # Close OTel span if present
        otel_span = span.attributes.pop("_otel_span", None)
        if otel_span:
            try:
                if error:
                    from opentelemetry import trace
                    otel_span.set_status(trace.StatusCode.ERROR, error)
                otel_span.end()
            except Exception:
                pass

        with self._lock:
            self._spans.append(span)
            if len(self._spans) > self._max_spans:
                self._spans = self._spans[-self._max_spans // 2:]

    def get_slow_spans(self, threshold_ms: float = 1000.0) -> list[dict]:
        """Return spans slower than the threshold."""
        with self._lock:
            return [
                s.to_dict() for s in self._spans
                if s.duration_ms >= threshold_ms
            ]

    def get_error_spans(self) -> list[dict]:
        """Return spans that recorded errors."""
        with self._lock:
            return [s.to_dict() for s in self._spans if s.status == "error"]

    def span_count(self) -> int:
        return len(self._spans)

    def summary(self) -> dict[str, Any]:
        """Return aggregate statistics per module."""
        by_module: dict[str, list[float]] = defaultdict(list)
        errors = 0
        with self._lock:
            for s in self._spans:
                by_module[s.module_name].append(s.duration_ms)
                if s.status == "error":
                    errors += 1

        module_stats = {}
        for name, durations in by_module.items():
            module_stats[name] = {
                "count": len(durations),
                "avg_ms": round(sum(durations) / len(durations), 2),
                "max_ms": round(max(durations), 2),
                "min_ms": round(min(durations), 2),
            }

        return {
            "total_spans": len(self._spans),
            "total_errors": errors,
            "modules": module_stats,
        }


# ====================================================================== #
# Cycle 98: Celery Retry Configuration                                   #
# ====================================================================== #

def celery_retry_config(
    max_retries: int = 3,
    backoff_base: float = 2.0,
    backoff_max: float = 300.0,
    retryable_exceptions: list[type[Exception]] | None = None,
) -> dict[str, Any]:
    """Generate Celery task retry kwargs compatible with ``@app.task()``.

    Wires SpiderFoot's ``retry.py`` exponential backoff strategy into
    Celery's built-in ``autoretry_for`` mechanism.

    Usage::

        from spiderfoot.scan.concurrency import celery_retry_config

        @celery_app.task(**celery_retry_config(max_retries=5))
        def my_task():
            ...

    Returns:
        dict of Celery task decorator kwargs
    """
    if retryable_exceptions is None:
        retryable_exceptions = [
            ConnectionError,
            TimeoutError,
            OSError,
            IOError,
        ]

    return {
        "autoretry_for": tuple(retryable_exceptions),
        "max_retries": max_retries,
        "retry_backoff": backoff_base,
        "retry_backoff_max": backoff_max,
        "retry_jitter": True,
        "acks_late": True,
    }


# ====================================================================== #
# Cycle 99: Module Timeout Enforcer                                      #
# ====================================================================== #

class ModuleTimeoutEnforcer:
    """Enforce per-module execution timeouts.

    Tracks how long each module takes to handle an event and raises
    an alarm (callback) if the timeout is exceeded.  Also provides
    recommended Celery ``soft_time_limit`` and ``time_limit`` values.

    Usage::

        enforcer = ModuleTimeoutEnforcer(default_timeout=300)
        enforcer.set_timeout("sfp_spider", 600)  # spider gets extra time

        # In the module execution loop:
        enforcer.start_tracking("sfp_dns", "event-hash-123")
        try:
            module.handleEvent(event)
        finally:
            enforcer.stop_tracking("sfp_dns", "event-hash-123")
    """

    DEFAULT_TIMEOUT = 300.0  # 5 minutes
    CELERY_GRACE = 60.0  # extra seconds for Celery hard limit

    def __init__(
        self,
        default_timeout: float = DEFAULT_TIMEOUT,
        on_timeout: Callable[[str, str, float], None] | None = None,
    ) -> None:
        """
        Args:
            default_timeout: Default timeout in seconds
            on_timeout: Callback(module_name, event_id, elapsed_seconds)
        """
        self._default_timeout = default_timeout
        self._on_timeout = on_timeout
        self._timeouts: dict[str, float] = {}
        self._active: dict[str, dict[str, float]] = defaultdict(dict)
        self._violations: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def set_timeout(self, module_name: str, timeout: float) -> None:
        """Set a custom timeout for a specific module."""
        self._timeouts[module_name] = timeout

    def get_timeout(self, module_name: str) -> float:
        """Get the timeout for a module."""
        return self._timeouts.get(module_name, self._default_timeout)

    def start_tracking(self, module_name: str, event_id: str) -> None:
        """Start tracking execution time for a module/event pair."""
        with self._lock:
            self._active[module_name][event_id] = time.time()

    def stop_tracking(self, module_name: str, event_id: str) -> float:
        """Stop tracking and return elapsed time.

        Returns:
            Elapsed time in seconds
        """
        with self._lock:
            start = self._active.get(module_name, {}).pop(event_id, None)
        if start is None:
            return 0.0
        elapsed = time.time() - start
        timeout = self.get_timeout(module_name)
        if elapsed > timeout:
            violation = {
                "module": module_name,
                "event_id": event_id,
                "elapsed": round(elapsed, 2),
                "timeout": timeout,
                "timestamp": time.time(),
            }
            self._violations.append(violation)
            log.warning("Module %s exceeded timeout: %.1fs > %.1fs",
                        module_name, elapsed, timeout)
            if self._on_timeout:
                try:
                    self._on_timeout(module_name, event_id, elapsed)
                except Exception:
                    pass
        return elapsed

    def check_active(self) -> list[dict[str, Any]]:
        """Check all active trackings for timeouts.

        Returns list of currently exceeded timeout violations.
        """
        now = time.time()
        exceeded = []
        with self._lock:
            for module_name, events in self._active.items():
                timeout = self.get_timeout(module_name)
                for event_id, start in events.items():
                    elapsed = now - start
                    if elapsed > timeout:
                        exceeded.append({
                            "module": module_name,
                            "event_id": event_id,
                            "elapsed": round(elapsed, 2),
                            "timeout": timeout,
                        })
        return exceeded

    def get_celery_limits(self, module_name: str) -> dict[str, float]:
        """Return recommended Celery task time limits for a module.

        Returns:
            Dict with 'soft_time_limit' and 'time_limit' keys
        """
        timeout = self.get_timeout(module_name)
        return {
            "soft_time_limit": timeout,
            "time_limit": timeout + self.CELERY_GRACE,
        }

    @property
    def violations(self) -> list[dict]:
        return list(self._violations)

    @property
    def active_count(self) -> int:
        return sum(len(events) for events in self._active.values())


# ====================================================================== #
# Cycles 100-110: Scan Splitter                                          #
# ====================================================================== #

class SplitStrategy(str, Enum):
    """How to split a scan target."""
    IP_RANGE = "ip_range"
    MODULE_CATEGORY = "module_category"
    SUBDOMAIN = "subdomain"


@dataclass
class ScanChunk:
    """A partition of a scan that can be distributed to a worker."""
    chunk_id: str
    scan_id: str
    target: str
    target_type: str
    modules: list[str]
    strategy: SplitStrategy
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "scan_id": self.scan_id,
            "target": self.target,
            "target_type": self.target_type,
            "modules": self.modules,
            "strategy": self.strategy.value,
            "metadata": self.metadata,
        }


class ScanSplitter:
    """Split large scan targets across multiple workers.

    Supports three strategies:
    1. IP_RANGE: Split a CIDR range into sub-ranges
    2. MODULE_CATEGORY: Assign module groups to different workers
    3. SUBDOMAIN: Split subdomains across workers

    Usage::

        splitter = ScanSplitter()
        chunks = splitter.split_by_ip_range(
            scan_id="scan-1",
            target="10.0.0.0/16",
            max_hosts_per_chunk=256,
            modules=["sfp_portscan_basic", "sfp_ssl"],
        )
    """

    # Module categories for MODULE_CATEGORY strategy
    MODULE_CATEGORIES = {
        "passive_dns": ["sfp_dnsresolve", "sfp_dnsbrute", "sfp_dnscommonfqdn",
                        "sfp_dnsdumpster", "sfp_dnszonexfer"],
        "active_scan": ["sfp_portscan_basic", "sfp_portscan_tcp", "sfp_ssl",
                        "sfp_spider"],
        "osint": ["sfp_shodan", "sfp_censys", "sfp_binaryedge", "sfp_greynoise"],
        "threat_intel": ["sfp_virustotal", "sfp_alienvault", "sfp_abuseipdb",
                         "sfp_maltiverse"],
        "identity": ["sfp_whois", "sfp_email", "sfp_accounts", "sfp_linkedin"],
    }

    def split_by_ip_range(
        self,
        scan_id: str,
        target: str,
        modules: list[str],
        max_hosts_per_chunk: int = 256,
    ) -> list[ScanChunk]:
        """Split a CIDR target into sub-ranges.

        Args:
            scan_id: Scan identifier
            target: CIDR notation (e.g., "10.0.0.0/16")
            modules: Module names to use for each chunk
            max_hosts_per_chunk: Max hosts per chunk (default 256 = /24)

        Returns:
            List of ScanChunks
        """
        try:
            network = ipaddress.ip_network(target, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid CIDR target: {target}") from e

        num_hosts = network.num_addresses
        if num_hosts <= max_hosts_per_chunk:
            return [ScanChunk(
                chunk_id=f"{scan_id}_chunk_0",
                scan_id=scan_id,
                target=str(network),
                target_type="NETBLOCK_OWNER",
                modules=list(modules),
                strategy=SplitStrategy.IP_RANGE,
                metadata={"hosts": num_hosts},
            )]

        # Calculate subnet prefix for the desired chunk size
        import math
        bits_needed = math.ceil(math.log2(max_hosts_per_chunk))
        if network.version == 4:
            new_prefix = 32 - bits_needed
        else:
            new_prefix = 128 - bits_needed

        new_prefix = max(new_prefix, network.prefixlen)
        subnets = list(network.subnets(new_prefix=new_prefix))

        chunks = []
        for i, subnet in enumerate(subnets):
            chunks.append(ScanChunk(
                chunk_id=f"{scan_id}_chunk_{i}",
                scan_id=scan_id,
                target=str(subnet),
                target_type="NETBLOCK_OWNER",
                modules=list(modules),
                strategy=SplitStrategy.IP_RANGE,
                metadata={"hosts": subnet.num_addresses, "index": i, "total": len(subnets)},
            ))

        return chunks

    def split_by_module_category(
        self,
        scan_id: str,
        target: str,
        target_type: str,
        modules: list[str],
    ) -> list[ScanChunk]:
        """Split modules into category-based chunks.

        Each chunk gets modules from the same category, so different
        workers can specialize.

        Args:
            scan_id: Scan identifier
            target: Scan target
            target_type: Target type
            modules: Full list of modules to categorize

        Returns:
            List of ScanChunks
        """
        # Categorize modules
        categorized: dict[str, list[str]] = defaultdict(list)
        uncategorized: list[str] = []

        category_lookup: dict[str, str] = {}
        for cat, mod_list in self.MODULE_CATEGORIES.items():
            for mod in mod_list:
                category_lookup[mod] = cat

        for mod in modules:
            cat = category_lookup.get(mod)
            if cat:
                categorized[cat].append(mod)
            else:
                uncategorized.append(mod)

        chunks = []
        idx = 0
        for cat, cat_modules in categorized.items():
            chunks.append(ScanChunk(
                chunk_id=f"{scan_id}_cat_{idx}",
                scan_id=scan_id,
                target=target,
                target_type=target_type,
                modules=cat_modules,
                strategy=SplitStrategy.MODULE_CATEGORY,
                metadata={"category": cat},
            ))
            idx += 1

        if uncategorized:
            chunks.append(ScanChunk(
                chunk_id=f"{scan_id}_cat_{idx}",
                scan_id=scan_id,
                target=target,
                target_type=target_type,
                modules=uncategorized,
                strategy=SplitStrategy.MODULE_CATEGORY,
                metadata={"category": "uncategorized"},
            ))

        return chunks

    def split_subdomains(
        self,
        scan_id: str,
        subdomains: list[str],
        modules: list[str],
        max_per_chunk: int = 50,
    ) -> list[ScanChunk]:
        """Split a list of subdomains into chunks.

        Args:
            scan_id: Scan identifier
            subdomains: List of subdomains to scan
            modules: Modules to apply
            max_per_chunk: Max subdomains per chunk

        Returns:
            List of ScanChunks
        """
        chunks = []
        for i in range(0, len(subdomains), max_per_chunk):
            batch = subdomains[i:i + max_per_chunk]
            chunks.append(ScanChunk(
                chunk_id=f"{scan_id}_sub_{i // max_per_chunk}",
                scan_id=scan_id,
                target=",".join(batch),
                target_type="INTERNET_NAME",
                modules=list(modules),
                strategy=SplitStrategy.SUBDOMAIN,
                metadata={
                    "subdomain_count": len(batch),
                    "index": i // max_per_chunk,
                    "total": -(-len(subdomains) // max_per_chunk),
                },
            ))

        return chunks

    def estimate_chunks(self, target: str, strategy: SplitStrategy,
                        max_per_chunk: int = 256) -> int:
        """Estimate how many chunks a target would produce."""
        if strategy == SplitStrategy.IP_RANGE:
            try:
                net = ipaddress.ip_network(target, strict=False)
                return max(1, -(-net.num_addresses // max_per_chunk))
            except ValueError:
                return 1
        return 1
