"""Module Sandbox for SpiderFoot.

Provides isolated execution environments for modules with
resource limits, timeout enforcement, output capture, and
fault isolation to prevent module failures from affecting scans.
"""

import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

log = logging.getLogger("spiderfoot.module_sandbox")


class SandboxState(Enum):
    """State of a sandbox."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    KILLED = "killed"


@dataclass
class ResourceLimits:
    """Resource limits for sandboxed execution."""
    max_execution_seconds: float = 300.0
    max_memory_mb: Optional[int] = None
    max_events: int = 10000
    max_errors: int = 100
    max_http_requests: int = 1000
    rate_limit_per_second: Optional[float] = None


@dataclass
class SandboxResult:
    """Result from sandboxed module execution."""
    module_name: str
    state: SandboxState
    events_produced: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    output: str = ""
    exception: Optional[str] = None
    resource_usage: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.state == SandboxState.COMPLETED

    def to_dict(self) -> dict:
        return {
            "module": self.module_name,
            "state": self.state.value,
            "success": self.success,
            "events_produced": self.events_produced,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 3),
            "exception": self.exception,
            "resource_usage": self.resource_usage,
        }


class ResourceTracker:
    """Tracks resource usage within a sandbox."""

    def __init__(self, limits: ResourceLimits):
        self.limits = limits
        self._event_count = 0
        self._error_count = 0
        self._http_count = 0
        self._start_time = 0.0
        self._lock = threading.Lock()

    def start(self) -> None:
        self._start_time = time.monotonic()

    @property
    def elapsed(self) -> float:
        if self._start_time == 0:
            return 0.0
        return time.monotonic() - self._start_time

    def record_event(self) -> bool:
        """Record an event. Returns False if limit exceeded."""
        with self._lock:
            self._event_count += 1
            return self._event_count <= self.limits.max_events

    def record_error(self) -> bool:
        """Record an error. Returns False if limit exceeded."""
        with self._lock:
            self._error_count += 1
            return self._error_count <= self.limits.max_errors

    def record_http_request(self) -> bool:
        """Record an HTTP request. Returns False if limit exceeded."""
        with self._lock:
            self._http_count += 1
            return self._http_count <= self.limits.max_http_requests

    def check_timeout(self) -> bool:
        """Returns True if execution has timed out."""
        return self.elapsed > self.limits.max_execution_seconds

    def check_limits(self) -> Optional[str]:
        """Check all limits. Returns violation message or None."""
        if self.check_timeout():
            return f"Execution timeout ({self.limits.max_execution_seconds}s)"
        with self._lock:
            if self._event_count > self.limits.max_events:
                return f"Event limit exceeded ({self.limits.max_events})"
            if self._error_count > self.limits.max_errors:
                return f"Error limit exceeded ({self.limits.max_errors})"
            if self._http_count > self.limits.max_http_requests:
                return f"HTTP request limit exceeded ({self.limits.max_http_requests})"
        return None

    def get_usage(self) -> dict:
        with self._lock:
            return {
                "events": self._event_count,
                "errors": self._error_count,
                "http_requests": self._http_count,
                "elapsed_seconds": round(self.elapsed, 3),
            }


class ModuleSandbox:
    """Isolated execution environment for a module.

    Usage:
        sandbox = ModuleSandbox("sfp_dns", limits=ResourceLimits(max_execution_seconds=60))
        result = sandbox.execute(my_module_func, target="example.com")
        if result.success:
            print(f"Produced {result.events_produced} events")
    """

    def __init__(
        self,
        module_name: str,
        limits: Optional[ResourceLimits] = None,
    ):
        self.module_name = module_name
        self.limits = limits or ResourceLimits()
        self._state = SandboxState.IDLE
        self._tracker = ResourceTracker(self.limits)
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[SandboxResult], None]] = []

    @property
    def state(self) -> SandboxState:
        return self._state

    @property
    def tracker(self) -> ResourceTracker:
        return self._tracker

    def on_complete(self, callback: Callable[[SandboxResult], None]) -> None:
        self._callbacks.append(callback)

    def execute(self, func: Callable[..., Any], **kwargs: Any) -> SandboxResult:
        """Execute a function within the sandbox.

        The function receives the ResourceTracker as first argument.
        """
        with self._lock:
            if self._state == SandboxState.RUNNING:
                return SandboxResult(
                    module_name=self.module_name,
                    state=SandboxState.FAILED,
                    exception="Sandbox already running",
                )
            self._state = SandboxState.RUNNING

        self._tracker = ResourceTracker(self.limits)
        self._tracker.start()
        errors: List[str] = []
        events = 0

        try:
            result_value = func(self._tracker, **kwargs)
            if isinstance(result_value, int):
                events = result_value

            violation = self._tracker.check_limits()
            if violation:
                self._state = SandboxState.TIMED_OUT if "timeout" in violation.lower() else SandboxState.FAILED
                return self._make_result(
                    state=self._state,
                    events=events,
                    errors=[violation],
                    exception=violation,
                )

            self._state = SandboxState.COMPLETED
            result = self._make_result(
                state=SandboxState.COMPLETED,
                events=events,
                errors=errors,
            )

        except Exception as e:
            self._state = SandboxState.FAILED
            tb = traceback.format_exc()
            log.error("Module '%s' sandbox error: %s", self.module_name, e)
            result = self._make_result(
                state=SandboxState.FAILED,
                events=events,
                errors=[str(e)],
                exception=f"{type(e).__name__}: {e}",
            )

        for cb in self._callbacks:
            try:
                cb(result)
            except Exception as e:
                log.error("Sandbox callback error: %s", e)

        return result

    def execute_with_timeout(self, func: Callable[..., Any], **kwargs: Any) -> SandboxResult:
        """Execute with enforced timeout using a thread."""
        result_holder: List[SandboxResult] = []

        def _run():
            r = self.execute(func, **kwargs)
            result_holder.append(r)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=self.limits.max_execution_seconds)

        if thread.is_alive():
            self._state = SandboxState.TIMED_OUT
            return SandboxResult(
                module_name=self.module_name,
                state=SandboxState.TIMED_OUT,
                duration_seconds=self.limits.max_execution_seconds,
                exception=f"Execution timed out after {self.limits.max_execution_seconds}s",
                resource_usage=self._tracker.get_usage(),
            )

        if result_holder:
            return result_holder[0]

        return SandboxResult(
            module_name=self.module_name,
            state=SandboxState.FAILED,
            exception="No result from execution",
        )

    def _make_result(
        self,
        state: SandboxState,
        events: int = 0,
        errors: Optional[List[str]] = None,
        exception: Optional[str] = None,
    ) -> SandboxResult:
        return SandboxResult(
            module_name=self.module_name,
            state=state,
            events_produced=events,
            errors=errors or [],
            duration_seconds=self._tracker.elapsed,
            exception=exception,
            resource_usage=self._tracker.get_usage(),
        )

    def reset(self) -> None:
        with self._lock:
            self._state = SandboxState.IDLE
            self._tracker = ResourceTracker(self.limits)

    def to_dict(self) -> dict:
        return {
            "module": self.module_name,
            "state": self._state.value,
            "limits": {
                "max_execution_seconds": self.limits.max_execution_seconds,
                "max_events": self.limits.max_events,
                "max_errors": self.limits.max_errors,
                "max_http_requests": self.limits.max_http_requests,
            },
            "usage": self._tracker.get_usage(),
        }


class SandboxManager:
    """Manages sandboxes for multiple modules.

    Usage:
        manager = SandboxManager(default_limits=ResourceLimits(max_execution_seconds=120))
        sandbox = manager.get_sandbox("sfp_dns")
        result = sandbox.execute(func)
    """

    def __init__(self, default_limits: Optional[ResourceLimits] = None):
        self.default_limits = default_limits or ResourceLimits()
        self._sandboxes: Dict[str, ModuleSandbox] = {}
        self._results: List[SandboxResult] = []
        self._lock = threading.Lock()

    def get_sandbox(
        self,
        module_name: str,
        limits: Optional[ResourceLimits] = None,
    ) -> ModuleSandbox:
        with self._lock:
            if module_name not in self._sandboxes:
                self._sandboxes[module_name] = ModuleSandbox(
                    module_name, limits or self.default_limits
                )
            return self._sandboxes[module_name]

    def remove_sandbox(self, module_name: str) -> bool:
        with self._lock:
            return self._sandboxes.pop(module_name, None) is not None

    def record_result(self, result: SandboxResult) -> None:
        with self._lock:
            self._results.append(result)

    def get_results(self, module_name: Optional[str] = None) -> List[SandboxResult]:
        with self._lock:
            if module_name:
                return [r for r in self._results if r.module_name == module_name]
            return list(self._results)

    @property
    def sandbox_count(self) -> int:
        with self._lock:
            return len(self._sandboxes)

    @property
    def module_names(self) -> List[str]:
        with self._lock:
            return sorted(self._sandboxes.keys())

    def get_failed_modules(self) -> List[str]:
        with self._lock:
            return [
                name for name, sb in self._sandboxes.items()
                if sb.state in (SandboxState.FAILED, SandboxState.TIMED_OUT, SandboxState.KILLED)
            ]

    def summary(self) -> dict:
        with self._lock:
            states = {}
            for sb in self._sandboxes.values():
                s = sb.state.value
                states[s] = states.get(s, 0) + 1
            return {
                "total_sandboxes": len(self._sandboxes),
                "states": states,
                "total_results": len(self._results),
                "failed_modules": self.get_failed_modules(),
            }

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "sandboxes": {name: sb.to_dict() for name, sb in self._sandboxes.items()},
                "summary": self.summary(),
            }
