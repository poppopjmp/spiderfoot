# -*- coding: utf-8 -*-
"""
Structured audit event log for security-critical actions.

Complements the request-level audit middleware with explicit event
logging for actions that require compliance tracking such as:
  - API key creation/revocation
  - Role changes
  - Scan scheduling changes
  - Configuration modifications
  - Login/authentication events

Events are stored in Redis (recent buffer) and emitted via the
standard logger for persistence in Loki/Elasticsearch.

Usage::

    from spiderfoot.audit_log import audit_event

    audit_event(
        action="api_key.created",
        actor="admin",
        resource="sfk_abc123efgh",
        details={"role": "analyst", "name": "CI scanner"},
    )
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("spiderfoot.audit")

# Max events kept in Redis ring buffer
MAX_REDIS_EVENTS = int(os.environ.get("SF_AUDIT_MAX_EVENTS", "10000"))


# ---------------------------------------------------------------------------
# Event model
# ---------------------------------------------------------------------------

@dataclass
class AuditEvent:
    """A single audit log event."""
    event_id: str = ""
    timestamp: float = 0.0
    action: str = ""           # e.g. "api_key.created", "scan.started"
    actor: str = ""            # User or service identity
    actor_ip: str = ""         # Client IP
    resource: str = ""         # Affected resource ID
    resource_type: str = ""    # e.g. "api_key", "scan", "schedule"
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"     # info, warning, critical
    request_id: str = ""       # Correlation with request tracing

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "actor": self.actor,
            "actor_ip": self.actor_ip,
            "resource": self.resource,
            "resource_type": self.resource_type,
            "details": self.details,
            "severity": self.severity,
            "request_id": self.request_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEvent:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Action constants
# ---------------------------------------------------------------------------

class Actions:
    """Standard audit action constants."""
    # Auth
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"

    # API Keys
    KEY_CREATED = "api_key.created"
    KEY_UPDATED = "api_key.updated"
    KEY_REVOKED = "api_key.revoked"
    KEY_DELETED = "api_key.deleted"

    # RBAC
    ROLE_CHANGED = "rbac.role_changed"
    PERMISSION_DENIED = "rbac.permission_denied"

    # Scans
    SCAN_STARTED = "scan.started"
    SCAN_COMPLETED = "scan.completed"
    SCAN_FAILED = "scan.failed"
    SCAN_ABORTED = "scan.aborted"
    SCAN_DELETED = "scan.deleted"

    # Schedules
    SCHEDULE_CREATED = "schedule.created"
    SCHEDULE_UPDATED = "schedule.updated"
    SCHEDULE_DELETED = "schedule.deleted"
    SCHEDULE_TRIGGERED = "schedule.triggered"

    # Config
    CONFIG_CHANGED = "config.changed"

    # Rate limits
    RATELIMIT_CHANGED = "ratelimit.changed"

    # Engine
    ENGINE_CREATED = "engine.created"
    ENGINE_UPDATED = "engine.updated"
    ENGINE_DELETED = "engine.deleted"

    # Reports
    REPORT_GENERATED = "report.generated"
    DATA_EXPORTED = "data.exported"

    # System
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"


# ---------------------------------------------------------------------------
# Redis-backed storage
# ---------------------------------------------------------------------------

def _get_redis():
    """Get Redis connection."""
    import redis as redis_lib
    redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
    return redis_lib.from_url(redis_url)


def _audit_list_key() -> str:
    return "sf:audit:events"


def _store_event(event: AuditEvent) -> None:
    """Store an event in Redis ring buffer."""
    try:
        r = _get_redis()
        r.lpush(_audit_list_key(), json.dumps(event.to_dict()))
        r.ltrim(_audit_list_key(), 0, MAX_REDIS_EVENTS - 1)
    except Exception as e:
        log.debug("Failed to store audit event in Redis: %s", e)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def audit_event(
    action: str,
    actor: str = "",
    actor_ip: str = "",
    resource: str = "",
    resource_type: str = "",
    details: dict[str, Any] | None = None,
    severity: str = "info",
    request_id: str = "",
) -> AuditEvent:
    """Record an audit event.

    The event is:
      1. Emitted via the ``spiderfoot.audit`` logger (for Loki/ELK)
      2. Stored in Redis ring buffer (for API queries)

    Args:
        action: Action constant (see ``Actions``).
        actor: User/service performing the action.
        resource: Affected resource ID.
        resource_type: Resource type (e.g. "api_key").
        details: Additional context.
        severity: info / warning / critical.
        request_id: Correlation ID from request tracing.

    Returns:
        The created AuditEvent.
    """
    event = AuditEvent(
        event_id=str(uuid.uuid4()),
        timestamp=time.time(),
        action=action,
        actor=actor,
        actor_ip=actor_ip,
        resource=resource,
        resource_type=resource_type,
        details=details or {},
        severity=severity,
        request_id=request_id,
    )

    # Emit via logger
    log_fn = log.info
    if severity == "warning":
        log_fn = log.warning
    elif severity == "critical":
        log_fn = log.critical

    log_fn(
        "AUDIT: %s by %s on %s:%s",
        action, actor or "system", resource_type, resource,
        extra={"audit": event.to_dict()},
    )

    # Store in Redis
    _store_event(event)

    return event


def query_audit_events(
    action: str | None = None,
    actor: str | None = None,
    resource_type: str | None = None,
    severity: str | None = None,
    since: float = 0,
    limit: int = 100,
) -> list[AuditEvent]:
    """Query recent audit events from Redis.

    Args:
        action: Filter by action prefix (e.g. "api_key").
        actor: Filter by actor.
        resource_type: Filter by resource type.
        severity: Filter by severity.
        since: Unix timestamp — only events after this.
        limit: Max results.

    Returns:
        List of matching AuditEvents (newest first).
    """
    try:
        r = _get_redis()
        # Read more than limit to account for filtering
        raw_events = r.lrange(_audit_list_key(), 0, min(limit * 3, MAX_REDIS_EVENTS))
    except Exception:
        return []

    results = []
    for raw in raw_events:
        try:
            data = json.loads(raw)
            if since and data.get("timestamp", 0) < since:
                continue
            if action and not data.get("action", "").startswith(action):
                continue
            if actor and data.get("actor") != actor:
                continue
            if resource_type and data.get("resource_type") != resource_type:
                continue
            if severity and data.get("severity") != severity:
                continue
            results.append(AuditEvent.from_dict(data))
            if len(results) >= limit:
                break
        except (json.JSONDecodeError, TypeError):
            continue

    return results
