"""Error telemetry — centralised error capture, fingerprinting, and rate tracking.

Bridges the gap between per-module ``self.error()`` calls and system-wide
observability.  Features:

* **Error capture** with full context (exception type, traceback, module,
  scan, event type, source location).
* **Fingerprinting** — deterministic hash of (exception_type, module,
  source_file, line) so duplicate errors are grouped automatically.
* **Error classification** — ``TRANSIENT_NETWORK``, ``AUTH_FAILURE``,
  ``DATA_PARSE``, ``RESOURCE_EXHAUSTION``, ``RATE_LIMITED``, ``INTERNAL``.
* **Sliding-window error rate** — per-module and global errors-per-minute.
* **Ring buffer** of recent errors queryable by module, scan, or class.
* **Alert hooks** — callbacks fired when configurable thresholds are breached.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
import traceback as tb_module
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("spiderfoot.error_telemetry")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ErrorClass(Enum):
    """Coarse classification of an error."""

    TRANSIENT_NETWORK = "transient_network"
    AUTH_FAILURE = "auth_failure"
    DATA_PARSE = "data_parse"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    WARNING = "warning"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ErrorRecord:
    """A single captured error occurrence."""

    fingerprint: str
    exception_type: str
    message: str
    module_name: str = ""
    scan_id: str = ""
    event_type: str = ""
    target: str = ""
    error_class: ErrorClass = ErrorClass.UNKNOWN
    traceback: str = ""
    source_file: str = ""
    source_line: int = 0
    timestamp: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "exception_type": self.exception_type,
            "message": self.message,
            "module_name": self.module_name,
            "scan_id": self.scan_id,
            "event_type": self.event_type,
            "target": self.target,
            "error_class": self.error_class.value,
            "traceback": self.traceback,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "timestamp": self.timestamp,
            "extra": self.extra,
        }


@dataclass
class ErrorGroup:
    """Aggregated stats for errors sharing the same fingerprint."""

    fingerprint: str
    exception_type: str
    module_name: str
    source_file: str
    source_line: int
    error_class: ErrorClass = ErrorClass.UNKNOWN
    first_seen: float = 0.0
    last_seen: float = 0.0
    count: int = 0
    last_message: str = ""
    affected_scans: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "exception_type": self.exception_type,
            "module_name": self.module_name,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "error_class": self.error_class.value,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "count": self.count,
            "last_message": self.last_message,
            "affected_scans": list(self.affected_scans),
        }


@dataclass
class AlertRule:
    """Threshold that triggers an alert callback."""

    name: str
    severity: AlertSeverity
    threshold: float  # errors per minute
    window_seconds: float = 60.0
    module_filter: str = ""  # empty = global
    callback: Callable[[AlertEvent], None] | None = None


@dataclass
class AlertEvent:
    """Payload delivered to alert callbacks."""

    rule_name: str
    severity: AlertSeverity
    current_rate: float
    threshold: float
    module_name: str
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Error classifier
# ---------------------------------------------------------------------------

# Keywords matched against str(exception) and exception class name.
_CLASSIFICATION_RULES: list[tuple] = [
    (ErrorClass.TIMEOUT, {"timeout", "timed out", "TimeoutError", "ReadTimeout"}),
    (ErrorClass.RATE_LIMITED, {"429", "rate limit", "too many requests", "RateLimitError"}),
    (ErrorClass.AUTH_FAILURE, {"401", "403", "unauthorized", "forbidden", "AuthError", "authentication"}),
    (ErrorClass.TRANSIENT_NETWORK, {
        "ConnectionError", "ConnectionRefused", "ConnectionReset",
        "BrokenPipeError", "socket", "ECONNREFUSED", "ECONNRESET",
        "DNS", "resolve", "getaddrinfo", "NetworkError",
    }),
    (ErrorClass.RESOURCE_EXHAUSTION, {
        "MemoryError", "OSError", "disk", "quota", "ENOMEM",
        "ResourceExhausted", "no space",
    }),
    (ErrorClass.DATA_PARSE, {
        "JSONDecodeError", "ValueError", "KeyError", "IndexError",
        "UnicodeDecodeError", "ParseError", "XMLSyntaxError",
        "json.decoder", "decode", "parse",
    }),
]


def classify_error(exc_type: str, message: str) -> ErrorClass:
    """Return the best-matching :class:`ErrorClass` for an error."""
    combined = f"{exc_type} {message}".lower()
    for cls, keywords in _CLASSIFICATION_RULES:
        for kw in keywords:
            if kw.lower() in combined:
                return cls
    return ErrorClass.INTERNAL if exc_type else ErrorClass.UNKNOWN


def compute_fingerprint(
    exc_type: str,
    module_name: str,
    source_file: str,
    source_line: int,
) -> str:
    """Deterministic fingerprint for grouping identical errors."""
    raw = f"{exc_type}|{module_name}|{source_file}|{source_line}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Sliding window rate tracker
# ---------------------------------------------------------------------------

class _SlidingWindow:
    """Fixed-window error counter for rate computation."""

    def __init__(self, window_seconds: float = 60.0):
        self._window = window_seconds
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def record(self, ts: float | None = None) -> None:
        ts = ts or time.time()
        with self._lock:
            self._timestamps.append(ts)

    def rate(self, now: float | None = None) -> float:
        """Return events per minute within the window."""
        now = now or time.time()
        cutoff = now - self._window
        with self._lock:
            self._timestamps = [t for t in self._timestamps if t >= cutoff]
            count = len(self._timestamps)
        if self._window <= 0:
            return 0.0
        return count * (60.0 / self._window)

    def count(self, now: float | None = None) -> int:
        now = now or time.time()
        cutoff = now - self._window
        with self._lock:
            self._timestamps = [t for t in self._timestamps if t >= cutoff]
            return len(self._timestamps)


# ---------------------------------------------------------------------------
# ErrorTelemetry service
# ---------------------------------------------------------------------------

class ErrorTelemetry:
    """Centralised error capture and analysis.

    Usage::

        telemetry = ErrorTelemetry()
        telemetry.capture(exception, module_name="sfp_shodan", scan_id="abc")
        print(telemetry.error_rate())
        for grp in telemetry.top_errors(5):
            print(grp.fingerprint, grp.count)
    """

    def __init__(
        self,
        *,
        ring_size: int = 1000,
        window_seconds: float = 60.0,
    ):
        self._ring_size = ring_size
        self._window_seconds = window_seconds

        self._records: list[ErrorRecord] = []  # ring buffer
        self._groups: dict[str, ErrorGroup] = {}  # fingerprint → group
        self._global_rate = _SlidingWindow(window_seconds)
        self._module_rates: dict[str, _SlidingWindow] = {}
        self._alerts: list[AlertRule] = []
        self._alert_history: list[AlertEvent] = []
        self._lock = threading.Lock()

    # -------------------------------------------------------------------
    # Capture
    # -------------------------------------------------------------------

    def capture(
        self,
        exc: BaseException | None = None,
        *,
        message: str = "",
        module_name: str = "",
        scan_id: str = "",
        event_type: str = "",
        target: str = "",
        error_class: ErrorClass | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ErrorRecord:
        """Record an error occurrence.

        Args:
            exc: The exception object (optional — can capture string-only
                 errors too).
            message: Human-readable message.  Defaults to ``str(exc)``.
            module_name: Name of the module that raised the error.
            scan_id: Active scan identifier.
            event_type: The event type being processed when error occurred.
            target: Scan target.
            error_class: Explicit classification; auto-detected if omitted.
            extra: Arbitrary key-value metadata.

        Returns:
            The captured :class:`ErrorRecord`.
        """
        exc_type = type(exc).__name__ if exc else ""
        if not message and exc:
            message = str(exc)

        tback = ""
        source_file = ""
        source_line = 0
        if exc and exc.__traceback__:
            tback = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__))
            tb_obj = exc.__traceback__
            while tb_obj.tb_next:
                tb_obj = tb_obj.tb_next
            source_file = tb_obj.tb_frame.f_code.co_filename
            source_line = tb_obj.tb_lineno

        if error_class is None:
            error_class = classify_error(exc_type, message)

        fp = compute_fingerprint(exc_type, module_name, source_file, source_line)
        now = time.time()

        record = ErrorRecord(
            fingerprint=fp,
            exception_type=exc_type,
            message=message,
            module_name=module_name,
            scan_id=scan_id,
            event_type=event_type,
            target=target,
            error_class=error_class,
            traceback=tback,
            source_file=source_file,
            source_line=source_line,
            timestamp=now,
            extra=extra or {},
        )

        with self._lock:
            # Ring buffer
            self._records.append(record)
            if len(self._records) > self._ring_size:
                self._records = self._records[-self._ring_size:]

            # Update group
            grp = self._groups.get(fp)
            if grp is None:
                grp = ErrorGroup(
                    fingerprint=fp,
                    exception_type=exc_type,
                    module_name=module_name,
                    source_file=source_file,
                    source_line=source_line,
                    error_class=error_class,
                    first_seen=now,
                )
                self._groups[fp] = grp
            grp.last_seen = now
            grp.count += 1
            grp.last_message = message
            if scan_id:
                grp.affected_scans.add(scan_id)

            # Rate tracking
            self._global_rate.record(now)
            if module_name:
                if module_name not in self._module_rates:
                    self._module_rates[module_name] = _SlidingWindow(self._window_seconds)
                self._module_rates[module_name].record(now)

        # Check alerts (outside lock to avoid deadlock in callbacks)
        self._check_alerts(module_name, now)

        return record

    def capture_from_log(
        self,
        message: str,
        *,
        module_name: str = "",
        scan_id: str = "",
        event_type: str = "",
    ) -> ErrorRecord:
        """Capture an error from a log message (no exception object)."""
        return self.capture(
            message=message,
            module_name=module_name,
            scan_id=scan_id,
            event_type=event_type,
        )

    # -------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------

    def error_rate(self, module_name: str = "") -> float:
        """Errors per minute (global or per-module)."""
        if module_name:
            sw = self._module_rates.get(module_name)
            return sw.rate() if sw else 0.0
        return self._global_rate.rate()

    def error_count(self, module_name: str = "") -> int:
        """Error count in current window."""
        if module_name:
            sw = self._module_rates.get(module_name)
            return sw.count() if sw else 0
        return self._global_rate.count()

    def recent_errors(
        self,
        limit: int = 50,
        *,
        module_name: str = "",
        scan_id: str = "",
        error_class: ErrorClass | None = None,
    ) -> list[ErrorRecord]:
        """Return the most recent errors, optionally filtered."""
        with self._lock:
            records = list(self._records)
        if module_name:
            records = [r for r in records if r.module_name == module_name]
        if scan_id:
            records = [r for r in records if r.scan_id == scan_id]
        if error_class is not None:
            records = [r for r in records if r.error_class == error_class]
        return records[-limit:]

    def top_errors(self, limit: int = 10) -> list[ErrorGroup]:
        """Return error groups sorted by frequency (descending)."""
        with self._lock:
            groups = list(self._groups.values())
        groups.sort(key=lambda g: g.count, reverse=True)
        return groups[:limit]

    def get_group(self, fingerprint: str) -> ErrorGroup | None:
        with self._lock:
            return self._groups.get(fingerprint)

    def groups_for_module(self, module_name: str) -> list[ErrorGroup]:
        with self._lock:
            return [
                g for g in self._groups.values()
                if g.module_name == module_name
            ]

    def groups_for_scan(self, scan_id: str) -> list[ErrorGroup]:
        with self._lock:
            return [
                g for g in self._groups.values()
                if scan_id in g.affected_scans
            ]

    def affected_modules(self) -> dict[str, int]:
        """Return {module_name: error_count} for all modules with errors."""
        with self._lock:
            result: dict[str, int] = {}
            for g in self._groups.values():
                if g.module_name:
                    result[g.module_name] = result.get(g.module_name, 0) + g.count
            return result

    # -------------------------------------------------------------------
    # Alerts
    # -------------------------------------------------------------------

    def add_alert(self, rule: AlertRule) -> None:
        """Register an alert rule."""
        self._alerts.append(rule)

    def remove_alert(self, name: str) -> bool:
        before = len(self._alerts)
        self._alerts = [a for a in self._alerts if a.name != name]
        return len(self._alerts) < before

    def _check_alerts(self, module_name: str, now: float) -> None:
        for rule in self._alerts:
            # Module filter
            if rule.module_filter and rule.module_filter != module_name:
                continue

            rate = self.error_rate(rule.module_filter)
            if rate >= rule.threshold:
                evt = AlertEvent(
                    rule_name=rule.name,
                    severity=rule.severity,
                    current_rate=rate,
                    threshold=rule.threshold,
                    module_name=module_name,
                    timestamp=now,
                )
                self._alert_history.append(evt)
                if rule.callback:
                    try:
                        rule.callback(evt)
                    except Exception:
                        log.debug("Alert callback error", exc_info=True)

    def alert_history(self, limit: int = 50) -> list[AlertEvent]:
        return self._alert_history[-limit:]

    # -------------------------------------------------------------------
    # Management
    # -------------------------------------------------------------------

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._groups.clear()
            self._module_rates.clear()
            self._global_rate = _SlidingWindow(self._window_seconds)
            self._alert_history.clear()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_records": len(self._records),
                "total_groups": len(self._groups),
                "total_errors_all_time": sum(g.count for g in self._groups.values()),
                "global_rate_per_min": self._global_rate.rate(),
                "modules_affected": len(self._module_rates),
                "alert_rules": len(self._alerts),
                "alerts_fired": len(self._alert_history),
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ErrorTelemetry | None = None
_instance_lock = threading.Lock()


def get_error_telemetry(**kwargs: Any) -> ErrorTelemetry:
    """Return the global :class:`ErrorTelemetry` singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ErrorTelemetry(**kwargs)
    return _instance
