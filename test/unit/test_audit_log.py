"""Tests for spiderfoot.audit_log."""
from __future__ import annotations

import json
import os
import tempfile
import time

import pytest

from spiderfoot.observability.audit_log import (
    AuditCategory,
    AuditEvent,
    AuditLogger,
    AuditSeverity,
    FileAuditBackend,
    MemoryAuditBackend,
    get_audit_logger,
)


class TestAuditEvent:
    def test_defaults(self):
        e = AuditEvent(category=AuditCategory.AUTH, action="login")
        assert e.actor == "system"
        assert e.severity == AuditSeverity.INFO
        assert e.event_id != ""
        assert e.timestamp > 0

    def test_to_dict(self):
        e = AuditEvent(
            category=AuditCategory.SCAN,
            action="start",
            actor="admin",
            detail="Started scan for example.com",
            resource_id="scan-123",
        )
        d = e.to_dict()
        assert d["category"] == "scan"
        assert d["action"] == "start"
        assert d["actor"] == "admin"
        assert d["resource_id"] == "scan-123"

    def test_from_dict(self):
        data = {
            "category": "auth",
            "action": "login",
            "actor": "user1",
            "severity": "warning",
            "detail": "Failed password",
            "source_ip": "10.0.0.1",
        }
        e = AuditEvent.from_dict(data)
        assert e.category == AuditCategory.AUTH
        assert e.severity == AuditSeverity.WARNING
        assert e.source_ip == "10.0.0.1"

    def test_from_dict_unknown_category(self):
        data = {"category": "unknown", "action": "test"}
        e = AuditEvent.from_dict(data)
        assert e.category == AuditCategory.SYSTEM

    def test_round_trip(self):
        original = AuditEvent(
            category=AuditCategory.CONFIG,
            action="update",
            actor="admin",
            metadata={"key": "value"},
        )
        restored = AuditEvent.from_dict(original.to_dict())
        assert restored.category == original.category
        assert restored.action == original.action
        assert restored.actor == original.actor

    def test_unique_event_ids(self):
        e1 = AuditEvent(category=AuditCategory.AUTH, action="login")
        time.sleep(0.01)
        e2 = AuditEvent(category=AuditCategory.AUTH, action="login")
        assert e1.event_id != e2.event_id


class TestMemoryAuditBackend:
    def test_write_and_query(self):
        backend = MemoryAuditBackend()
        e = AuditEvent(category=AuditCategory.AUTH, action="login",
                      actor="admin")
        assert backend.write(e) is True

        results = backend.query()
        assert len(results) == 1
        assert results[0].action == "login"

    def test_query_by_category(self):
        backend = MemoryAuditBackend()
        backend.write(AuditEvent(
            category=AuditCategory.AUTH, action="login"))
        backend.write(AuditEvent(
            category=AuditCategory.SCAN, action="start"))

        results = backend.query(category=AuditCategory.AUTH)
        assert len(results) == 1
        assert results[0].action == "login"

    def test_query_by_actor(self):
        backend = MemoryAuditBackend()
        backend.write(AuditEvent(
            category=AuditCategory.AUTH, action="login",
            actor="admin"))
        backend.write(AuditEvent(
            category=AuditCategory.AUTH, action="login",
            actor="user1"))

        results = backend.query(actor="admin")
        assert len(results) == 1

    def test_query_limit(self):
        backend = MemoryAuditBackend()
        for i in range(20):
            backend.write(AuditEvent(
                category=AuditCategory.AUTH,
                action=f"action_{i}"))

        results = backend.query(limit=5)
        assert len(results) == 5

    def test_query_most_recent_first(self):
        backend = MemoryAuditBackend()
        backend.write(AuditEvent(
            category=AuditCategory.AUTH, action="first",
            timestamp=100.0))
        backend.write(AuditEvent(
            category=AuditCategory.AUTH, action="second",
            timestamp=200.0))

        results = backend.query()
        assert results[0].action == "second"

    def test_bounded_buffer(self):
        backend = MemoryAuditBackend(max_events=5)
        for i in range(10):
            backend.write(AuditEvent(
                category=AuditCategory.AUTH,
                action=f"action_{i}"))

        results = backend.query(limit=100)
        assert len(results) == 5

    def test_count(self):
        backend = MemoryAuditBackend()
        for _ in range(3):
            backend.write(AuditEvent(
                category=AuditCategory.AUTH, action="login"))
        assert backend.count() == 3

    def test_query_by_severity(self):
        backend = MemoryAuditBackend()
        backend.write(AuditEvent(
            category=AuditCategory.AUTH, action="login",
            severity=AuditSeverity.INFO))
        backend.write(AuditEvent(
            category=AuditCategory.AUTH, action="failed",
            severity=AuditSeverity.ERROR))

        results = backend.query(severity=AuditSeverity.ERROR)
        assert len(results) == 1
        assert results[0].action == "failed"

    def test_query_time_range(self):
        backend = MemoryAuditBackend()
        backend.write(AuditEvent(
            category=AuditCategory.AUTH, action="old",
            timestamp=100.0))
        backend.write(AuditEvent(
            category=AuditCategory.AUTH, action="new",
            timestamp=200.0))

        results = backend.query(since=150.0)
        assert len(results) == 1
        assert results[0].action == "new"


