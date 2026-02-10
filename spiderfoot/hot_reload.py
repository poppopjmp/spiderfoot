#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         hot_reload
# Purpose:      Module hot-reload for SpiderFoot.
#               Monitors module files for changes and reloads them
#               at runtime without requiring a full restart.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Module Hot-Reload

Watches the modules/ directory for changes and reloads modified modules
without restarting the application. Supports:

    - File modification detection (polling-based, no external deps)
    - Safe reload with validation (syntax check before swap)
    - Callback hooks for pre/post reload
    - Module version tracking
    - Reload history and rollback info

Usage::

    from spiderfoot.hot_reload import ModuleWatcher

    watcher = ModuleWatcher("/path/to/modules")
    watcher.on_reload(lambda name, mod: print(f"Reloaded {name}"))
    watcher.start()

    # Later
    watcher.stop()
"""

import importlib
import importlib.util
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("spiderfoot.hot_reload")


@dataclass
class ModuleState:
    """Tracked state of a module file."""
    filepath: str
    module_name: str
    last_modified: float = 0.0
    last_size: int = 0
    loaded_at: float = 0.0
    reload_count: int = 0
    last_error: Optional[str] = None
    module_obj: Optional[Any] = None


@dataclass
class ReloadEvent:
    """Record of a module reload."""
    module_name: str
    filepath: str
    timestamp: float
    success: bool
    error: Optional[str] = None
    duration_ms: float = 0.0


class ModuleWatcher:
    """Watches module directory and reloads modified modules.

    Uses polling (os.stat) to detect file changes — no external
    dependencies like watchdog or inotify required.
    """

    def __init__(self, modules_dir: str = "modules", *,
                 poll_interval: float = 2.0,
                 pattern: str = "sfp_*.py",
                 auto_start: bool = False) -> None:
        """
        Args:
            modules_dir: Path to modules directory.
            poll_interval: Seconds between file checks.
            pattern: Glob pattern for module files.
            auto_start: Start watching immediately.
        """
        self.modules_dir = os.path.abspath(modules_dir)
        self.poll_interval = poll_interval
        self.pattern = pattern

        self._states: dict[str, ModuleState] = {}
        self._history: list[ReloadEvent] = []
        self._callbacks: list[Callable] = []
        self._error_callbacks: list[Callable] = []

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Initial scan
        self._scan_files()

        if auto_start:
            self.start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the file watcher thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._watch_loop,
            name="module-watcher",
            daemon=True)
        self._thread.start()
        log.info("Module watcher started: %s (interval=%.1fs)",
                 self.modules_dir, self.poll_interval)

    def stop(self) -> None:
        """Stop the file watcher."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.poll_interval * 2)
            self._thread = None
        log.info("Module watcher stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_reload(self, callback: Callable) -> None:
        """Register a callback for successful reloads.

        Callback signature: (module_name: str, module_obj: Any) -> None
        """
        self._callbacks.append(callback)

    def on_error(self, callback: Callable) -> None:
        """Register a callback for reload errors.

        Callback signature: (module_name: str, error: str) -> None
        """
        self._error_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Manual operations
    # ------------------------------------------------------------------

    def reload_module(self, module_name: str) -> bool:
        """Manually trigger a reload of a specific module.

        Returns True on success.
        """
        state = self._states.get(module_name)
        if not state:
            log.warning("Module not tracked: %s", module_name)
            return False

        return self._reload(state)

    def reload_all(self) -> dict[str, bool]:
        """Reload all tracked modules. Returns name->success map."""
        results = {}
        for name, state in self._states.items():
            results[name] = self._reload(state)
        return results

    def check_now(self) -> list[str]:
        """Check for changes immediately. Returns list of reloaded modules."""
        return self._check_changes()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def tracked_modules(self) -> list[str]:
        """Get list of tracked module names."""
        return sorted(self._states.keys())

    def get_state(self, module_name: str) -> Optional[ModuleState]:
        """Get the tracked state of a module."""
        return self._states.get(module_name)

    def get_history(self, limit: int = 50) -> list[ReloadEvent]:
        """Get reload history, most recent first."""
        return list(reversed(self._history[-limit:]))

    @property
    def stats(self) -> dict:
        total_reloads = sum(s.reload_count
                            for s in self._states.values())
        errors = sum(1 for s in self._states.values()
                     if s.last_error)
        return {
            "modules_tracked": len(self._states),
            "total_reloads": total_reloads,
            "modules_with_errors": errors,
            "is_running": self._running,
            "poll_interval": self.poll_interval,
            "history_length": len(self._history),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _scan_files(self) -> None:
        """Scan directory for module files and initialize tracking."""
        if not os.path.isdir(self.modules_dir):
            log.warning("Modules directory not found: %s",
                        self.modules_dir)
            return

        import glob
        file_pattern = os.path.join(self.modules_dir, self.pattern)

        for filepath in glob.glob(file_pattern):
            name = os.path.basename(filepath).replace(".py", "")
            if name not in self._states:
                try:
                    stat = os.stat(filepath)
                    self._states[name] = ModuleState(
                        filepath=filepath,
                        module_name=name,
                        last_modified=stat.st_mtime,
                        last_size=stat.st_size,
                    )
                except OSError:
                    pass

        log.debug("Tracking %d module files", len(self._states))

    def _watch_loop(self) -> None:
        """Background polling loop."""
        while self._running:
            try:
                self._check_changes()
            except Exception as e:
                log.error("Watch loop error: %s", e)

            # Sleep in small increments for responsive shutdown
            waited = 0.0
            while waited < self.poll_interval and self._running:
                time.sleep(min(0.5, self.poll_interval - waited))
                waited += 0.5

    def _check_changes(self) -> list[str]:
        """Check all tracked files for modifications."""
        reloaded = []

        # Also check for new files
        self._scan_files()

        with self._lock:
            for name, state in list(self._states.items()):
                try:
                    stat = os.stat(state.filepath)
                except FileNotFoundError:
                    log.info("Module file removed: %s", name)
                    continue

                if (stat.st_mtime > state.last_modified or
                        stat.st_size != state.last_size):
                    log.info("Change detected: %s (mtime %.0f -> %.0f)",
                             name, state.last_modified, stat.st_mtime)

                    if self._reload(state):
                        state.last_modified = stat.st_mtime
                        state.last_size = stat.st_size
                        reloaded.append(name)
                    else:
                        # Update stat even on error to avoid retry spam
                        state.last_modified = stat.st_mtime
                        state.last_size = stat.st_size

        return reloaded

    def _reload(self, state: ModuleState) -> bool:
        """Reload a single module with validation."""
        start = time.time()

        # Step 1: Syntax check
        try:
            with open(state.filepath, encoding="utf-8") as f:
                source = f.read()
            compile(source, state.filepath, "exec")
        except SyntaxError as e:
            error_msg = f"Syntax error: {e}"
            self._record_failure(state, error_msg, start)
            return False

        # Step 2: Import/reload
        try:
            if state.module_name in sys.modules:
                # Reload existing module
                mod = sys.modules[state.module_name]
                mod = importlib.reload(mod)
            else:
                # Fresh import
                spec = importlib.util.spec_from_file_location(
                    state.module_name, state.filepath)
                if spec is None or spec.loader is None:
                    self._record_failure(
                        state, "Failed to create module spec", start)
                    return False

                mod = importlib.util.module_from_spec(spec)
                sys.modules[state.module_name] = mod
                spec.loader.exec_module(mod)

            state.module_obj = mod
            state.reload_count += 1
            state.loaded_at = time.time()
            state.last_error = None

            duration = (time.time() - start) * 1000
            self._history.append(ReloadEvent(
                module_name=state.module_name,
                filepath=state.filepath,
                timestamp=time.time(),
                success=True,
                duration_ms=duration,
            ))

            log.info("Reloaded %s (%.1fms, reload #%d)",
                     state.module_name, duration, state.reload_count)

            # Notify callbacks
            for cb in self._callbacks:
                try:
                    cb(state.module_name, mod)
                except Exception as e:
                    log.debug("Reload callback error: %s", e)

            return True

        except Exception as e:
            self._record_failure(state, str(e), start)
            return False

    def _record_failure(self, state: ModuleState,
                        error: str, start_time: float) -> None:
        """Record a reload failure."""
        duration = (time.time() - start_time) * 1000
        state.last_error = error

        self._history.append(ReloadEvent(
            module_name=state.module_name,
            filepath=state.filepath,
            timestamp=time.time(),
            success=False,
            error=error,
            duration_ms=duration,
        ))

        log.error("Failed to reload %s: %s",
                  state.module_name, error)

        for cb in self._error_callbacks:
            try:
                cb(state.module_name, error)
            except Exception as e:
                log.debug("error callback cb(module_name, error) failed: %s", e)

    # ------------------------------------------------------------------
    # Trim history
    # ------------------------------------------------------------------

    def trim_history(self, keep: int = 100) -> int:
        """Trim reload history to last N entries. Returns removed count."""
        if len(self._history) <= keep:
            return 0
        removed = len(self._history) - keep
        self._history = self._history[-keep:]
        return removed
