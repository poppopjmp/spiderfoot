"""
Task Queue — centralised background job manager for SpiderFoot.

Provides a unified ``TaskManager`` that replaces ad-hoc
``BackgroundTasks`` usage across routers.  Every submitted task gets
a persistent ID, lifecycle tracking, and progress updates.

The default backend is in-memory (suitable for single-process
deployments).  The interface is designed to be replaced with
Redis / Celery / NATS backends later.

Usage::

    from spiderfoot.task_queue import get_task_manager, TaskType

    mgr = get_task_manager()
    task_id = mgr.submit(
        task_type=TaskType.SCAN,
        func=start_scan_background,
        args=(scan_id, scan_name, target, ...),
        meta={"scan_id": scan_id},
    )
    status = mgr.get(task_id)
    mgr.cancel(task_id)
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List

log = logging.getLogger("spiderfoot.task_queue")


# -----------------------------------------------------------------------
# Enums & data models
# -----------------------------------------------------------------------

class TaskType(Enum):
    """Broad category of background tasks."""
    SCAN = "scan"
    REPORT = "report"
    WORKSPACE = "workspace"
    EXPORT = "export"
    GENERIC = "generic"


class TaskState(Enum):
    """Task lifecycle states."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskRecord:
    """Immutable snapshot of a task's state."""
    task_id: str
    task_type: TaskType
    state: TaskState
    progress: float  # 0-100
    meta: dict[str, Any]
    result: Any = None
    error: str | None = None
    created_at: float = 0.0
    started_at: float | None = None
    completed_at: float | None = None

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        return round(end - self.started_at, 2)

    @property
    def is_terminal(self) -> bool:
        return self.state in (
            TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "state": self.state.value,
            "progress": round(self.progress, 2),
            "meta": self.meta,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_seconds": self.elapsed_seconds,
        }


# -----------------------------------------------------------------------
# Task Manager
# -----------------------------------------------------------------------

