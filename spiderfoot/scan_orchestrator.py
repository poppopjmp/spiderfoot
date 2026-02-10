"""Scan Orchestrator for SpiderFoot.

High-level scan lifecycle orchestration with phase management,
module scheduling, event routing, and completion detection.
"""

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("spiderfoot.scan_orchestrator")


class ScanPhase(Enum):
    """Phases of a scan lifecycle."""
    INIT = "init"
    DISCOVERY = "discovery"
    ENUMERATION = "enumeration"
    ANALYSIS = "analysis"
    ENRICHMENT = "enrichment"
    CORRELATION = "correlation"
    REPORTING = "reporting"
    COMPLETE = "complete"
    FAILED = "failed"


PHASE_ORDER = [
    ScanPhase.INIT,
    ScanPhase.DISCOVERY,
    ScanPhase.ENUMERATION,
    ScanPhase.ANALYSIS,
    ScanPhase.ENRICHMENT,
    ScanPhase.CORRELATION,
    ScanPhase.REPORTING,
    ScanPhase.COMPLETE,
]


@dataclass
class PhaseResult:
    """Result of a completed scan phase."""
    phase: ScanPhase
    duration_seconds: float = 0.0
    events_produced: int = 0
    modules_run: int = 0
    errors: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleSchedule:
    """Scheduling info for a module within a phase."""
    module_name: str
    phase: ScanPhase
    priority: int = 0
    timeout_seconds: Optional[float] = None
    depends_on: set[str] = field(default_factory=set)


