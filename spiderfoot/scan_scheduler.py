"""
Scan Scheduler Service — Manages scan lifecycle as a standalone service.

Extracted from SpiderFootScanner to provide scan orchestration that can
run independently of the WebUI/API. Coordinates module loading, event
routing through the EventBus, and scan state management via DataService.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from spiderfoot.scan_state import ScanState

log = logging.getLogger("spiderfoot.scan_scheduler")


class ScanPriority(str, Enum):
    """Scan execution priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ScanRequest:
    """A request to run a scan.

    Attributes:
        scan_id: Unique scan identifier (auto-generated if empty)
        scan_name: Human-readable name
        target: Scan target (domain, IP, etc.)
        modules: List of module names to run
        config: Scan-specific configuration overrides
        priority: Execution priority
        max_duration: Max scan duration in seconds (0 = no limit)
        tags: Optional tags for categorization
    """
    scan_name: str
    target: str
    modules: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    scan_id: str = ""
    priority: ScanPriority = ScanPriority.NORMAL
    max_duration: int = 0
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.scan_id:
            self.scan_id = str(uuid.uuid4())


@dataclass
class ScanStatus:
    """Current status of a scan."""
    scan_id: str
    scan_name: str
    target: str
    state: ScanState
    progress: float = 0.0  # 0-100%
    modules_total: int = 0
    modules_running: int = 0
    modules_finished: int = 0
    events_produced: int = 0
    started_at: float = 0.0
    ended_at: float = 0.0
    error_message: str = ""

    @property
    def duration(self) -> float:
        """Scan duration in seconds."""
        end = self.ended_at or time.time()
        if self.started_at == 0:
            return 0
        return end - self.started_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "scan_name": self.scan_name,
            "target": self.target,
            "state": self.state.value,
            "progress": round(self.progress, 1),
            "modules_total": self.modules_total,
            "modules_running": self.modules_running,
            "modules_finished": self.modules_finished,
            "events_produced": self.events_produced,
            "duration": round(self.duration, 1),
            "error_message": self.error_message,
        }


@dataclass
class SchedulerConfig:
    """Configuration for the scan scheduler.

    Attributes:
        max_concurrent_scans: Max scans running simultaneously
        scan_poll_interval: Check interval for pending scans (seconds)
        default_max_duration: Default max scan duration (seconds)
        enable_auto_correlations: Run correlations after scan completes
    """
    max_concurrent_scans: int = 3
    scan_poll_interval: float = 5.0
    default_max_duration: int = 0  # unlimited
    enable_auto_correlations: bool = True

    @classmethod
    def from_sf_config(cls, opts: dict[str, Any]) -> "SchedulerConfig":
        return cls(
            max_concurrent_scans=int(opts.get("_scheduler_max_scans", 3)),
            scan_poll_interval=float(opts.get("_scheduler_poll_interval", 5)),
            default_max_duration=int(opts.get("_scheduler_max_duration", 0)),
            enable_auto_correlations=opts.get("_scheduler_auto_correlations", True),
        )


