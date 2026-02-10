"""Scan Progress Tracker for SpiderFoot.

Estimates scan completion percentage based on module progress,
event throughput, and elapsed time. Provides ETA calculations
and progress snapshots for UI/API consumption.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.scan_progress")


class ModuleStatus(Enum):
    """Individual module processing status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ModuleProgress:
    """Tracks progress for a single module."""
    module_name: str
    status: ModuleStatus = ModuleStatus.PENDING
    events_produced: int = 0
    events_consumed: int = 0
    started_at: float | None = None
    completed_at: float | None = None
    error_message: str = ""

    @property
    def elapsed(self) -> float:
        """Elapsed time in seconds."""
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        return end - self.started_at

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            ModuleStatus.COMPLETED,
            ModuleStatus.FAILED,
            ModuleStatus.SKIPPED,
        )

    def to_dict(self) -> dict:
        return {
            "module": self.module_name,
            "status": self.status.value,
            "events_produced": self.events_produced,
            "events_consumed": self.events_consumed,
            "elapsed_seconds": round(self.elapsed, 2),
            "error": self.error_message,
        }


@dataclass
class ProgressSnapshot:
    """Point-in-time snapshot of scan progress."""
    timestamp: float
    overall_pct: float
    modules_completed: int
    modules_total: int
    events_total: int
    throughput_eps: float  # events per second
    eta_seconds: float | None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "overall_pct": round(self.overall_pct, 2),
            "modules_completed": self.modules_completed,
            "modules_total": self.modules_total,
            "events_total": self.events_total,
            "throughput_eps": round(self.throughput_eps, 2),
            "eta_seconds": round(self.eta_seconds, 1) if self.eta_seconds is not None else None,
        }


