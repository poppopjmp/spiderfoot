# -------------------------------------------------------------------------------
# Name:         spiderfoot/memory.py
# Purpose:      Memory and resource management utilities (ROADMAP Cycles 111-130)
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2025-07-11
# Copyright:    (c) Agostino Panico 2025
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Memory & resource management utilities for SpiderFoot v6.

Implements ROADMAP Cycles 111-130:

- **Cycle 111:** `SlottedEvent`, `SlottedPluginState` – ``__slots__`` mixins to
  reduce per-instance memory overhead in long-running scans.
- **Cycle 112:** `StreamingResultSet` – server-side cursor wrapper that yields
  batches of scan results without loading the full result set into memory.
- **Cycle 113:** `LazyImporter` – deferred import helper that delays heavy
  third-party modules (``requests``, ``bs4``, ``lxml``, etc.) until first use.
- **Cycle 114:** `CachedHelpers` – LRU-cached wrappers for frequently-called
  ``SpiderFootHelpers`` methods (``urlBaseUrl``, ``validEmail``, etc.).
- **Cycle 115:** `CeleryMemoryGuard` – runtime memory watchdog that can be
  polled inside long-running tasks to trigger voluntary restarts before the
  hard ``max-memory-per-child`` kill.
- **Cycles 116-130:** `MemoryProfiler`, `AllocationTracker`,
  `ObjectSizeAnalyzer`, `GCTuner`, `WeakEventCache` – profiling and
  optimization utilities for identifying and reducing top memory allocators.
"""

from __future__ import annotations

import functools
import gc
import logging
import os
import re
import sys
import threading
import time
import weakref
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Generator, Iterator

log = logging.getLogger("spiderfoot.ops.memory")


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 111 — __slots__ mixins for high-traffic objects
# ═══════════════════════════════════════════════════════════════════════════

class SlottedEvent:
    """Lightweight event container using ``__slots__`` to reduce memory.

    Each ``SpiderFootEvent`` instance exists for the lifetime of a scan.
    A large scan can generate 100k+ events, so reducing per-instance
    overhead from ~400 bytes (dict) to ~120 bytes (slots) has a
    measurable impact.

    This class is intended as a drop-in value holder; modules should
    still use :class:`SpiderFootEvent` for event dispatch.  The scan
    result pipeline can convert to ``SlottedEvent`` for storage/cache.
    """

    __slots__ = (
        "event_type",
        "data",
        "module",
        "source_event",
        "confidence",
        "visibility",
        "risk",
        "generated",
        "hash",
        "source_hash",
        "scan_id",
        "_extra",
    )

    def __init__(
        self,
        event_type: str,
        data: str,
        module: str = "",
        source_event: SlottedEvent | None = None,
        *,
        confidence: int = 100,
        visibility: int = 100,
        risk: int = 0,
        generated: float | None = None,
        hash: str = "",
        source_hash: str = "",
        scan_id: str = "",
    ) -> None:
        self.event_type = event_type
        self.data = data
        self.module = module
        self.source_event = source_event
        self.confidence = confidence
        self.visibility = visibility
        self.risk = risk
        self.generated = generated or time.time()
        self.hash = hash
        self.source_hash = source_hash
        self.scan_id = scan_id
        self._extra = None  # lazy dict for rare attrs

    def set_extra(self, key: str, value: Any) -> None:
        """Store an infrequently-used attribute in overflow dict."""
        if self._extra is None:
            self._extra = {}
        self._extra[key] = value

    def get_extra(self, key: str, default: Any = None) -> Any:
        if self._extra is None:
            return default
        return self._extra.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict for JSON / DB storage."""
        d = {
            "event_type": self.event_type,
            "data": self.data,
            "module": self.module,
            "confidence": self.confidence,
            "visibility": self.visibility,
            "risk": self.risk,
            "generated": self.generated,
            "hash": self.hash,
            "source_hash": self.source_hash,
            "scan_id": self.scan_id,
        }
        if self._extra:
            d.update(self._extra)
        return d

    def __repr__(self) -> str:
        return f"SlottedEvent({self.event_type!r}, data_len={len(self.data)}, module={self.module!r})"


