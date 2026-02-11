"""Backward-compatibility shim for audit_log.py.

This module re-exports from observability/audit_log.py for backward compatibility.
"""

from __future__ import annotations

from .observability.audit_log import (
    AuditCategory,
    AuditSeverity,
    AuditEvent,
    AuditBackend,
    MemoryAuditBackend,
    FileAuditBackend,
    AuditLogger,
    get_audit_logger,
)

__all__ = [
    "AuditCategory",
    "AuditSeverity",
    "AuditEvent",
    "AuditBackend",
    "MemoryAuditBackend",
    "FileAuditBackend",
    "AuditLogger",
    "get_audit_logger",
]
