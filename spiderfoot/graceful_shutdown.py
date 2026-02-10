"""
Graceful shutdown coordination for SpiderFoot services.

Ensures:
- Running scans are checkpointed before exit
- gRPC/HTTP connections are drained
- EventBus subscriptions are cleanly closed
- Database connections are released
- All resources are torn down in reverse-dependency order

Usage::

    from spiderfoot.graceful_shutdown import ShutdownCoordinator

    coordinator = ShutdownCoordinator()
    coordinator.register("eventbus", eventbus.close, priority=10)
    coordinator.register("database", db.close, priority=20)
    coordinator.install_signal_handlers()

    # On SIGTERM/SIGINT:
    #   1. Sets shutdown flag (coordinator.is_shutting_down == True)
    #   2. Waits for drain_timeout for in-flight requests
    #   3. Calls registered handlers in priority order (low → high)
    #   4. Logs teardown summary
"""
from __future__ import annotations

import asyncio
import atexit
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("spiderfoot.graceful_shutdown")


@dataclass
class ShutdownHandler:
    """Registered teardown handler."""
    name: str
    callback: Callable[[], Any]
    priority: int = 50  # Lower = executed first
    timeout: float = 10.0  # Max seconds for this handler
    async_handler: bool = False


@dataclass
class ShutdownResult:
    """Result of a complete shutdown sequence."""
    handlers_executed: int = 0
    handlers_failed: int = 0
    total_duration: float = 0.0
    errors: list[tuple[str, str]] = field(default_factory=list)
    signal_received: str | None = None