class TaskManager:
    """In-memory task queue with thread pool execution.

    Thread-safe.  Maintains a bounded history of completed tasks so
    clients can poll for results after completion.

    Parameters:
        max_workers: Thread pool size (default 4).
        max_history: Number of completed tasks to retain (default 500).
    """

    def __init__(
        self,
        max_workers: int = 4,
        max_history: int = 500,
    ) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, _TaskEntry] = {}
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="sf-task",
        )
        self._max_history = max_history
        self._callbacks: list[Callable[[TaskRecord], None]] = []

    # -- submit -----------------------------------------------------------

    def submit(
        self,
        task_type: TaskType,
        func: Callable[..., Any],
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> str:
        """Submit a callable for background execution.

        Returns the task ID.
        """
        tid = task_id or str(uuid.uuid4())
        kwargs = kwargs or {}
        meta = meta or {}

        entry = _TaskEntry(
            task_id=tid,
            task_type=task_type,
            meta=meta,
            created_at=time.time(),
        )

        with self._lock:
            if tid in self._tasks:
                raise ValueError(f"Task '{tid}' already exists")
            self._tasks[tid] = entry

        log.info("Task submitted: %s (%s)", tid, task_type.value)

        def _wrapper():
            with self._lock:
                entry.state = TaskState.RUNNING
                entry.started_at = time.time()
            try:
                result = func(*args, **kwargs)
                with self._lock:
                    entry.state = TaskState.COMPLETED
                    entry.progress = 100.0
                    entry.result = result
                    entry.completed_at = time.time()
                log.info("Task completed: %s", tid)
            except Exception as e:
                with self._lock:
                    entry.state = TaskState.FAILED
                    entry.error = str(e)
                    entry.completed_at = time.time()
                log.error("Task failed: %s — %s", tid, e)
            finally:
                self._fire_callbacks(entry.to_record())
                self._prune_history()

        future = self._pool.submit(_wrapper)
        with self._lock:
            entry.future = future

        return tid

    # -- query ------------------------------------------------------------

    def get(self, task_id: str) -> TaskRecord | None:
        """Get current state of a task.  Returns None if unknown."""
        with self._lock:
            entry = self._tasks.get(task_id)
            return entry.to_record() if entry else None

    def list_tasks(
        self,
        state: TaskState | None = None,
        task_type: TaskType | None = None,
        limit: int = 50,
    ) -> list[TaskRecord]:
        """List tasks, optionally filtered by state and type."""
        with self._lock:
            entries = list(self._tasks.values())
        records = []
        for e in entries:
            if state and e.state != state:
                continue
            if task_type and e.task_type != task_type:
                continue
            records.append(e.to_record())
        # Sort newest first
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    def active_count(self) -> int:
        """Count tasks in QUEUED or RUNNING state."""
        with self._lock:
            return sum(
                1 for e in self._tasks.values()
                if e.state in (TaskState.QUEUED, TaskState.RUNNING)
            )

    # -- update -----------------------------------------------------------

    def update_progress(self, task_id: str, progress: float) -> bool:
        """Update progress (0-100) for a running task.

        Returns False if the task is not found or not running.
        """
        with self._lock:
            entry = self._tasks.get(task_id)
            if entry and entry.state == TaskState.RUNNING:
                entry.progress = min(100.0, max(0.0, progress))
                return True
        return False

    # -- cancel -----------------------------------------------------------

    def cancel(self, task_id: str) -> bool:
        """Attempt to cancel a task.  Returns True if state changed."""
        with self._lock:
            entry = self._tasks.get(task_id)
            if entry is None:
                return False
            if entry.is_terminal:
                return False
            entry.state = TaskState.CANCELLED
            entry.completed_at = time.time()
            if entry.future and not entry.future.done():
                entry.future.cancel()
        log.info("Task cancelled: %s", task_id)
        self._fire_callbacks(entry.to_record())
        return True

    # -- callbacks --------------------------------------------------------

    def on_task_complete(
        self, callback: Callable[[TaskRecord], None],
    ) -> None:
        """Register a callback fired when any task reaches terminal state."""
        self._callbacks.append(callback)

    def _fire_callbacks(self, record: TaskRecord) -> None:
        for cb in self._callbacks:
            try:
                cb(record)
            except Exception as e:
                log.error("Task callback error: %s", e)

    # -- housekeeping -----------------------------------------------------

    def _prune_history(self) -> None:
        """Remove oldest completed tasks beyond max_history."""
        with self._lock:
            terminal = [
                e for e in self._tasks.values() if e.is_terminal
            ]
            if len(terminal) <= self._max_history:
                return
            terminal.sort(key=lambda e: e.completed_at or 0)
            to_remove = terminal[: len(terminal) - self._max_history]
            for e in to_remove:
                self._tasks.pop(e.task_id, None)

    def clear_completed(self) -> int:
        """Remove all terminal tasks.  Returns count removed."""
        with self._lock:
            ids = [
                tid for tid, e in self._tasks.items() if e.is_terminal
            ]
            for tid in ids:
                del self._tasks[tid]
        return len(ids)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the thread pool."""
        self._pool.shutdown(wait=wait)
        log.info("TaskManager shut down (wait=%s)", wait)

    # -- properties -------------------------------------------------------

    @property
    def task_count(self) -> int:
        with self._lock:
            return len(self._tasks)


# -----------------------------------------------------------------------
# Internal mutable entry (not exposed)
# -----------------------------------------------------------------------

class _TaskEntry:
    """Mutable internal record for a task."""

    __slots__ = (
        "task_id", "task_type", "state", "progress", "meta",
        "result", "error", "created_at", "started_at",
        "completed_at", "future",
    )

    def __init__(
        self,
        task_id: str,
        task_type: TaskType,
        meta: dict[str, Any],
        created_at: float,
    ) -> None:
        self.task_id = task_id
        self.task_type = task_type
        self.state = TaskState.QUEUED
        self.progress = 0.0
        self.meta = meta
        self.result: Any = None
        self.error: str | None = None
        self.created_at = created_at
        self.started_at: float | None = None
        self.completed_at: float | None = None
        self.future: Future | None = None

    @property
    def is_terminal(self) -> bool:
        return self.state in (
            TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED,
        )

    def to_record(self) -> TaskRecord:
        return TaskRecord(
            task_id=self.task_id,
            task_type=self.task_type,
            state=self.state,
            progress=self.progress,
            meta=dict(self.meta),
            result=self.result,
            error=self.error,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
        )


# -----------------------------------------------------------------------
# Singleton accessor
# -----------------------------------------------------------------------

_manager: TaskManager | None = None
_manager_lock = threading.Lock()


def get_task_manager(
    max_workers: int = 4,
    max_history: int = 500,
) -> TaskManager:
    """Get or create the global ``TaskManager`` singleton."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = TaskManager(
                    max_workers=max_workers,
                    max_history=max_history,
                )
    return _manager


def reset_task_manager() -> None:
    """Reset the global singleton (for testing)."""
    global _manager
    with _manager_lock:
        if _manager is not None:
            _manager.shutdown(wait=False)
        _manager = None