class SlottedPluginState:
    """Minimal per-plugin scan state using ``__slots__``.

    Replaces the ``dict``-based attribute accumulation that occurs as
    ``SpiderFootPlugin`` instances process events during a scan.
    """

    __slots__ = (
        "module_name",
        "scan_id",
        "events_received",
        "events_produced",
        "errors",
        "started_at",
        "last_activity",
        "peak_memory_kb",
    )

    def __init__(self, module_name: str, scan_id: str = "") -> None:
        self.module_name = module_name
        self.scan_id = scan_id
        self.events_received = 0
        self.events_produced = 0
        self.errors = 0
        self.started_at = time.time()
        self.last_activity = self.started_at
        self.peak_memory_kb = 0

    def record_event_received(self) -> None:
        self.events_received += 1
        self.last_activity = time.time()

    def record_event_produced(self) -> None:
        self.events_produced += 1
        self.last_activity = time.time()

    def record_error(self) -> None:
        self.errors += 1

    def update_memory(self, current_kb: int) -> None:
        if current_kb > self.peak_memory_kb:
            self.peak_memory_kb = current_kb

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_name": self.module_name,
            "scan_id": self.scan_id,
            "events_received": self.events_received,
            "events_produced": self.events_produced,
            "errors": self.errors,
            "duration_s": round(time.time() - self.started_at, 2),
            "peak_memory_kb": self.peak_memory_kb,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 112 — Streaming large result sets
# ═══════════════════════════════════════════════════════════════════════════

class StreamingResultSet:
    """Server-side cursor wrapper for streaming DB results.

    Instead of ``dbh.scanResultEvent(scan_id)`` loading all rows into a
    Python list, this class uses a *named server-side cursor* (PostgreSQL
    ``DECLARE … CURSOR``) and fetches in configurable batches.

    Usage::

        srs = StreamingResultSet(conn, "SELECT * FROM tbl_scan_results WHERE scan_instance_id=%s", [scan_id])
        for batch in srs.iter_batches():
            for row in batch:
                process(row)
    """

    def __init__(
        self,
        conn: Any,
        query: str,
        params: tuple | list | None = None,
        *,
        batch_size: int = 500,
        cursor_name: str | None = None,
    ) -> None:
        self.conn = conn
        self.query = query
        self.params = params or ()
        self.batch_size = batch_size
        self.cursor_name = cursor_name or f"sf_stream_{id(self)}"
        self._total_yielded = 0
        self._closed = False

    def iter_batches(self) -> Generator[list[tuple], None, None]:
        """Yield batches of rows from a server-side cursor.

        Each batch is a list of up to ``batch_size`` tuples.  The cursor
        is automatically closed when iteration completes.
        """
        cursor = None
        try:
            cursor = self.conn.cursor(name=self.cursor_name)
            cursor.itersize = self.batch_size
            cursor.execute(self.query, self.params)

            while True:
                batch = cursor.fetchmany(self.batch_size)
                if not batch:
                    break
                self._total_yielded += len(batch)
                yield batch
        except Exception:
            log.exception("StreamingResultSet error on cursor %s", self.cursor_name)
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            self._closed = True

    def iter_rows(self) -> Generator[tuple, None, None]:
        """Yield individual rows (convenience wrapper)."""
        for batch in self.iter_batches():
            yield from batch

    @property
    def total_yielded(self) -> int:
        return self._total_yielded

    @property
    def is_closed(self) -> bool:
        return self._closed


class StreamingJsonEncoder:
    """Incremental JSON array encoder for large result sets.

    Produces a valid JSON array ``[{...}, {...}, ...]`` one object at a
    time, suitable for ``StreamingResponse`` in FastAPI.

    Usage::

        encoder = StreamingJsonEncoder()
        for chunk in encoder.encode_iter(row_generator()):
            yield chunk
    """

    def __init__(self, indent: bool = False) -> None:
        self._indent = indent
        self._count = 0

    def encode_iter(
        self,
        rows: Iterator[dict[str, Any]],
        *,
        json_dumps: Callable[..., str] | None = None,
    ) -> Generator[str, None, None]:
        """Yield JSON fragments forming a valid array.

        Args:
            rows: Iterator of dicts to encode.
            json_dumps: Optional custom ``json.dumps`` callable.

        Yields:
            Successive JSON string fragments.
        """
        import json as _json

        dumps = json_dumps or (
            functools.partial(_json.dumps, indent=2, default=str)
            if self._indent
            else functools.partial(_json.dumps, default=str)
        )

        yield "[\n" if self._indent else "["
        first = True
        for row in rows:
            if not first:
                yield ",\n" if self._indent else ","
            first = False
            yield dumps(row)
            self._count += 1
        yield "\n]" if self._indent else "]"

    @property
    def count(self) -> int:
        return self._count


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 113 — Lazy imports in handleEvent
# ═══════════════════════════════════════════════════════════════════════════