class ScanOrchestrator:
    """Orchestrates the lifecycle of a scan through phases.

    Manages module scheduling, phase transitions, event counting,
    and completion detection.

    Usage:
        orch = ScanOrchestrator(scan_id="scan_001")
        orch.register_module("sfp_dns", ScanPhase.DISCOVERY, priority=10)
        orch.register_module("sfp_whois", ScanPhase.ENUMERATION)

        orch.start()
        orch.advance_phase()  # Move to next phase
        orch.module_completed("sfp_dns", events_produced=15)
        orch.advance_phase()
        orch.module_completed("sfp_whois", events_produced=8)
        orch.complete()
    """

    def __init__(self, scan_id: str, target: str = ""):
        self.scan_id = scan_id
        self.target = target
        self._phase = ScanPhase.INIT
        self._phase_start = time.time()
        self._scan_start = time.time()
        self._lock = threading.Lock()

        # Module scheduling
        self._modules: dict[str, ModuleSchedule] = {}
        self._phase_modules: dict[ScanPhase, list[str]] = defaultdict(list)
        self._completed_modules: set[str] = set()
        self._failed_modules: set[str] = set()
        self._running_modules: set[str] = set()

        # Tracking
        self._phase_results: list[PhaseResult] = []
        self._total_events = 0
        self._total_errors = 0

        # Callbacks
        self._phase_callbacks: list[Callable[[ScanPhase, ScanPhase], None]] = []
        self._completion_callbacks: list[Callable[["ScanOrchestrator"], None]] = []

    def register_module(
        self,
        module_name: str,
        phase: ScanPhase,
        priority: int = 0,
        timeout_seconds: Optional[float] = None,
        depends_on: Optional[set[str]] = None,
    ) -> "ScanOrchestrator":
        """Register a module to run in a specific phase."""
        schedule = ModuleSchedule(
            module_name=module_name,
            phase=phase,
            priority=priority,
            timeout_seconds=timeout_seconds,
            depends_on=depends_on or set(),
        )
        self._modules[module_name] = schedule
        self._phase_modules[phase].append(module_name)
        return self

    def unregister_module(self, module_name: str) -> bool:
        schedule = self._modules.pop(module_name, None)
        if schedule is None:
            return False
        self._phase_modules[schedule.phase] = [
            m for m in self._phase_modules[schedule.phase] if m != module_name
        ]
        return True

    def start(self) -> None:
        """Start the scan."""
        with self._lock:
            self._scan_start = time.time()
            self._phase = ScanPhase.INIT
            self._phase_start = time.time()
            log.info("Scan %s started targeting '%s'", self.scan_id, self.target)

    def advance_phase(self) -> ScanPhase:
        """Advance to the next scan phase."""
        with self._lock:
            old_phase = self._phase
            now = time.time()

            # Record result of current phase
            result = PhaseResult(
                phase=old_phase,
                duration_seconds=now - self._phase_start,
                modules_run=len([m for m in self._completed_modules
                               if self._modules.get(m, ModuleSchedule("", ScanPhase.INIT)).phase == old_phase]),
            )
            self._phase_results.append(result)

            # Find next phase
            try:
                idx = PHASE_ORDER.index(old_phase)
                if idx + 1 < len(PHASE_ORDER):
                    self._phase = PHASE_ORDER[idx + 1]
                else:
                    self._phase = ScanPhase.COMPLETE
            except ValueError:
                self._phase = ScanPhase.COMPLETE

            self._phase_start = now
            new_phase = self._phase

        # Fire callbacks outside lock
        for cb in self._phase_callbacks:
            try:
                cb(old_phase, new_phase)
            except Exception as e:
                log.error("Phase callback error: %s", e)

        log.info("Scan %s: %s -> %s", self.scan_id, old_phase.value, new_phase.value)
        return new_phase

    def module_started(self, module_name: str) -> None:
        with self._lock:
            self._running_modules.add(module_name)

    def module_completed(self, module_name: str, events_produced: int = 0) -> None:
        with self._lock:
            self._running_modules.discard(module_name)
            self._completed_modules.add(module_name)
            self._total_events += events_produced

    def module_failed(self, module_name: str, error: str = "") -> None:
        with self._lock:
            self._running_modules.discard(module_name)
            self._failed_modules.add(module_name)
            self._total_errors += 1
            log.error("Module %s failed: %s", module_name, error)

    def complete(self) -> None:
        """Mark the scan as complete."""
        with self._lock:
            # Record final phase
            now = time.time()
            result = PhaseResult(
                phase=self._phase,
                duration_seconds=now - self._phase_start,
            )
            self._phase_results.append(result)
            self._phase = ScanPhase.COMPLETE

        for cb in self._completion_callbacks:
            try:
                cb(self)
            except Exception as e:
                log.error("Completion callback error: %s", e)

        log.info("Scan %s completed", self.scan_id)

    def fail(self, reason: str = "") -> None:
        """Mark the scan as failed."""
        with self._lock:
            self._phase = ScanPhase.FAILED
        log.error("Scan %s failed: %s", self.scan_id, reason)

    def on_phase_change(self, callback: Callable[[ScanPhase, ScanPhase], None]) -> None:
        self._phase_callbacks.append(callback)

    def on_completion(self, callback: Callable[["ScanOrchestrator"], None]) -> None:
        self._completion_callbacks.append(callback)

    @property
    def current_phase(self) -> ScanPhase:
        return self._phase

    @property
    def is_complete(self) -> bool:
        return self._phase in (ScanPhase.COMPLETE, ScanPhase.FAILED)

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self._scan_start

    @property
    def total_events(self) -> int:
        return self._total_events

    @property
    def total_errors(self) -> int:
        return self._total_errors

    def get_phase_modules(self, phase: ScanPhase) -> list[str]:
        """Get modules scheduled for a phase, sorted by priority."""
        modules = self._phase_modules.get(phase, [])
        return sorted(
            modules,
            key=lambda m: -(self._modules[m].priority if m in self._modules else 0),
        )

    def get_pending_modules(self) -> list[str]:
        all_done = self._completed_modules | self._failed_modules
        return [m for m in self._modules if m not in all_done]

    def get_module_status(self, module_name: str) -> str:
        if module_name in self._completed_modules:
            return "completed"
        if module_name in self._failed_modules:
            return "failed"
        if module_name in self._running_modules:
            return "running"
        if module_name in self._modules:
            return "pending"
        return "unknown"

    def can_run_module(self, module_name: str) -> bool:
        """Check if module dependencies are satisfied."""
        schedule = self._modules.get(module_name)
        if schedule is None:
            return False
        return schedule.depends_on.issubset(self._completed_modules)

    def get_phase_results(self) -> list[PhaseResult]:
        return list(self._phase_results)

    def summary(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "target": self.target,
            "phase": self._phase.value,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "total_events": self._total_events,
            "total_errors": self._total_errors,
            "modules_total": len(self._modules),
            "modules_completed": len(self._completed_modules),
            "modules_failed": len(self._failed_modules),
            "modules_running": len(self._running_modules),
            "modules_pending": len(self.get_pending_modules()),
        }

    def to_dict(self) -> dict:
        return {
            **self.summary(),
            "phases": [
                {
                    "phase": r.phase.value,
                    "duration_seconds": round(r.duration_seconds, 2),
                    "events_produced": r.events_produced,
                    "modules_run": r.modules_run,
                    "errors": r.errors,
                }
                for r in self._phase_results
            ],
        }
