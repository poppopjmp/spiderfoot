"""
Graceful shutdown manager for SpiderFoot.

Coordinates orderly shutdown of all background services when the process
receives SIGINT/SIGTERM or the FastAPI app shuts down.  Services register
shutdown callbacks during startup; the manager invokes them in reverse
registration order (LIFO) so that high-level consumers stop before the
infrastructure they depend on.

Usage:
    from spiderfoot.shutdown_manager import get_shutdown_manager

    mgr = get_shutdown_manager()
    mgr.register("RecurringScheduler", scheduler.stop)
    mgr.register("EventBus", eventbus.close, timeout=10.0)

    # At shutdown (called automatically via atexit / signal handlers):
    mgr.shutdown()
"""
import atexit
import logging
import signal
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

log = logging.getLogger("spiderfoot.shutdown_manager")


@dataclass
class _ShutdownEntry:
    """A registered shutdown callback."""
    name: str
    callback: Callable[[], None]
    timeout: float = 5.0
    order: int = 0  # higher = later shutdown


class ShutdownManager:
    """Coordinates graceful shutdown of registered background services.

    Thread-safe.  Callbacks are invoked once in LIFO order; duplicate
    ``shutdown()`` calls are ignored.
    """

    def __init__(self) -> None:
        self._entries: List[_ShutdownEntry] = []
        self._lock = threading.Lock()
        self._shutting_down = False
        self._completed = False
        self._results: Dict[str, str] = {}

    # ── Registration ─────────────────────────────────────────────────

    def register(
        self,
        name: str,
        callback: Callable[[], None],
        *,
        timeout: float = 5.0,
        order: int = 0,
    ) -> None:
        """Register a shutdown callback.

        Args:
            name: Human-readable service name (for logging).
            callback: Zero-arg callable invoked at shutdown.
            timeout: Max seconds to wait for the callback.
            order: Lower values shut down first; same-order entries
                   use LIFO (last-registered-first).
        """
        with self._lock:
            if self._shutting_down:
                log.warning("Cannot register '%s' — shutdown already in progress", name)
                return
            self._entries.append(_ShutdownEntry(
                name=name, callback=callback, timeout=timeout, order=order,
            ))
            log.debug("Registered shutdown callback: %s (order=%d, timeout=%.1fs)",
                      name, order, timeout)

    def unregister(self, name: str) -> bool:
        """Remove a previously registered callback by name."""
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.name != name]
            removed = len(self._entries) < before
            if removed:
                log.debug("Unregistered shutdown callback: %s", name)
            return removed

    # ── Shutdown execution ───────────────────────────────────────────

    def shutdown(self, reason: str = "requested") -> Dict[str, str]:
        """Execute all registered shutdown callbacks.

        Returns a dict of {service_name: status} where status is one of
        ``"ok"``, ``"error: ..."``, or ``"timeout"``.

        Safe to call multiple times — only the first call runs callbacks.
        """
        with self._lock:
            if self._completed:
                return dict(self._results)
            if self._shutting_down:
                return {"_status": "already in progress"}
            self._shutting_down = True
            # Snapshot entries in shutdown order (stable sort: order ASC, then LIFO)
            entries = list(reversed(self._entries))
            entries.sort(key=lambda e: e.order)

        log.info("Graceful shutdown started (reason=%s, services=%d)", reason, len(entries))
        start = time.monotonic()

        results: Dict[str, str] = {}
        for entry in entries:
            status = self._run_callback(entry)
            results[entry.name] = status

        elapsed = time.monotonic() - start
        log.info("Graceful shutdown completed in %.2fs: %s", elapsed, results)

        with self._lock:
            self._results = results
            self._completed = True

        return results

    @staticmethod
    def _run_callback(entry: _ShutdownEntry) -> str:
        """Run a single shutdown callback with timeout protection."""
        log.info("Shutting down: %s (timeout=%.1fs)", entry.name, entry.timeout)
        result_holder: List[str] = ["timeout"]

        def _target():
            try:
                entry.callback()
                result_holder[0] = "ok"
            except Exception as exc:
                result_holder[0] = f"error: {exc}"
                log.error("Shutdown error in '%s': %s", entry.name, exc)

        t = threading.Thread(target=_target, name=f"shutdown-{entry.name}", daemon=True)
        t.start()
        t.join(timeout=entry.timeout)
        if t.is_alive():
            log.warning("Shutdown timeout for '%s' after %.1fs", entry.name, entry.timeout)
        return result_holder[0]

    # ── Introspection ────────────────────────────────────────────────

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    def registered_services(self) -> List[str]:
        """Return names of all registered services."""
        with self._lock:
            return [e.name for e in self._entries]

    def status(self) -> dict:
        """Return shutdown manager status for health endpoints."""
        with self._lock:
            return {
                "shutting_down": self._shutting_down,
                "completed": self._completed,
                "registered_services": [e.name for e in self._entries],
                "results": dict(self._results) if self._results else None,
            }


# ── Singleton ───────────────────────────────────────────────────────

_manager: Optional[ShutdownManager] = None
_manager_lock = threading.Lock()


def get_shutdown_manager() -> ShutdownManager:
    """Get or create the global ShutdownManager singleton."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = ShutdownManager()
                _install_signal_handlers(_manager)
                atexit.register(_manager.shutdown, reason="atexit")
    return _manager


def _install_signal_handlers(mgr: ShutdownManager) -> None:
    """Install SIGINT/SIGTERM handlers that trigger graceful shutdown."""
    def _handler(signum, frame):
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        log.info("Received signal %s — initiating graceful shutdown", sig_name)
        # Run shutdown in a separate thread to avoid blocking the signal handler
        threading.Thread(
            target=mgr.shutdown,
            kwargs={"reason": f"signal:{sig_name}"},
            daemon=True,
        ).start()

    try:
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
        log.debug("Signal handlers installed for graceful shutdown")
    except (OSError, ValueError):
        # Cannot set signal handlers outside main thread
        log.debug("Could not install signal handlers (not main thread)")