class ShutdownCoordinator:
    """Coordinates graceful shutdown of all service components.

    Handlers are executed in priority order (lowest first), ensuring
    that dependent services are torn down before their dependencies.
    For example:
        - priority 10: stop accepting new requests
        - priority 20: drain in-flight requests
        - priority 30: flush metrics/logs
        - priority 40: close EventBus
        - priority 50: close database connections
        - priority 60: cleanup temp files

    Thread-safe: handlers can be registered from any thread.
    """

    def __init__(
        self,
        *,
        drain_timeout: float = 15.0,
        force_timeout: float = 30.0,
    ):
        """
        Args:
            drain_timeout: Seconds to wait for in-flight work after signal.
            force_timeout: Max total shutdown time before forced exit.
        """
        self._handlers: list[ShutdownHandler] = []
        self._lock = threading.Lock()
        self._shutting_down = threading.Event()
        self._shutdown_complete = threading.Event()
        self._drain_timeout = drain_timeout
        self._force_timeout = force_timeout
        self._in_flight = 0
        self._in_flight_lock = threading.Lock()
        self._result: ShutdownResult | None = None
        self._signals_installed = False

    # ── Registration ──────────────────────────────────────────────

    def register(
        self,
        name: str,
        callback: Callable[[], Any],
        *,
        priority: int = 50,
        timeout: float = 10.0,
        async_handler: bool = False,
    ) -> None:
        """Register a shutdown handler.

        Args:
            name: Human-readable handler name (for logging).
            callback: Callable to invoke during shutdown.
            priority: Execution order (lower = earlier). Defaults to 50.
            timeout: Max seconds for this handler. Defaults to 10.
            async_handler: True if callback is a coroutine function.
        """
        handler = ShutdownHandler(
            name=name,
            callback=callback,
            priority=priority,
            timeout=timeout,
            async_handler=async_handler,
        )
        with self._lock:
            self._handlers.append(handler)
            self._handlers.sort(key=lambda h: h.priority)
        log.debug("Registered shutdown handler: %s (priority=%d)", name, priority)

    def unregister(self, name: str) -> bool:
        """Remove a handler by name."""
        with self._lock:
            before = len(self._handlers)
            self._handlers = [h for h in self._handlers if h.name != name]
            return len(self._handlers) < before

    # ── In-flight tracking ────────────────────────────────────────

    def track_request(self) -> bool:
        """Increment in-flight counter. Returns False if shutting down."""
        if self._shutting_down.is_set():
            return False
        with self._in_flight_lock:
            self._in_flight += 1
        return True

    def release_request(self) -> None:
        """Decrement in-flight counter."""
        with self._in_flight_lock:
            self._in_flight = max(0, self._in_flight - 1)

    @property
    def is_shutting_down(self) -> bool:
        """True once a shutdown signal has been received."""
        return self._shutting_down.is_set()

    @property
    def in_flight_count(self) -> int:
        with self._in_flight_lock:
            return self._in_flight

    # ── Signal installation ───────────────────────────────────────

    def install_signal_handlers(self) -> None:
        """Install SIGTERM/SIGINT handlers (main thread only)."""
        if self._signals_installed:
            return

        if threading.current_thread() is not threading.main_thread():
            log.warning("Signal handlers can only be installed from the main thread")
            return

        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            atexit.register(self._atexit_handler)
            self._signals_installed = True
            log.info("Shutdown signal handlers installed (SIGTERM, SIGINT)")
        except (OSError, ValueError) as exc:
            log.warning("Could not install signal handlers: %s", exc)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle SIGTERM/SIGINT."""
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        log.info("Received %s — initiating graceful shutdown", sig_name)

        # Run shutdown in a separate thread to avoid blocking signal handler
        t = threading.Thread(
            target=self._execute_shutdown,
            args=(sig_name,),
            daemon=True,
            name="shutdown-coordinator",
        )
        t.start()

        # Wait for shutdown to complete or force exit
        if not self._shutdown_complete.wait(timeout=self._force_timeout):
            log.error("Shutdown timed out after %.0fs — forcing exit", self._force_timeout)
            os._exit(1)

    def _atexit_handler(self) -> None:
        """Fallback: run handlers on normal interpreter exit."""
        if not self._shutting_down.is_set():
            self._execute_shutdown("atexit")

    # ── Shutdown execution ────────────────────────────────────────

    def _execute_shutdown(self, signal_name: str = "manual") -> ShutdownResult:
        """Execute all shutdown handlers in order."""
        if self._shutting_down.is_set():
            if self._result:
                return self._result
            return ShutdownResult()

        self._shutting_down.set()
        result = ShutdownResult(signal_received=signal_name)
        start = time.monotonic()

        log.info("=== Graceful shutdown initiated (%s) ===", signal_name)

        # Phase 1: Drain in-flight requests
        if self._in_flight > 0:
            log.info("Draining %d in-flight requests (timeout=%.0fs)...",
                     self._in_flight, self._drain_timeout)
            drain_start = time.monotonic()
            while self._in_flight > 0:
                if time.monotonic() - drain_start > self._drain_timeout:
                    log.warning("Drain timeout — %d requests still in-flight",
                                self._in_flight)
                    break
                time.sleep(0.1)

        # Phase 2: Execute handlers in priority order
        with self._lock:
            handlers = list(self._handlers)

        for handler in handlers:
            handler_start = time.monotonic()
            try:
                log.info("  [%d] Shutting down: %s", handler.priority, handler.name)
                if handler.async_handler:
                    self._run_async_handler(handler)
                else:
                    handler.callback()
                duration = time.monotonic() - handler_start
                log.info("  [OK] %s (%.1fs)", handler.name, duration)
                result.handlers_executed += 1
            except Exception as exc:
                duration = time.monotonic() - handler_start
                log.error("  [FAIL] %s: %s (%.1fs)", handler.name, exc, duration)
                result.handlers_failed += 1
                result.errors.append((handler.name, str(exc)))

        result.total_duration = time.monotonic() - start
        log.info(
            "=== Shutdown complete: %d/%d handlers OK (%.1fs) ===",
            result.handlers_executed,
            result.handlers_executed + result.handlers_failed,
            result.total_duration,
        )

        self._result = result
        self._shutdown_complete.set()
        return result

    @staticmethod
    def _run_async_handler(handler: ShutdownHandler) -> None:
        """Run an async handler synchronously."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(1) as pool:
                    pool.submit(asyncio.run, handler.callback()).result(
                        timeout=handler.timeout
                    )
            else:
                loop.run_until_complete(
                    asyncio.wait_for(handler.callback(), timeout=handler.timeout)
                )
        except RuntimeError:
            asyncio.run(handler.callback())

    def shutdown(self, reason: str = "manual") -> ShutdownResult:
        """Manually trigger shutdown (for programmatic use)."""
        return self._execute_shutdown(reason)

    # ── Info ───────────────────────────────────────────────────────

    def handler_summary(self) -> list[dict[str, Any]]:
        """Return registered handlers for diagnostics."""
        with self._lock:
            return [
                {
                    "name": h.name,
                    "priority": h.priority,
                    "timeout": h.timeout,
                    "async": h.async_handler,
                }
                for h in self._handlers
            ]

    def registered_services(self) -> list[str]:
        """Return names of registered shutdown handlers."""
        with self._lock:
            return [h.name for h in self._handlers]

    def status(self) -> dict[str, Any]:
        """Return shutdown manager status dict (compat with ShutdownManager API)."""
        return {
            "shutting_down": self._shutting_down,
            "in_flight_requests": self._in_flight,
            "handlers": self.handler_summary(),
        }


# ── Singleton ─────────────────────────────────────────────────────

_coordinator: ShutdownCoordinator | None = None
_coordinator_lock = threading.Lock()


def get_shutdown_coordinator(**kwargs: Any) -> ShutdownCoordinator:
    """Get or create the global ShutdownCoordinator."""
    global _coordinator
    if _coordinator is None:
        with _coordinator_lock:
            if _coordinator is None:
                _coordinator = ShutdownCoordinator(**kwargs)
    return _coordinator