class LazyImporter:
    """Thread-safe deferred module importer.

    Heavy third-party packages (``requests``, ``bs4``, ``lxml``, ``dns``,
    ``netaddr``, ``phonenumbers``) should be imported *lazily* inside
    ``handleEvent()`` rather than at module-level so that:

    1. Worker processes that never execute a particular module don't
       pay the import cost.
    2. Memory is only allocated when the module is actually needed.

    Usage::

        _lazy = LazyImporter()

        class sfp_example(SpiderFootPlugin):
            def handleEvent(self, event):
                requests = _lazy.get("requests")
                resp = requests.get(url)

    The actual ``import`` happens exactly once, subsequent calls return
    the cached module object.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._lock = threading.Lock()

    def get(self, module_name: str) -> Any:
        """Import and cache a module by name.

        Thread-safe — concurrent calls for the same module will block
        until the first import completes, then return the cached result.
        """
        mod = self._cache.get(module_name)
        if mod is not None:
            return mod

        with self._lock:
            # Double-checked locking
            mod = self._cache.get(module_name)
            if mod is not None:
                return mod

            import importlib
            mod = importlib.import_module(module_name)
            self._cache[module_name] = mod
            return mod

    def preload(self, *module_names: str) -> dict[str, bool]:
        """Pre-import a list of modules.  Returns {name: success}."""
        results: dict[str, bool] = {}
        for name in module_names:
            try:
                self.get(name)
                results[name] = True
            except ImportError:
                results[name] = False
                log.warning("LazyImporter: failed to import %s", name)
        return results

    def is_loaded(self, module_name: str) -> bool:
        return module_name in self._cache

    @property
    def loaded_modules(self) -> list[str]:
        return list(self._cache.keys())

    def unload(self, module_name: str) -> bool:
        """Remove a module from the cache (does NOT unload from ``sys.modules``)."""
        with self._lock:
            return self._cache.pop(module_name, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


# Global lazy importer instance for modules to share.
lazy = LazyImporter()


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 114 — LRU cache for SpiderFootHelpers hot methods
# ═══════════════════════════════════════════════════════════════════════════

class CachedHelpers:
    """LRU-cached wrappers for ``SpiderFootHelpers`` static methods.

    During a scan, methods like ``urlBaseUrl()`` and ``validEmail()`` can
    be called millions of times with the same arguments.  Wrapping them
    in ``functools.lru_cache`` eliminates redundant regex compilation
    and matching overhead.

    Usage::

        cached = CachedHelpers(maxsize=8192)
        base = cached.urlBaseUrl("https://example.com/path?q=1")
        # → "https://example.com"

    Cache stats are exposed via :meth:`stats` for monitoring.
    """

    def __init__(self, maxsize: int = 8192) -> None:
        self._maxsize = maxsize

        # Build cached wrappers for each method
        self.urlBaseUrl = functools.lru_cache(maxsize=maxsize)(self._urlBaseUrl)
        self.urlBaseDir = functools.lru_cache(maxsize=maxsize)(self._urlBaseDir)
        self.validEmail = functools.lru_cache(maxsize=maxsize)(self._validEmail)
        self.validPhoneNumber = functools.lru_cache(maxsize=maxsize)(self._validPhoneNumber)
        self.validLEI = functools.lru_cache(maxsize=maxsize)(self._validLEI)
        self.validIP = functools.lru_cache(maxsize=maxsize)(self._validIP)
        self.validIP6 = functools.lru_cache(maxsize=maxsize)(self._validIP6)

    # ── Wrapped methods ───────────────────────────────────────────────

    @staticmethod
    def _urlBaseUrl(url: str) -> str | None:
        """Extract scheme + domain from URL (no trailing slash)."""
        if not url or not isinstance(url, str):
            return None
        if '://' in url:
            bits = re.match(r'(\w+://.[^/:\?]*)[:/\?].*', url)
        else:
            bits = re.match(r'(.[^/:\?]*)[:/\?]', url)
        if bits is None:
            return url.lower()
        return bits.group(1).lower()

    @staticmethod
    def _urlBaseDir(url: str) -> str:
        """Extract base directory from URL."""
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rsplit('/', 1)[0] if '/' in parsed.path else ''
        return f"{parsed.scheme}://{parsed.netloc}{path}/"

    @staticmethod
    def _validEmail(email: str) -> bool:
        if not isinstance(email, str):
            return False
        if "@" not in email:
            return False
        if not re.match(
            r'^([\%a-zA-Z\.0-9_\-\+]+@[a-zA-Z\.0-9\-]+\.[a-zA-Z\.0-9\-]+)$',
            email,
        ):
            return False
        if len(email) < 6:
            return False
        if "%" in email:
            return False
        if "..." in email:
            return False
        return True

    @staticmethod
    def _validPhoneNumber(phone: str) -> bool:
        if not isinstance(phone, str):
            return False
        return bool(re.match(r'^\+?[\d\s\-\(\)]{7,15}$', phone.strip()))

    @staticmethod
    def _validLEI(lei: str) -> bool:
        if not isinstance(lei, str):
            return False
        return bool(re.match(r'^[A-Z0-9]{18}[0-9]{2}$', lei, re.IGNORECASE))

    @staticmethod
    def _validIP(address: str) -> bool:
        if not address or not isinstance(address, str):
            return False
        parts = address.split('.')
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False

    @staticmethod
    def _validIP6(address: str) -> bool:
        if not address or not isinstance(address, str):
            return False
        try:
            import ipaddress
            ipaddress.IPv6Address(address)
            return True
        except (ValueError, ipaddress.AddressValueError):
            return False

    # ── Stats ─────────────────────────────────────────────────────────

    def stats(self) -> dict[str, dict[str, int]]:
        """Return cache statistics for each wrapped method."""
        result = {}
        for name in (
            "urlBaseUrl", "urlBaseDir", "validEmail",
            "validPhoneNumber", "validLEI", "validIP", "validIP6",
        ):
            fn = getattr(self, name, None)
            if fn and hasattr(fn, "cache_info"):
                info = fn.cache_info()
                result[name] = {
                    "hits": info.hits,
                    "misses": info.misses,
                    "maxsize": info.maxsize,
                    "currsize": info.currsize,
                }
        return result

    def clear_all(self) -> None:
        """Clear all LRU caches."""
        for name in (
            "urlBaseUrl", "urlBaseDir", "validEmail",
            "validPhoneNumber", "validLEI", "validIP", "validIP6",
        ):
            fn = getattr(self, name, None)
            if fn and hasattr(fn, "cache_clear"):
                fn.cache_clear()

    def total_hits(self) -> int:
        return sum(v["hits"] for v in self.stats().values())

    def total_misses(self) -> int:
        return sum(v["misses"] for v in self.stats().values())

    def hit_rate(self) -> float:
        """Overall cache hit rate as a percentage."""
        h = self.total_hits()
        m = self.total_misses()
        total = h + m
        if total == 0:
            return 0.0
        return (h / total) * 100.0


# ═══════════════════════════════════════════════════════════════════════════
# Cycle 115 — Celery memory guard
# ═══════════════════════════════════════════════════════════════════════════

class CeleryMemoryGuard:
    """Runtime memory watchdog for Celery tasks.

    Celery's ``worker_max_memory_per_child`` terminates a worker *after*
    a task completes.  ``CeleryMemoryGuard`` provides *voluntary* early
    exit by polling RSS memory inside long-running scan tasks.

    Usage::

        guard = CeleryMemoryGuard(soft_limit_mb=1500, hard_limit_mb=1900)

        # Inside a scan loop:
        for event in events:
            process(event)
            action = guard.check()
            if action == "stop":
                raise SoftTimeLimitExceeded("Memory limit reached")
            elif action == "warn":
                gc.collect()

    The guard reads ``/proc/self/status`` on Linux or uses ``psutil``
    as a fallback.
    """

    def __init__(
        self,
        soft_limit_mb: int = 1500,
        hard_limit_mb: int = 1900,
        *,
        check_interval: int = 50,
    ) -> None:
        self.soft_limit_mb = soft_limit_mb
        self.hard_limit_mb = hard_limit_mb
        self.check_interval = check_interval
        self._check_count = 0
        self._current_rss_mb = 0.0
        self._peak_rss_mb = 0.0
        self._warnings: list[dict[str, Any]] = []

    def check(self) -> str:
        """Check current memory usage.

        Returns:
            ``"ok"``, ``"warn"`` (soft limit exceeded), or
            ``"stop"`` (hard limit exceeded).

        For performance, actual measurement only happens every
        ``check_interval`` calls; intermediate calls return the
        previous result.
        """
        self._check_count += 1
        if self._check_count % self.check_interval != 0:
            if self._current_rss_mb >= self.hard_limit_mb:
                return "stop"
            if self._current_rss_mb >= self.soft_limit_mb:
                return "warn"
            return "ok"

        self._current_rss_mb = self._get_rss_mb()
        if self._current_rss_mb > self._peak_rss_mb:
            self._peak_rss_mb = self._current_rss_mb

        if self._current_rss_mb >= self.hard_limit_mb:
            self._warnings.append({
                "level": "hard",
                "rss_mb": self._current_rss_mb,
                "timestamp": time.time(),
            })
            log.error(
                "CeleryMemoryGuard: HARD limit exceeded (%.1f MB / %d MB)",
                self._current_rss_mb,
                self.hard_limit_mb,
            )
            return "stop"

        if self._current_rss_mb >= self.soft_limit_mb:
            self._warnings.append({
                "level": "soft",
                "rss_mb": self._current_rss_mb,
                "timestamp": time.time(),
            })
            log.warning(
                "CeleryMemoryGuard: soft limit exceeded (%.1f MB / %d MB)",
                self._current_rss_mb,
                self.soft_limit_mb,
            )
            return "warn"

        return "ok"

    @staticmethod
    def _get_rss_mb() -> float:
        """Get current process RSS in MB."""
        # Fast path: /proc/self/status on Linux
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        # VmRSS:  123456 kB
                        kb = int(line.split()[1])
                        return kb / 1024.0
        except (FileNotFoundError, PermissionError, OSError):
            pass

        # Fallback: psutil
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            return proc.memory_info().rss / (1024 * 1024)
        except ImportError:
            pass

        # Last resort: resource module (Unix only)
        try:
            import resource
            # ru_maxrss is in KB on Linux, bytes on macOS
            usage = resource.getrusage(resource.RUSAGE_SELF)
            if sys.platform == "darwin":
                return usage.ru_maxrss / (1024 * 1024)
            return usage.ru_maxrss / 1024.0
        except (ImportError, AttributeError):
            pass

        return 0.0

    @property
    def current_rss_mb(self) -> float:
        return self._current_rss_mb

    @property
    def peak_rss_mb(self) -> float:
        return self._peak_rss_mb

    @property
    def warnings(self) -> list[dict[str, Any]]:
        return list(self._warnings)

    def reset(self) -> None:
        """Reset counters and warnings."""
        self._check_count = 0
        self._current_rss_mb = 0.0
        self._peak_rss_mb = 0.0
        self._warnings.clear()

    def summary(self) -> dict[str, Any]:
        return {
            "checks_performed": self._check_count,
            "current_rss_mb": self._current_rss_mb,
            "peak_rss_mb": self._peak_rss_mb,
            "soft_limit_mb": self.soft_limit_mb,
            "hard_limit_mb": self.hard_limit_mb,
            "warning_count": len(self._warnings),
        }


# ═══════════════════════════════════════════════════════════════════════════
# Cycles 116-120 — Memory profiling utilities
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AllocationSnapshot:
    """Point-in-time snapshot of Python allocator state."""

    timestamp: float = field(default_factory=time.time)
    total_objects: int = 0
    gc_gen0: int = 0
    gc_gen1: int = 0
    gc_gen2: int = 0
    rss_mb: float = 0.0
    top_types: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_objects": self.total_objects,
            "gc_gen0": self.gc_gen0,
            "gc_gen1": self.gc_gen1,
            "gc_gen2": self.gc_gen2,
            "rss_mb": self.rss_mb,
            "top_types": [{"type": t, "count": c} for t, c in self.top_types],
        }


class MemoryProfiler:
    """Periodic memory profiling for scan diagnostics.

    Captures ``AllocationSnapshot`` at regular intervals and identifies
    growth trends.  Designed to run as a background thread during long
    scans.

    Usage::

        profiler = MemoryProfiler(interval_s=10, max_snapshots=100)
        profiler.start()
        # ... scan runs ...
        profiler.stop()
        print(profiler.report())
    """

    def __init__(
        self,
        interval_s: float = 10.0,
        max_snapshots: int = 100,
    ) -> None:
        self.interval_s = interval_s
        self.max_snapshots = max_snapshots
        self._snapshots: list[AllocationSnapshot] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _take_snapshot(self) -> AllocationSnapshot:
        """Capture a memory snapshot (called in profiler thread)."""
        gc_counts = gc.get_count()
        type_counts: dict[str, int] = {}
        all_objects = gc.get_objects()
        total = len(all_objects)

        # Count by type — limit to first 50k objects for speed
        for obj in all_objects[:50000]:
            t = type(obj).__name__
            type_counts[t] = type_counts.get(t, 0) + 1

        top_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return AllocationSnapshot(
            total_objects=total,
            gc_gen0=gc_counts[0],
            gc_gen1=gc_counts[1],
            gc_gen2=gc_counts[2],
            rss_mb=CeleryMemoryGuard._get_rss_mb(),
            top_types=top_types,
        )

    def _run(self) -> None:
        """Background profiling loop."""
        while not self._stop_event.is_set():
            snap = self._take_snapshot()
            with self._lock:
                self._snapshots.append(snap)
                if len(self._snapshots) > self.max_snapshots:
                    self._snapshots.pop(0)
            self._stop_event.wait(self.interval_s)

    def start(self) -> None:
        """Start the profiling thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="sf-memory-profiler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the profiling thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def snapshot_now(self) -> AllocationSnapshot:
        """Take an immediate snapshot (from the calling thread)."""
        snap = self._take_snapshot()
        with self._lock:
            self._snapshots.append(snap)
            if len(self._snapshots) > self.max_snapshots:
                self._snapshots.pop(0)
        return snap

    @property
    def snapshots(self) -> list[AllocationSnapshot]:
        with self._lock:
            return list(self._snapshots)

    def growth_rate(self) -> float:
        """Estimate object growth rate (objects/second).

        Returns 0.0 if fewer than 2 snapshots.
        """
        with self._lock:
            snaps = list(self._snapshots)
        if len(snaps) < 2:
            return 0.0
        first, last = snaps[0], snaps[-1]
        dt = last.timestamp - first.timestamp
        if dt <= 0:
            return 0.0
        return (last.total_objects - first.total_objects) / dt

    def rss_growth_rate(self) -> float:
        """Estimate RSS growth rate (MB/second)."""
        with self._lock:
            snaps = list(self._snapshots)
        if len(snaps) < 2:
            return 0.0
        first, last = snaps[0], snaps[-1]
        dt = last.timestamp - first.timestamp
        if dt <= 0:
            return 0.0
        return (last.rss_mb - first.rss_mb) / dt

    def report(self) -> dict[str, Any]:
        """Generate a profiling report."""
        with self._lock:
            snaps = list(self._snapshots)
        if not snaps:
            return {"error": "No snapshots collected"}

        latest = snaps[-1]
        return {
            "snapshots_collected": len(snaps),
            "duration_s": round(snaps[-1].timestamp - snaps[0].timestamp, 2) if len(snaps) > 1 else 0,
            "latest": latest.to_dict(),
            "object_growth_rate": round(self.growth_rate(), 2),
            "rss_growth_rate_mb_s": round(self.rss_growth_rate(), 4),
            "peak_rss_mb": max(s.rss_mb for s in snaps),
            "peak_objects": max(s.total_objects for s in snaps),
        }


