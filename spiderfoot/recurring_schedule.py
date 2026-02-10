"""
Recurring Scan Schedule — time-based scan scheduling.

Provides in-memory storage for recurring scan schedules with
interval-based timing and one-shot delayed execution. Works
alongside the existing ScanScheduler (which handles execution)
by creating scan requests when schedules are due.

Usage:
    from spiderfoot.recurring_schedule import get_recurring_scheduler

    scheduler = get_recurring_scheduler()
    scheduler.add_schedule(
        name="Weekly Recon",
        target="example.com",
        interval_minutes=10080,  # 1 week
        modules=["sfp_dns", "sfp_whois"],
    )
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.recurring_schedule")


class RecurringStatus(str, Enum):
    """Enumeration of recurring schedule states."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"     # one-shot that has fired
    EXPIRED = "expired"         # max_runs reached


@dataclass
class RecurringSchedule:
    """A time-based recurring scan schedule."""
    schedule_id: str = ""
    name: str = ""
    target: str = ""
    modules: list[str] = field(default_factory=list)
    type_filter: list[str] = field(default_factory=list)

    # Timing
    interval_minutes: int = 0        # recurring: run every N minutes
    run_at: float | None = None   # one-shot: unix timestamp to run at

    # State
    status: RecurringStatus = RecurringStatus.ACTIVE
    created_at: float = 0.0
    last_run_at: float | None = None
    next_run_at: float | None = None
    run_count: int = 0
    max_runs: int = 0                # 0 = unlimited
    last_scan_id: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.schedule_id:
            self.schedule_id = str(uuid.uuid4())[:12]
        if not self.created_at:
            self.created_at = time.time()
        if self.run_at and not self.next_run_at:
            self.next_run_at = self.run_at
        elif self.interval_minutes and not self.next_run_at:
            self.next_run_at = self.created_at + (self.interval_minutes * 60)

    def is_due(self) -> bool:
        """Check if this schedule is due to run."""
        if self.status != RecurringStatus.ACTIVE:
            return False
        if self.max_runs > 0 and self.run_count >= self.max_runs:
            return False
        if self.next_run_at is None:
            return False
        return time.time() >= self.next_run_at

    def mark_run(self, scan_id: str = "") -> None:
        """Update state after a run."""
        self.last_run_at = time.time()
        self.run_count += 1
        self.last_scan_id = scan_id

        if self.run_at and not self.interval_minutes:
            # One-shot
            self.status = RecurringStatus.COMPLETED
            self.next_run_at = None
        elif self.max_runs > 0 and self.run_count >= self.max_runs:
            self.status = RecurringStatus.EXPIRED
            self.next_run_at = None
        elif self.interval_minutes:
            self.next_run_at = time.time() + (self.interval_minutes * 60)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "target": self.target,
            "modules": self.modules,
            "type_filter": self.type_filter,
            "interval_minutes": self.interval_minutes,
            "run_at": self.run_at,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "run_count": self.run_count,
            "max_runs": self.max_runs,
            "last_scan_id": self.last_scan_id,
            "description": self.description,
            "tags": self.tags,
        }


class RecurringScheduler:
    """In-memory recurring scan scheduler with background check loop."""

    def __init__(self, check_interval: float = 30.0) -> None:
        self._schedules: dict[str, RecurringSchedule] = {}
        self._lock = threading.Lock()
        self._check_interval = check_interval
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_trigger: Callable | None = None

    def set_trigger_callback(self, callback: Callable) -> None:
        """Set the callback invoked when a schedule fires.

        Callback signature: ``callback(schedule: RecurringSchedule) -> str``
        Should return the new scan ID.
        """
        self._on_trigger = callback

    def add_schedule(
        self,
        name: str,
        target: str,
        interval_minutes: int = 0,
        run_at: float | None = None,
        modules: list[str] | None = None,
        type_filter: list[str] | None = None,
        max_runs: int = 0,
        description: str = "",
        tags: list[str] | None = None,
    ) -> RecurringSchedule:
        """Create and register a new recurring schedule."""
        schedule = RecurringSchedule(
            name=name,
            target=target,
            interval_minutes=interval_minutes,
            run_at=run_at,
            modules=modules or [],
            type_filter=type_filter or [],
            max_runs=max_runs,
            description=description,
            tags=tags or [],
        )
        with self._lock:
            self._schedules[schedule.schedule_id] = schedule
        log.info("Recurring schedule added: %s (%s → %s, every %d min)",
                 schedule.schedule_id, name, target, interval_minutes)
        return schedule

    def get(self, schedule_id: str) -> RecurringSchedule | None:
        with self._lock:
            return self._schedules.get(schedule_id)

    def remove(self, schedule_id: str) -> bool:
        with self._lock:
            if schedule_id in self._schedules:
                del self._schedules[schedule_id]
                log.info("Recurring schedule removed: %s", schedule_id)
                return True
            return False

    def list_all(self) -> list[RecurringSchedule]:
        with self._lock:
            return list(self._schedules.values())

    def pause(self, schedule_id: str) -> bool:
        with self._lock:
            s = self._schedules.get(schedule_id)
            if s and s.status == RecurringStatus.ACTIVE:
                s.status = RecurringStatus.PAUSED
                return True
            return False

    def resume(self, schedule_id: str) -> bool:
        with self._lock:
            s = self._schedules.get(schedule_id)
            if s and s.status == RecurringStatus.PAUSED:
                s.status = RecurringStatus.ACTIVE
                # Recompute next run
                if s.interval_minutes:
                    s.next_run_at = time.time() + (s.interval_minutes * 60)
                return True
            return False

    def start(self) -> None:
        """Start the background scheduler loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name="recurring-scheduler", daemon=True,
        )
        self._thread.start()
        log.info("Recurring scheduler started (check every %.0fs)", self._check_interval)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        log.info("Recurring scheduler stopped")

    def _loop(self) -> None:
        while self._running:
            try:
                self._check_schedules()
            except Exception as e:
                log.error("Recurring scheduler check failed: %s", e)
            time.sleep(self._check_interval)

    def _check_schedules(self) -> None:
        with self._lock:
            due = [s for s in self._schedules.values() if s.is_due()]

        for schedule in due:
            scan_id = ""
            log.info("Recurring schedule triggered: %s (%s → %s)",
                     schedule.schedule_id, schedule.name, schedule.target)
            if self._on_trigger:
                try:
                    scan_id = self._on_trigger(schedule) or ""
                except Exception as e:
                    log.error("Recurring schedule trigger failed for %s: %s",
                              schedule.schedule_id, e)
            with self._lock:
                schedule.mark_run(scan_id)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            statuses = {}
            for s in self._schedules.values():
                statuses[s.status.value] = statuses.get(s.status.value, 0) + 1
            return {
                "total_schedules": len(self._schedules),
                "running": self._running,
                "by_status": statuses,
                "total_runs": sum(s.run_count for s in self._schedules.values()),
            }


# -----------------------------------------------------------------------
# Singleton
# -----------------------------------------------------------------------

_scheduler: RecurringScheduler | None = None
_lock = threading.Lock()


def get_recurring_scheduler() -> RecurringScheduler:
    """Get or create the singleton RecurringScheduler."""
    global _scheduler
    if _scheduler is None:
        with _lock:
            if _scheduler is None:
                _scheduler = RecurringScheduler()
    return _scheduler
