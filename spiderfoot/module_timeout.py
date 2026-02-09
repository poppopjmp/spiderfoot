"""
Module execution timeout guard.

Provides a configurable per-module timeout for ``handleEvent()`` calls.
If a module exceeds its timeout, the call is interrupted and an error
event is recorded, preventing a single misbehaving module from stalling
an entire scan.

The timeout is enforced via a daemon ``threading.Timer`` that sets
a flag and logs a warning.  For truly stuck modules, a hard
``ctypes.pythonapi.PyThreadState_SetAsyncExc`` interrupt is attempted
on CPython (non-fatal, best-effort).

Usage:
    from spiderfoot.module_timeout import ModuleTimeoutGuard

    guard = ModuleTimeoutGuard(default_timeout=300)

    with guard.timed("sfp_dns", scan_id="abc123"):
        module.handleEvent(event)

    # Or as a decorator
    @guard.wrap(module_name="sfp_dns")
    def run_module(event):
        ...

Configuration:
    SF_MODULE_TIMEOUT       — default timeout in seconds (default: 300)
    SF_MODULE_TIMEOUT_HARD  — attempt hard thread interrupt (default: false)
"""
from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimeoutRecord:
    """Record of a module execution timeout."""
    module_name: str
    scan_id: str
    started: float
    timeout_seconds: float
    hard_interrupted: bool = False
    timestamp: float = field(default_factory=time.time)


class ModuleTimeoutGuard:
    """Enforces per-module execution timeouts.

    Args:
        default_timeout: Default timeout in seconds (0 = unlimited).
        hard_interrupt: Attempt to raise an exception in the stuck thread.
        module_timeouts: Per-module overrides ``{module_name: seconds}``.
    """

    def __init__(
        self,
        default_timeout: float = 300.0,
        hard_interrupt: bool = False,
        module_timeouts: Optional[Dict[str, float]] = None,
    ) -> None:
        # Config from environment
        env_timeout = os.environ.get("SF_MODULE_TIMEOUT")
        env_hard = os.environ.get("SF_MODULE_TIMEOUT_HARD", "").lower()

        self.default_timeout = float(env_timeout) if env_timeout else default_timeout
        self.hard_interrupt = env_hard in ("1", "true", "yes") or hard_interrupt
        self._module_timeouts: Dict[str, float] = module_timeouts or {}
        self._timeout_log: List[TimeoutRecord] = []
        self._max_log = 200
        self._lock = threading.Lock()

    def set_module_timeout(self, module_name: str, timeout: float) -> None:
        """Set a per-module timeout override."""
        self._module_timeouts[module_name] = timeout

    def get_timeout(self, module_name: str) -> float:
        """Get the effective timeout for a module."""
        return self._module_timeouts.get(module_name, self.default_timeout)

    @contextmanager
    def timed(self, module_name: str, scan_id: str = ""):
        """Context manager that enforces a timeout on the enclosed block.

        On timeout:
        - Logs a warning
        - Records the timeout
        - Optionally attempts a hard thread interrupt (CPython only)
        - Does NOT raise — the module continues but is flagged

        Yields immediately; the timer runs in a background daemon thread.
        """
        timeout = self.get_timeout(module_name)
        if timeout <= 0:
            yield
            return

        timed_out = threading.Event()
        caller_thread = threading.current_thread()
        start_time = time.monotonic()

        def _on_timeout() -> None:
            timed_out.set()
            elapsed = time.monotonic() - start_time
            logger.warning(
                "Module %s exceeded timeout of %.1fs (elapsed: %.1fs) scan=%s",
                module_name, timeout, elapsed, scan_id,
            )

            hard = False
            if self.hard_interrupt:
                hard = self._try_hard_interrupt(caller_thread)

            record = TimeoutRecord(
                module_name=module_name,
                scan_id=scan_id,
                started=start_time,
                timeout_seconds=timeout,
                hard_interrupted=hard,
            )
            with self._lock:
                self._timeout_log.append(record)
                if len(self._timeout_log) > self._max_log:
                    self._timeout_log = self._timeout_log[-self._max_log:]

        timer = threading.Timer(timeout, _on_timeout)
        timer.daemon = True
        timer.start()

        try:
            yield
        finally:
            timer.cancel()
            if timed_out.is_set():
                elapsed = time.monotonic() - start_time
                logger.info(
                    "Module %s completed after timeout (%.1fs) scan=%s",
                    module_name, elapsed, scan_id,
                )

    def wrap(
        self,
        module_name: str,
        scan_id: str = "",
    ) -> Callable:
        """Decorator that wraps a function with timeout enforcement."""
        def decorator(fn: Callable) -> Callable:
            @wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                sid = scan_id or kwargs.get("scan_id", "")
                with self.timed(module_name, scan_id=sid):
                    return fn(*args, **kwargs)
            return wrapper
        return decorator

    @staticmethod
    def _try_hard_interrupt(thread: threading.Thread) -> bool:
        """Attempt to raise a TimeoutError in the target thread (CPython only)."""
        try:
            thread_id = thread.ident
            if thread_id is None:
                return False
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(thread_id),
                ctypes.py_object(TimeoutError),
            )
            if res == 1:
                logger.info("Hard interrupt sent to thread %s", thread_id)
                return True
            elif res > 1:
                # Revert if more than one thread affected (shouldn't happen)
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_ulong(thread_id), None
                )
            return False
        except Exception as exc:
            logger.debug("Hard interrupt failed: %s", exc)
            return False

    # ── Query ────────────────────────────────────────────────────
    def get_timeout_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent timeout records."""
        with self._lock:
            records = self._timeout_log[-limit:]
        return [
            {
                "module": r.module_name,
                "scan_id": r.scan_id,
                "timeout_seconds": r.timeout_seconds,
                "hard_interrupted": r.hard_interrupted,
                "timestamp": r.timestamp,
            }
            for r in records
        ]

    def stats(self) -> Dict[str, Any]:
        """Summary statistics."""
        with self._lock:
            total = len(self._timeout_log)
            by_module: Dict[str, int] = {}
            for r in self._timeout_log:
                by_module[r.module_name] = by_module.get(r.module_name, 0) + 1
        return {
            "total_timeouts": total,
            "default_timeout": self.default_timeout,
            "hard_interrupt_enabled": self.hard_interrupt,
            "module_overrides": len(self._module_timeouts),
            "by_module": by_module,
        }


# ── Singleton ────────────────────────────────────────────────────────

_instance: Optional[ModuleTimeoutGuard] = None


def get_timeout_guard() -> ModuleTimeoutGuard:
    """Get or create the global ModuleTimeoutGuard instance."""
    global _instance
    if _instance is None:
        _instance = ModuleTimeoutGuard()
    return _instance