class AllocationTracker:
    """Track memory allocations by label.

    Provides a ``@track`` context manager and decorator for measuring
    memory delta of specific code blocks.

    Usage::

        tracker = AllocationTracker()

        with tracker.track("db_query"):
            results = db.fetch_all()

        print(tracker.report())
    """

    def __init__(self) -> None:
        self._records: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()

    class _TrackContext:
        """Context manager for tracking a labeled allocation."""

        def __init__(self, tracker: AllocationTracker, label: str) -> None:
            self._tracker = tracker
            self._label = label
            self._start_objects = 0
            self._start_rss = 0.0
            self._start_time = 0.0

        def __enter__(self) -> AllocationTracker._TrackContext:
            gc.collect()
            self._start_objects = len(gc.get_objects())
            self._start_rss = CeleryMemoryGuard._get_rss_mb()
            self._start_time = time.time()
            return self

        def __exit__(self, exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
            gc.collect()
            end_objects = len(gc.get_objects())
            end_rss = CeleryMemoryGuard._get_rss_mb()
            end_time = time.time()

            record = {
                "objects_delta": end_objects - self._start_objects,
                "rss_delta_mb": round(end_rss - self._start_rss, 4),
                "duration_s": round(end_time - self._start_time, 4),
                "timestamp": end_time,
            }

            with self._tracker._lock:
                if self._label not in self._tracker._records:
                    self._tracker._records[self._label] = []
                self._tracker._records[self._label].append(record)

    def track(self, label: str) -> _TrackContext:
        """Return a context manager that tracks memory for ``label``."""
        return self._TrackContext(self, label)

    def report(self) -> dict[str, Any]:
        """Aggregate stats per label."""
        with self._lock:
            result = {}
            for label, records in self._records.items():
                obj_deltas = [r["objects_delta"] for r in records]
                rss_deltas = [r["rss_delta_mb"] for r in records]
                result[label] = {
                    "call_count": len(records),
                    "avg_objects_delta": sum(obj_deltas) / len(obj_deltas) if obj_deltas else 0,
                    "max_objects_delta": max(obj_deltas) if obj_deltas else 0,
                    "avg_rss_delta_mb": sum(rss_deltas) / len(rss_deltas) if rss_deltas else 0,
                    "max_rss_delta_mb": max(rss_deltas) if rss_deltas else 0,
                }
            return result

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


# ═══════════════════════════════════════════════════════════════════════════
# Cycles 121-125 — Object size analysis and GC tuning
# ═══════════════════════════════════════════════════════════════════════════

class ObjectSizeAnalyzer:
    """Analyze deep object sizes using ``sys.getsizeof`` tree walk.

    Used to identify unexpectedly large objects in the scan pipeline.
    """

    def __init__(self, max_depth: int = 5) -> None:
        self.max_depth = max_depth

    def deep_sizeof(self, obj: Any) -> int:
        """Recursively compute the deep size of an object.

        Follows references up to ``max_depth`` levels. Avoids infinite
        loops via an ``id()`` visited set.
        """
        seen: set[int] = set()
        return self._deep_sizeof_inner(obj, seen, 0)

    def _deep_sizeof_inner(self, obj: Any, seen: set[int], depth: int) -> int:
        obj_id = id(obj)
        if obj_id in seen or depth > self.max_depth:
            return 0
        seen.add(obj_id)

        size = sys.getsizeof(obj, 0)

        if isinstance(obj, dict):
            for k, v in obj.items():
                size += self._deep_sizeof_inner(k, seen, depth + 1)
                size += self._deep_sizeof_inner(v, seen, depth + 1)
        elif isinstance(obj, (list, tuple, set, frozenset)):
            for item in obj:
                size += self._deep_sizeof_inner(item, seen, depth + 1)
        elif hasattr(obj, "__dict__"):
            size += self._deep_sizeof_inner(obj.__dict__, seen, depth + 1)
        elif hasattr(obj, "__slots__"):
            for slot in obj.__slots__:
                try:
                    val = getattr(obj, slot, None)
                    if val is not None:
                        size += self._deep_sizeof_inner(val, seen, depth + 1)
                except AttributeError:
                    pass

        return size

    def top_objects(self, n: int = 10) -> list[dict[str, Any]]:
        """Find the top-N largest objects tracked by GC.

        Warning: This is expensive — only call during diagnostics.
        """
        gc.collect()
        sizes = []
        for obj in gc.get_objects()[:20000]:  # Limit for speed
            try:
                shallow = sys.getsizeof(obj, 0)
                sizes.append({
                    "type": type(obj).__name__,
                    "shallow_bytes": shallow,
                    "id": id(obj),
                    "repr": repr(obj)[:100],
                })
            except (TypeError, ReferenceError):
                continue

        sizes.sort(key=lambda x: x["shallow_bytes"], reverse=True)
        return sizes[:n]

    def type_summary(self) -> dict[str, dict[str, int]]:
        """Aggregate object counts and sizes by type."""
        gc.collect()
        summary: dict[str, dict[str, int]] = {}
        for obj in gc.get_objects()[:50000]:
            t = type(obj).__name__
            try:
                s = sys.getsizeof(obj, 0)
            except (TypeError, ReferenceError):
                s = 0
            if t not in summary:
                summary[t] = {"count": 0, "total_bytes": 0}
            summary[t]["count"] += 1
            summary[t]["total_bytes"] += s

        return dict(
            sorted(summary.items(), key=lambda x: x[1]["total_bytes"], reverse=True)[:20]
        )


class GCTuner:
    """Garbage collection tuner for long-running scan processes.

    Python's default GC thresholds (700, 10, 10) can cause excessive
    GC pauses in data-intensive scans.  ``GCTuner`` allows:

    - Raising gen-0 threshold to reduce minor collection frequency.
    - Disabling GC during bulk operations and re-enabling after.
    - Manual collection between scan phases.
    """

    def __init__(self) -> None:
        self._original_thresholds = gc.get_threshold()
        self._original_enabled = gc.isenabled()
        self._collection_times: list[float] = []
        self._lock = threading.Lock()

    @property
    def original_thresholds(self) -> tuple[int, int, int]:
        return self._original_thresholds

    def set_scan_thresholds(
        self,
        gen0: int = 5000,
        gen1: int = 50,
        gen2: int = 100,
    ) -> None:
        """Set GC thresholds optimized for scan workloads.

        Higher gen-0 threshold means fewer minor collections, which
        reduces pause frequency at the cost of slightly higher memory.
        """
        gc.set_threshold(gen0, gen1, gen2)
        log.info("GCTuner: thresholds set to (%d, %d, %d)", gen0, gen1, gen2)

    def restore_thresholds(self) -> None:
        """Restore original GC thresholds."""
        gc.set_threshold(*self._original_thresholds)
        if self._original_enabled:
            gc.enable()
        else:
            gc.disable()

    def collect_now(self, generation: int = 2) -> int:
        """Force immediate garbage collection.

        Returns number of unreachable objects found.
        """
        start = time.monotonic()
        collected = gc.collect(generation)
        elapsed = time.monotonic() - start
        with self._lock:
            self._collection_times.append(elapsed)
        log.debug("GCTuner: collected %d objects in %.3fs (gen %d)", collected, elapsed, generation)
        return collected

    class _BulkContext:
        """Context manager that disables GC during bulk operations."""

        def __init__(self, tuner: GCTuner) -> None:
            self._tuner = tuner
            self._was_enabled = gc.isenabled()

        def __enter__(self) -> GCTuner._BulkContext:
            gc.disable()
            return self

        def __exit__(self, exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
            if self._was_enabled:
                gc.enable()
            self._tuner.collect_now(2)

    def bulk_operation(self) -> _BulkContext:
        """Return a context manager that disables GC for bulk work."""
        return self._BulkContext(self)

    def collection_stats(self) -> dict[str, Any]:
        with self._lock:
            times = list(self._collection_times)
        if not times:
            return {"collections": 0}
        return {
            "collections": len(times),
            "total_time_s": round(sum(times), 4),
            "avg_time_s": round(sum(times) / len(times), 6),
            "max_time_s": round(max(times), 6),
            "current_thresholds": gc.get_threshold(),
        }


# ═══════════════════════════════════════════════════════════════════════════
# Cycles 126-130 — Weak references and event caching
# ═══════════════════════════════════════════════════════════════════════════

class WeakEventCache:
    """Cache of recently-produced events using weak references.

    During a scan, modules may want to check if a specific event was
    already produced without querying the database.  A regular dict
    cache would prevent GC of event objects, leading to unbounded
    memory growth.

    ``WeakEventCache`` stores ``weakref.ref`` so events are automatically
    evicted when no strong references remain.  For events stored as
    plain strings (which don't support weakref), it uses a bounded
    ``OrderedDict`` as a fallback LRU.
    """

    def __init__(self, maxsize: int = 10000) -> None:
        self._weak_refs: dict[str, weakref.ref] = {}
        self._string_cache: OrderedDict[str, str] = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, event_type: str, data: str, scan_id: str = "") -> str:
        """Build a cache key from event attributes."""
        return f"{scan_id}:{event_type}:{data}"

    def put(self, key: str, value: Any) -> None:
        """Store an event in the cache."""
        with self._lock:
            # Try weakref first
            try:
                self._weak_refs[key] = weakref.ref(
                    value, lambda ref, k=key: self._cleanup_ref(k)
                )
                return
            except TypeError:
                # Type doesn't support weakref (str, int, etc.)
                pass

            # Fallback to bounded LRU
            self._string_cache[key] = value
            self._string_cache.move_to_end(key)
            while len(self._string_cache) > self._maxsize:
                self._string_cache.popitem(last=False)

    def get(self, key: str) -> Any | None:
        """Retrieve an event from the cache, or ``None``."""
        with self._lock:
            # Check weakref first
            ref = self._weak_refs.get(key)
            if ref is not None:
                obj = ref()
                if obj is not None:
                    self._hits += 1
                    return obj
                else:
                    del self._weak_refs[key]

            # Check string cache
            val = self._string_cache.get(key)
            if val is not None:
                self._string_cache.move_to_end(key)
                self._hits += 1
                return val

            self._misses += 1
            return None

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def _cleanup_ref(self, key: str) -> None:
        """Callback when a weakref is garbage collected."""
        with self._lock:
            self._weak_refs.pop(key, None)

    def size(self) -> int:
        with self._lock:
            return len(self._weak_refs) + len(self._string_cache)

    def clear(self) -> None:
        with self._lock:
            self._weak_refs.clear()
            self._string_cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "weak_refs": len(self._weak_refs),
                "string_cache": len(self._string_cache),
                "maxsize": self._maxsize,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": (
                    self._hits / (self._hits + self._misses) * 100
                    if (self._hits + self._misses) > 0
                    else 0.0
                ),
            }


