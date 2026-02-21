"""SpiderFoot observability subpackage.

This subpackage contains metrics, logging, health checks, and auditing
components for monitoring and debugging.

Usage::

    from spiderfoot.observability import Counter, Gauge, MetricsRegistry
    from spiderfoot.observability import HealthAggregator, AuditLogger
"""

from __future__ import annotations

# Audit logging
from .audit_log import (
    AuditBackend,
    AuditCategory,
    AuditEvent,
    AuditLogger,
    AuditSeverity,
    FileAuditBackend,
    MemoryAuditBackend,
    get_audit_logger,
)

# Health checks
from .health import (
    check_cache,
    check_database,
    check_event_bus,
    ComponentHealth,
    HealthAggregator,
    HealthStatus,
    register_default_checks,
)

# Logger
from .logger import (
    logListenerSetup,
    logWorkerSetup,
    SpiderFootDbLogHandler,
    stop_listener,
)

# Metrics
from .metrics import (
    Counter,
    Gauge,
    get_registry,
    Histogram,
    MetricsRegistry,
)

# Structured logging
from .structured_logging import (
    EventLogEmitter,
    setup_structured_logging,
    StructuredFormatter,
    StructuredLogHandler,
)

__all__ = [
    # Audit logging
    "AuditBackend",
    "AuditCategory",
    "AuditEvent",
    "AuditLogger",
    "AuditSeverity",
    "FileAuditBackend",
    "MemoryAuditBackend",
    "get_audit_logger",
    # Health checks
    "check_cache",
    "check_database",
    "check_event_bus",
    "ComponentHealth",
    "HealthAggregator",
    "HealthStatus",
    "register_default_checks",
    # Logger
    "logListenerSetup",
    "logWorkerSetup",
    "SpiderFootDbLogHandler",
    "stop_listener",
    # Metrics
    "Counter",
    "Gauge",
    "get_registry",
    "Histogram",
    "MetricsRegistry",
    # Structured logging
    "EventLogEmitter",
    "setup_structured_logging",
    "StructuredFormatter",
    "StructuredLogHandler",
]