class ScanProgressTracker:
    """Tracks overall scan progress with module-level detail.

    Usage:
        tracker = ScanProgressTracker(scan_id="scan-001")
        tracker.register_modules(["sfp_dns", "sfp_portscan", "sfp_ssl"])

        tracker.module_started("sfp_dns")
        tracker.record_event("sfp_dns", produced=True)
        tracker.module_completed("sfp_dns")

        snapshot = tracker.get_snapshot()
        print(f"Progress: {snapshot.overall_pct}%, ETA: {snapshot.eta_seconds}s")
    """

    def __init__(self, scan_id: str) -> None:
        self.scan_id = scan_id
        self._modules: dict[str, ModuleProgress] = {}
        self._lock = threading.Lock()
        self._started_at: float | None = None
        self._completed_at: float | None = None
        self._total_events = 0
        self._snapshots: list[ProgressSnapshot] = []
        self._max_snapshots = 1000
        self._callbacks: list[Callable] = []
        self._milestone_thresholds: set[int] = {25, 50, 75, 100}
        self._milestones_reached: set[int] = set()

    def register_modules(self, module_names: list[str]) -> None:
        """Register the set of modules participating in this scan."""
        with self._lock:
            for name in module_names:
                if name not in self._modules:
                    self._modules[name] = ModuleProgress(module_name=name)

    def start(self) -> None:
        """Mark the scan as started."""
        with self._lock:
            self._started_at = time.time()

    def module_started(self, module_name: str) -> None:
        """Record that a module has started processing."""
        with self._lock:
            mp = self._modules.get(module_name)
            if mp is None:
                mp = ModuleProgress(module_name=module_name)
                self._modules[module_name] = mp
            mp.status = ModuleStatus.RUNNING
            mp.started_at = time.time()
            if self._started_at is None:
                self._started_at = mp.started_at

    def module_completed(self, module_name: str) -> None:
        """Record that a module has finished processing."""
        with self._lock:
            mp = self._modules.get(module_name)
            if mp:
                mp.status = ModuleStatus.COMPLETED
                mp.completed_at = time.time()
            self._check_milestones()

    def module_failed(self, module_name: str, error: str = "") -> None:
        """Record that a module has failed."""
        with self._lock:
            mp = self._modules.get(module_name)
            if mp:
                mp.status = ModuleStatus.FAILED
                mp.completed_at = time.time()
                mp.error_message = error
            self._check_milestones()

    def module_skipped(self, module_name: str) -> None:
        """Record that a module was skipped."""
        with self._lock:
            mp = self._modules.get(module_name)
            if mp:
                mp.status = ModuleStatus.SKIPPED
                mp.completed_at = time.time()
            self._check_milestones()

    def record_event(self, module_name: str, produced: bool = True) -> None:
        """Record an event being produced or consumed by a module."""
        with self._lock:
            self._total_events += 1
            mp = self._modules.get(module_name)
            if mp:
                if produced:
                    mp.events_produced += 1
                else:
                    mp.events_consumed += 1

    @property
    def overall_progress(self) -> float:
        """Calculate overall scan progress as a percentage (0-100)."""
        with self._lock:
            return self._calc_progress()

    def _calc_progress(self) -> float:
        """Internal progress calculation (caller must hold lock)."""
        total = len(self._modules)
        if total == 0:
            return 0.0
        done = sum(1 for m in self._modules.values() if m.is_terminal)
        return (done / total) * 100

    @property
    def elapsed(self) -> float:
        """Total elapsed time in seconds."""
        if self._started_at is None:
            return 0.0
        end = self._completed_at or time.time()
        return end - self._started_at

    @property
    def throughput(self) -> float:
        """Events per second."""
        e = self.elapsed
        if e <= 0:
            return 0.0
        return self._total_events / e

    @property
    def eta_seconds(self) -> float | None:
        """Estimated time remaining in seconds."""
        with self._lock:
            return self._calc_eta()

    def _calc_eta(self) -> float | None:
        """Internal ETA calculation (caller must hold lock)."""
        progress = self._calc_progress()
        if progress <= 0 or self._started_at is None:
            return None
        elapsed = (self._completed_at or time.time()) - self._started_at
        if elapsed <= 0:
            return None
        total_estimated = elapsed / (progress / 100)
        remaining = total_estimated - elapsed
        return max(0.0, remaining)

    def get_snapshot(self) -> ProgressSnapshot:
        """Create a point-in-time progress snapshot."""
        with self._lock:
            snap = ProgressSnapshot(
                timestamp=time.time(),
                overall_pct=self._calc_progress(),
                modules_completed=sum(
                    1 for m in self._modules.values() if m.is_terminal
                ),
                modules_total=len(self._modules),
                events_total=self._total_events,
                throughput_eps=self._total_events / max(0.001, self.elapsed),
                eta_seconds=self._calc_eta(),
            )
            if len(self._snapshots) < self._max_snapshots:
                self._snapshots.append(snap)
            return snap

    def get_module_progress(self, module_name: str) -> ModuleProgress | None:
        """Get progress for a specific module."""
        with self._lock:
            return self._modules.get(module_name)

    def get_all_module_progress(self) -> dict[str, ModuleProgress]:
        """Get progress for all modules."""
        with self._lock:
            return dict(self._modules)

    def get_running_modules(self) -> list[str]:
        """Get names of currently running modules."""
        with self._lock:
            return [
                name for name, mp in self._modules.items()
                if mp.status == ModuleStatus.RUNNING
            ]

    def get_failed_modules(self) -> list[str]:
        """Get names of failed modules."""
        with self._lock:
            return [
                name for name, mp in self._modules.items()
                if mp.status == ModuleStatus.FAILED
            ]

    def get_pending_modules(self) -> list[str]:
        """Get names of pending modules."""
        with self._lock:
            return [
                name for name, mp in self._modules.items()
                if mp.status == ModuleStatus.PENDING
            ]

    def complete(self) -> None:
        """Mark the scan as complete."""
        with self._lock:
            self._completed_at = time.time()

    def on_milestone(self, callback: Callable) -> None:
        """Register callback for milestone events (25/50/75/100%).

        Callback signature: callback(scan_id, milestone_pct, snapshot)
        """
        self._callbacks.append(callback)

    def _check_milestones(self) -> None:
        """Check if any milestone has been reached (caller must hold lock)."""
        pct = self._calc_progress()
        for threshold in self._milestone_thresholds:
            if pct >= threshold and threshold not in self._milestones_reached:
                self._milestones_reached.add(threshold)
                snap = ProgressSnapshot(
                    timestamp=time.time(),
                    overall_pct=pct,
                    modules_completed=sum(
                        1 for m in self._modules.values() if m.is_terminal
                    ),
                    modules_total=len(self._modules),
                    events_total=self._total_events,
                    throughput_eps=self._total_events / max(0.001, self.elapsed),
                    eta_seconds=self._calc_eta(),
                )
                for cb in self._callbacks:
                    try:
                        cb(self.scan_id, threshold, snap)
                    except Exception as e:
                        log.error("Milestone callback error: %s", e)

    def get_history(self) -> list[ProgressSnapshot]:
        """Get recorded snapshot history."""
        with self._lock:
            return list(self._snapshots)

    def to_dict(self) -> dict:
        """Serialize to dict for API responses."""
        with self._lock:
            return {
                "scan_id": self.scan_id,
                "overall_pct": round(self._calc_progress(), 2),
                "elapsed_seconds": round(self.elapsed, 2),
                "total_events": self._total_events,
                "throughput_eps": round(
                    self._total_events / max(0.001, self.elapsed), 2
                ),
                "eta_seconds": (
                    round(self._calc_eta(), 1)
                    if self._calc_eta() is not None
                    else None
                ),
                "modules": {
                    name: mp.to_dict()
                    for name, mp in self._modules.items()
                },
                "running": [
                    n for n, m in self._modules.items()
                    if m.status == ModuleStatus.RUNNING
                ],
                "failed": [
                    n for n, m in self._modules.items()
                    if m.status == ModuleStatus.FAILED
                ],
                "milestones_reached": sorted(self._milestones_reached),
            }