class ScanScheduler:
    """Scan lifecycle management service.

    Manages the queue of scan requests, coordinates active scans,
    and provides status monitoring. Can run as a standalone service
    or embedded in the existing monolith.

    Usage:
        scheduler = ScanScheduler(config)
        scheduler.start()

        scan_id = scheduler.submit_scan(ScanRequest(
            scan_name="Example Scan",
            target="example.com",
            modules=["sfp_dns", "sfp_whois"],
        ))

        status = scheduler.get_scan_status(scan_id)
        scheduler.abort_scan(scan_id)

        scheduler.shutdown()
    """

    def __init__(
        self,
        config: SchedulerConfig | None = None,
        registry: Any | None = None,
    ) -> None:
        self.config = config or SchedulerConfig()
        self._registry = registry
        self.log = logging.getLogger("spiderfoot.scan_scheduler")

        self._pending: list[ScanRequest] = []
        self._active: dict[str, ScanStatus] = {}
        self._completed: dict[str, ScanStatus] = {}
        self._lock = threading.RLock()
        self._running = False
        self._scheduler_thread: threading.Thread | None = None

        # Callbacks for scan lifecycle events
        self._on_scan_start: Callable | None = None
        self._on_scan_complete: Callable | None = None
        self._on_scan_error: Callable | None = None

    # --- Lifecycle ---

    def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="sf-scan-scheduler",
        )
        self._scheduler_thread.start()
        self.log.info(
            f"Scan scheduler started (max_concurrent={self.config.max_concurrent_scans})"
        )

    def shutdown(self, abort_active: bool = False) -> None:
        """Shutdown the scheduler.

        Args:
            abort_active: If True, abort all active scans
        """
        self._running = False

        if abort_active:
            with self._lock:
                for scan_id in list(self._active.keys()):
                    self.abort_scan(scan_id)

        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=10)

        self.log.info("Scan scheduler shutdown")

    # --- Scan Submission ---

    def submit_scan(self, request: ScanRequest) -> str:
        """Submit a scan request to the queue.

        Args:
            request: ScanRequest with target, modules, etc.

        Returns:
            Scan ID
        """
        with self._lock:
            # Insert based on priority
            if request.priority == ScanPriority.CRITICAL:
                self._pending.insert(0, request)
            elif request.priority == ScanPriority.HIGH:
                # Insert after critical scans
                idx = 0
                for i, r in enumerate(self._pending):
                    if r.priority != ScanPriority.CRITICAL:
                        idx = i
                        break
                    idx = i + 1
                self._pending.insert(idx, request)
            else:
                self._pending.append(request)

        self.log.info(
            f"Scan submitted: {request.scan_id} "
            f"(target={request.target}, priority={request.priority.value})"
        )
        return request.scan_id

    def abort_scan(self, scan_id: str, reason: str = "") -> bool:
        """Request a scan to be aborted.

        Args:
            scan_id: Scan identifier
            reason: Optional reason

        Returns:
            True if abort was requested
        """
        with self._lock:
            # Check pending queue
            for i, req in enumerate(self._pending):
                if req.scan_id == scan_id:
                    self._pending.pop(i)
                    self.log.info("Pending scan removed: %s", scan_id)
                    return True

            # Check active scans
            status = self._active.get(scan_id)
            if status:
                status.state = ScanState.STOPPING
                status.error_message = reason or "Abort requested"
                self.log.info("Scan abort requested: %s", scan_id)
                return True

        self.log.warning("Scan not found for abort: %s", scan_id)
        return False

    def pause_scan(self, scan_id: str) -> bool:
        """Pause a running scan."""
        with self._lock:
            status = self._active.get(scan_id)
            if status and status.state == ScanState.RUNNING:
                status.state = ScanState.PAUSED
                return True
        return False

    def resume_scan(self, scan_id: str) -> bool:
        """Resume a paused scan."""
        with self._lock:
            status = self._active.get(scan_id)
            if status and status.state == ScanState.PAUSED:
                status.state = ScanState.RUNNING
                return True
        return False

    # --- Status ---

    def get_scan_status(self, scan_id: str) -> dict[str, Any] | None:
        """Get the current status of a scan.

        Checks active, completed, and pending queues.
        """
        with self._lock:
            # Check active
            if scan_id in self._active:
                return self._active[scan_id].to_dict()

            # Check completed
            if scan_id in self._completed:
                return self._completed[scan_id].to_dict()

            # Check pending
            for req in self._pending:
                if req.scan_id == scan_id:
                    return {
                        "scan_id": scan_id,
                        "scan_name": req.scan_name,
                        "target": req.target,
                        "state": ScanState.CREATED.value,
                        "progress": 0,
                        "modules_total": len(req.modules),
                    }

        return None

    def list_scans(
        self,
        state: ScanState | None = None,
    ) -> list[dict[str, Any]]:
        """List scans, optionally filtered by state."""
        results = []

        with self._lock:
            # Pending
            if state is None or state == ScanState.CREATED:
                for req in self._pending:
                    results.append({
                        "scan_id": req.scan_id,
                        "scan_name": req.scan_name,
                        "target": req.target,
                        "state": ScanState.CREATED.value,
                        "priority": req.priority.value,
                    })

            # Active
            for status in self._active.values():
                if state is None or status.state == state:
                    results.append(status.to_dict())

            # Completed
            for status in self._completed.values():
                if state is None or status.state == state:
                    results.append(status.to_dict())

        return results

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def active_count(self) -> int:
        return len(self._active)

    # --- Internal ---

    def _scheduler_loop(self):
        """Main scheduler loop — checks for pending scans and starts them."""
        while self._running:
            try:
                self._process_pending()
                self._check_timeouts()
            except Exception as e:
                self.log.error("Scheduler loop error: %s", e)

            time.sleep(self.config.scan_poll_interval)

    def _process_pending(self):
        """Start pending scans if capacity is available."""
        with self._lock:
            while (self._pending and
                   len(self._active) < self.config.max_concurrent_scans):
                request = self._pending.pop(0)
                self._start_scan(request)

    def _start_scan(self, request: ScanRequest):
        """Start a scan from a request."""
        status = ScanStatus(
            scan_id=request.scan_id,
            scan_name=request.scan_name,
            target=request.target,
            state=ScanState.STARTING,
            modules_total=len(request.modules),
            started_at=time.time(),
        )

        self._active[request.scan_id] = status
        self.log.info("Starting scan: %s -> %s", request.scan_id, request.target)

        # Launch scan in a thread
        thread = threading.Thread(
            target=self._run_scan,
            args=(request, status),
            daemon=True,
            name=f"sf-scan-{request.scan_id[:8]}",
        )
        thread.start()

    def _run_scan(self, request: ScanRequest, status: ScanStatus):
        """Execute a scan (runs in a dedicated thread)."""
        try:
            status.state = ScanState.RUNNING

            if self._on_scan_start:
                self._on_scan_start(request, status)

            # The actual scan execution is delegated to the existing
            # SpiderFootScanner or the new modular pipeline.
            # This method provides the orchestration harness.

            # For now, this is a placeholder that will be wired to the
            # existing scanner in the integration cycle.
            self.log.info(
                f"Scan {request.scan_id} running "
                f"({status.modules_total} modules)"
            )

            # Scan completion will be signaled by the scanner
            # via complete_scan() or error_scan()

        except Exception as e:
            self.log.error("Scan %s failed: %s", request.scan_id, e)
            status.state = ScanState.FAILED
            status.error_message = str(e)
            status.ended_at = time.time()
            self._move_to_completed(request.scan_id)

            if self._on_scan_error:
                self._on_scan_error(request, status, e)

    def complete_scan(self, scan_id: str) -> None:
        """Mark a scan as completed (called by scanner)."""
        with self._lock:
            status = self._active.get(scan_id)
            if status:
                status.state = ScanState.COMPLETED
                status.ended_at = time.time()
                status.progress = 100.0
                self._move_to_completed(scan_id)

                self.log.info(
                    f"Scan completed: {scan_id} "
                    f"({status.events_produced} events, "
                    f"{status.duration:.1f}s)"
                )

                if self._on_scan_complete:
                    self._on_scan_complete(status)

    def error_scan(self, scan_id: str, error: str) -> None:
        """Mark a scan as errored (called by scanner)."""
        with self._lock:
            status = self._active.get(scan_id)
            if status:
                status.state = ScanState.FAILED
                status.error_message = error
                status.ended_at = time.time()
                self._move_to_completed(scan_id)
                self.log.error("Scan errored: %s — %s", scan_id, error)

    def update_scan_progress(
        self,
        scan_id: str,
        events_produced: int = 0,
        modules_running: int = 0,
        modules_finished: int = 0,
    ) -> None:
        """Update scan progress (called by scanner)."""
        with self._lock:
            status = self._active.get(scan_id)
            if status:
                status.events_produced = events_produced
                status.modules_running = modules_running
                status.modules_finished = modules_finished
                if status.modules_total > 0:
                    status.progress = (
                        modules_finished / status.modules_total * 100
                    )

    def _move_to_completed(self, scan_id: str):
        """Move a scan from active to completed."""
        status = self._active.pop(scan_id, None)
        if status:
            self._completed[scan_id] = status

    def _check_timeouts(self):
        """Check for scans that exceeded their max duration."""
        max_dur = self.config.default_max_duration
        if max_dur <= 0:
            return

        now = time.time()
        with self._lock:
            for scan_id, status in list(self._active.items()):
                if (status.state == ScanState.RUNNING and
                        status.started_at > 0 and
                        (now - status.started_at) > max_dur):
                    self.log.warning(
                        f"Scan {scan_id} exceeded max duration "
                        f"({max_dur}s), aborting"
                    )
                    status.state = ScanState.CANCELLED
                    status.error_message = f"Exceeded max duration ({max_dur}s)"
                    status.ended_at = now
                    self._move_to_completed(scan_id)

    # --- Callbacks ---

    def on_scan_start(self, callback: Callable) -> None:
        """Register callback for scan start events."""
        self._on_scan_start = callback

    def on_scan_complete(self, callback: Callable) -> None:
        """Register callback for scan completion events."""
        self._on_scan_complete = callback

    def on_scan_error(self, callback: Callable) -> None:
        """Register callback for scan error events."""
        self._on_scan_error = callback

    # --- Metrics ---

    def stats(self) -> dict[str, Any]:
        """Get scheduler statistics."""
        with self._lock:
            return {
                "running": self._running,
                "pending_scans": len(self._pending),
                "active_scans": len(self._active),
                "completed_scans": len(self._completed),
                "max_concurrent": self.config.max_concurrent_scans,
                "active_scan_ids": list(self._active.keys()),
            }