class TestFileAuditBackend:
    def test_write_and_query(self, tmp_path):
        filepath = str(tmp_path / "audit.log")
        backend = FileAuditBackend(filepath=filepath)

        e = AuditEvent(
            category=AuditCategory.CONFIG,
            action="update",
            actor="admin",
            detail="Changed setting X",
        )
        assert backend.write(e) is True
        assert os.path.exists(filepath)

        results = backend.query()
        assert len(results) == 1
        assert results[0].action == "update"

    def test_append_only(self, tmp_path):
        filepath = str(tmp_path / "audit.log")
        backend = FileAuditBackend(filepath=filepath)

        for i in range(3):
            backend.write(AuditEvent(
                category=AuditCategory.AUTH,
                action=f"action_{i}"))

        with open(filepath) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 3

    def test_query_nonexistent_file(self, tmp_path):
        filepath = str(tmp_path / "missing.log")
        backend = FileAuditBackend(filepath=filepath)
        results = backend.query()
        assert results == []

    def test_filter_on_file(self, tmp_path):
        filepath = str(tmp_path / "audit.log")
        backend = FileAuditBackend(filepath=filepath)

        backend.write(AuditEvent(
            category=AuditCategory.AUTH, action="login"))
        backend.write(AuditEvent(
            category=AuditCategory.SCAN, action="start"))

        results = backend.query(category=AuditCategory.SCAN)
        assert len(results) == 1


class TestAuditLogger:
    def test_log_and_query(self):
        logger = AuditLogger()
        logger.log(AuditEvent(
            category=AuditCategory.AUTH,
            action="login",
            actor="admin",
        ))

        events = logger.query()
        assert len(events) == 1

    def test_log_auth(self):
        logger = AuditLogger()
        logger.log_auth("login", "admin",
                       detail="Success", source_ip="10.0.0.1")

        events = logger.query(category=AuditCategory.AUTH)
        assert len(events) == 1
        assert events[0].source_ip == "10.0.0.1"

    def test_log_config(self):
        logger = AuditLogger()
        logger.log_config("update", "admin",
                         resource="sf.config",
                         old_value="x", new_value="y")

        events = logger.query(category=AuditCategory.CONFIG)
        assert len(events) == 1
        assert events[0].severity == AuditSeverity.WARNING

    def test_log_scan(self):
        logger = AuditLogger()
        logger.log_scan("start", actor="api",
                       resource_id="scan-123",
                       target="example.com")

        events = logger.query(category=AuditCategory.SCAN)
        assert len(events) == 1
        assert events[0].metadata.get("target") == "example.com"

    def test_log_api(self):
        logger = AuditLogger()
        logger.log_api("access", "user1",
                      source_ip="192.168.1.1",
                      endpoint="/api/scan")

        events = logger.query(category=AuditCategory.API)
        assert len(events) == 1

    def test_multiple_backends(self, tmp_path):
        filepath = str(tmp_path / "audit.log")
        memory = MemoryAuditBackend()
        file_b = FileAuditBackend(filepath=filepath)
        logger = AuditLogger(backends=[memory, file_b])

        logger.log(AuditEvent(
            category=AuditCategory.AUTH, action="test"))

        # Both backends should have the event
        assert len(memory.query()) == 1
        assert len(file_b.query()) == 1

    def test_hooks(self):
        logger = AuditLogger()
        received = []
        logger.add_hook(lambda e: received.append(e))

        logger.log(AuditEvent(
            category=AuditCategory.AUTH, action="test"))
        assert len(received) == 1

    def test_stats(self):
        logger = AuditLogger()
        logger.log(AuditEvent(
            category=AuditCategory.AUTH, action="a"))
        logger.log(AuditEvent(
            category=AuditCategory.AUTH, action="b"))

        s = logger.stats
        assert s["total_events"] == 2
        assert s["backends"] == 1

    def test_add_backend(self):
        logger = AuditLogger()
        logger.add_backend(MemoryAuditBackend())
        assert logger.stats["backends"] == 2


class TestSingleton:
    def test_get_audit_logger(self):
        import spiderfoot.audit_log as mod
        mod._audit_instance = None
        a1 = get_audit_logger()
        a2 = get_audit_logger()
        assert a1 is a2
        mod._audit_instance = None
