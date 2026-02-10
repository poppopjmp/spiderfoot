#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         audit_log
# Purpose:      Immutable audit logging for SpiderFoot.
#               Tracks administrative actions, authentication events,
#               configuration changes, and scan operations for
#               compliance and forensics.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
SpiderFoot Audit Log

Immutable audit trail for security-relevant actions::

    from spiderfoot.audit_log import AuditLogger, AuditEvent, AuditCategory

    audit = AuditLogger()

    audit.log(AuditEvent(
        category=AuditCategory.AUTH,
        action="login",
        actor="admin",
        detail="Successful login from 10.0.0.1",
    ))

    # Query audit log
    events = audit.query(category=AuditCategory.AUTH, limit=50)
"""

import hashlib
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List

log = logging.getLogger("spiderfoot.audit_log")


class AuditCategory(str, Enum):
    """Categories of auditable events."""
    AUTH = "auth"
    CONFIG = "config"
    SCAN = "scan"
    DATA = "data"
    MODULE = "module"
    ADMIN = "admin"
    API = "api"
    EXPORT = "export"
    SYSTEM = "system"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """An auditable event."""
    category: AuditCategory
    action: str
    actor: str = "system"
    detail: str = ""
    severity: AuditSeverity = AuditSeverity.INFO
    resource: str = ""
    resource_id: str = ""
    source_ip: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = ""

    def __post_init__(self):
        if not self.event_id:
            # Generate deterministic ID
            raw = f"{self.timestamp}:{self.category}:{self.action}:{self.actor}"
            self.event_id = hashlib.sha256(
                raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "category": self.category.value
            if isinstance(self.category, AuditCategory) else self.category,
            "action": self.action,
            "actor": self.actor,
            "severity": self.severity.value
            if isinstance(self.severity, AuditSeverity) else self.severity,
            "detail": self.detail,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "source_ip": self.source_ip,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditEvent":
        cat = data.get("category", "system")
        try:
            cat = AuditCategory(cat)
        except ValueError:
            cat = AuditCategory.SYSTEM

        sev = data.get("severity", "info")
        try:
            sev = AuditSeverity(sev)
        except ValueError:
            sev = AuditSeverity.INFO

        return cls(
            event_id=data.get("event_id", ""),
            timestamp=data.get("timestamp", time.time()),
            category=cat,
            action=data.get("action", ""),
            actor=data.get("actor", "system"),
            severity=sev,
            detail=data.get("detail", ""),
            resource=data.get("resource", ""),
            resource_id=data.get("resource_id", ""),
            source_ip=data.get("source_ip", ""),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Audit backends
# ---------------------------------------------------------------------------

class AuditBackend:
    """Base class for audit log storage."""

    def write(self, event: AuditEvent) -> bool:
        raise NotImplementedError

    def query(self, **filters) -> list[AuditEvent]:
        raise NotImplementedError

    def count(self, **filters) -> int:
        return len(self.query(**filters))


class MemoryAuditBackend(AuditBackend):
    """In-memory audit log with bounded buffer."""

    def __init__(self, max_events: int = 10000) -> None:
        self._events: deque = deque(maxlen=max_events)
        self._lock = threading.Lock()

    def write(self, event: AuditEvent) -> bool:
        with self._lock:
            self._events.append(event)
        return True

    def query(self, **filters) -> list[AuditEvent]:
        with self._lock:
            events = list(self._events)

        return self._apply_filters(events, **filters)

    def _apply_filters(self, events: list[AuditEvent],
                       **filters) -> list[AuditEvent]:
        category = filters.get("category")
        action = filters.get("action")
        actor = filters.get("actor")
        severity = filters.get("severity")
        since = filters.get("since")
        until = filters.get("until")
        limit = filters.get("limit", 100)

        result = []
        for event in reversed(events):  # Most recent first
            if category and event.category != category:
                continue
            if action and event.action != action:
                continue
            if actor and event.actor != actor:
                continue
            if severity and event.severity != severity:
                continue
            if since and event.timestamp < since:
                continue
            if until and event.timestamp > until:
                continue

            result.append(event)
            if len(result) >= limit:
                break

        return result


class FileAuditBackend(AuditBackend):
    """Append-only file audit log (JSON lines)."""

    def __init__(self, filepath: str = "audit.log") -> None:
        self._filepath = filepath
        self._lock = threading.Lock()

    def write(self, event: AuditEvent) -> bool:
        try:
            line = json.dumps(event.to_dict(), default=str) + "\n"
            with self._lock:
                with open(self._filepath, "a", encoding="utf-8") as f:
                    f.write(line)
            return True
        except Exception as e:
            log.error("Failed to write audit log: %s", e)
            return False

    def query(self, **filters) -> list[AuditEvent]:
        events = []
        try:
            if not os.path.exists(self._filepath):
                return events

            with open(self._filepath, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        events.append(AuditEvent.from_dict(data))
                    except (json.JSONDecodeError, Exception):
                        continue
        except Exception as e:
            log.error("Failed to read audit log: %s", e)

        # Apply filters
        backend = MemoryAuditBackend()
        return backend._apply_filters(events, **filters)


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------

class AuditLogger:
    """Central audit logging service.

    Supports multiple backends (memory, file) and optional
    callback hooks for real-time audit event processing.
    """

    def __init__(self, backends: list[AuditBackend] | None = None) -> None:
        """
        Args:
            backends: List of audit backends. Defaults to memory backend.
        """
        self._backends = backends or [MemoryAuditBackend()]
        self._hooks: list[Callable[[AuditEvent], None]] = []
        self._lock = threading.Lock()
        self._total_events = 0

    def add_backend(self, backend: AuditBackend) -> None:
        """Add an additional audit backend."""
        self._backends.append(backend)

    def add_hook(self, hook: Callable[[AuditEvent], None]) -> None:
        """Add a callback that is invoked for every audit event."""
        self._hooks.append(hook)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(self, event: AuditEvent) -> bool:
        """Log an audit event to all backends."""
        success = True
        for backend in self._backends:
            try:
                if not backend.write(event):
                    success = False
            except Exception as e:
                log.error("Audit backend error: %s", e)
                success = False

        # Invoke hooks
        for hook in self._hooks:
            try:
                hook(event)
            except Exception as e:
                log.debug("audit hook(event) callback failed: %s", e)

        with self._lock:
            self._total_events += 1

        return success

    # Convenience methods
    def log_auth(self, action: str, actor: str, *,
                 detail: str = "", source_ip: str = "",
                 severity: AuditSeverity = AuditSeverity.INFO,
                 **metadata) -> bool:
        """Log an authentication-related event."""
        return self.log(AuditEvent(
            category=AuditCategory.AUTH,
            action=action,
            actor=actor,
            detail=detail,
            source_ip=source_ip,
            severity=severity,
            metadata=metadata,
        ))

    def log_config(self, action: str, actor: str, *,
                   detail: str = "", resource: str = "",
                   **metadata) -> bool:
        """Log a configuration change."""
        return self.log(AuditEvent(
            category=AuditCategory.CONFIG,
            action=action,
            actor=actor,
            detail=detail,
            resource=resource,
            severity=AuditSeverity.WARNING,
            metadata=metadata,
        ))

    def log_scan(self, action: str, *, actor: str = "system",
                 detail: str = "", resource_id: str = "",
                 **metadata) -> bool:
        """Log a scan lifecycle event."""
        return self.log(AuditEvent(
            category=AuditCategory.SCAN,
            action=action,
            actor=actor,
            detail=detail,
            resource="scan",
            resource_id=resource_id,
            metadata=metadata,
        ))

    def log_api(self, action: str, actor: str, *,
                detail: str = "", source_ip: str = "",
                **metadata) -> bool:
        """Log an API access event."""
        return self.log(AuditEvent(
            category=AuditCategory.API,
            action=action,
            actor=actor,
            detail=detail,
            source_ip=source_ip,
            metadata=metadata,
        ))

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self, **filters) -> list[AuditEvent]:
        """Query audit events from the first backend."""
        if not self._backends:
            return []
        return self._backends[0].query(**filters)

    @property
    def stats(self) -> dict:
        return {
            "total_events": self._total_events,
            "backends": len(self._backends),
            "hooks": len(self._hooks),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_audit_instance: AuditLogger | None = None
_audit_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """Get the global AuditLogger singleton."""
    global _audit_instance
    if _audit_instance is None:
        with _audit_lock:
            if _audit_instance is None:
                _audit_instance = AuditLogger()
    return _audit_instance