class EventHistoryPruner:
    """Prune accumulated event history from plugin instances.

    ``SpiderFootPlugin`` instances accumulate references to events they've
    processed.  For large scans, this can retain millions of event objects
    in memory.  This pruner periodically clears history older than a
    configurable window, keeping only recent events for deduplication.
    """

    def __init__(
        self,
        max_history_per_module: int = 1000,
        prune_interval_s: float = 30.0,
    ) -> None:
        self.max_history_per_module = max_history_per_module
        self.prune_interval_s = prune_interval_s
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._plugins: list[weakref.ref] = []
        self._lock = threading.Lock()
        self._total_pruned = 0

    def register_plugin(self, plugin: Any) -> None:
        """Register a plugin instance for periodic pruning."""
        with self._lock:
            self._plugins.append(weakref.ref(plugin))

    def _prune_once(self) -> int:
        """Prune all registered plugins.  Returns count of pruned items."""
        pruned = 0
        with self._lock:
            live_refs = []
            for ref in self._plugins:
                plugin = ref()
                if plugin is None:
                    continue
                live_refs.append(ref)

                # Prune _listeners if it's a list
                listeners = getattr(plugin, "_listenerModules", None)
                if isinstance(listeners, list) and len(listeners) > self.max_history_per_module:
                    excess = len(listeners) - self.max_history_per_module
                    del listeners[:excess]
                    pruned += excess

                # Prune any event history list
                history = getattr(plugin, "_eventHistory", None)
                if isinstance(history, list) and len(history) > self.max_history_per_module:
                    excess = len(history) - self.max_history_per_module
                    del history[:excess]
                    pruned += excess

            self._plugins = live_refs
        self._total_pruned += pruned
        return pruned

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(self.prune_interval_s)
            if not self._stop_event.is_set():
                count = self._prune_once()
                if count > 0:
                    log.debug("EventHistoryPruner: pruned %d items", count)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="sf-event-pruner",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    @property
    def total_pruned(self) -> int:
        return self._total_pruned

    def stats(self) -> dict[str, Any]:
        with self._lock:
            live = sum(1 for r in self._plugins if r() is not None)
        return {
            "registered_plugins": live,
            "total_pruned": self._total_pruned,
            "max_history_per_module": self.max_history_per_module,
            "prune_interval_s": self.prune_interval_s,
        }
