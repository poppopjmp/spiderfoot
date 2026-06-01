"""Tests for spiderfoot.tasks.monitor — subdomain-change & recurring-scan tasks.

External dependencies (Redis, the DB lookup, and the run_scan task) are mocked
so the change-detection and schedule-triggering logic runs deterministically.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock

import pytest

from test.unit.utils.fake_redis import FakeRedis

import spiderfoot.tasks.monitor as monitor


class TestCheckSubdomainChanges:
    def test_detects_new_subdomains_from_empty_snapshot(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("redis.from_url", lambda *a, **k: fake)
        monkeypatch.setattr(monitor, "_get_current_subdomains",
                            lambda target: ["a.example.com", "b.example.com"])

        result = monitor.check_subdomain_changes(target="example.com")
        assert result["has_changes"] is True
        assert result["new"] == ["a.example.com", "b.example.com"]
        assert result["removed"] == []
        assert result["total_current"] == 2

    def test_detects_new_and_removed_against_previous(self, monkeypatch):
        monkeypatch.setattr("redis.from_url", lambda *a, **k: FakeRedis())
        monkeypatch.setattr(monitor, "_get_current_subdomains",
                            lambda target: ["a.example.com", "c.example.com"])

        prev = {"subdomains": ["a.example.com", "b.example.com"], "timestamp": 1}
        result = monitor.check_subdomain_changes(
            target="example.com", previous_snapshot=prev)
        assert result["new"] == ["c.example.com"]
        assert result["removed"] == ["b.example.com"]

    def test_no_changes(self, monkeypatch):
        monkeypatch.setattr("redis.from_url", lambda *a, **k: FakeRedis())
        monkeypatch.setattr(monitor, "_get_current_subdomains",
                            lambda target: ["a.example.com"])
        prev = {"subdomains": ["a.example.com"], "timestamp": 1}
        result = monitor.check_subdomain_changes(
            target="example.com", previous_snapshot=prev)
        assert result["has_changes"] is False

    def test_snapshot_persisted(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("redis.from_url", lambda *a, **k: fake)
        monkeypatch.setattr(monitor, "_get_current_subdomains",
                            lambda target: ["x.example.com"])
        monitor.check_subdomain_changes(target="example.com")
        # A snapshot should now be stored for the target.
        assert any("sf:monitor:subdomains:" in k for k in fake._store)


class TestTriggerRecurringScans:
    def test_triggers_due_and_skips_future(self, monkeypatch):
        fake = FakeRedis()
        now = time.time()
        fake.sadd("sf:recurring:schedules",
                  json.dumps({"target": "due.com", "next_run": now - 10,
                              "interval_seconds": 3600}))
        fake.sadd("sf:recurring:schedules",
                  json.dumps({"target": "future.com", "next_run": now + 10000}))
        monkeypatch.setattr("redis.from_url", lambda *a, **k: fake)

        run_scan_mock = MagicMock()
        monkeypatch.setattr("spiderfoot.tasks.scan.run_scan", run_scan_mock)

        result = monitor.trigger_recurring_scans()
        assert result["triggered"] == 1
        run_scan_mock.apply_async.assert_called_once()
        # The due schedule's target was passed through.
        kwargs = run_scan_mock.apply_async.call_args.kwargs["kwargs"]
        assert kwargs["scan_target"] == "due.com"

    def test_invalid_schedule_skipped(self, monkeypatch):
        fake = FakeRedis()
        fake.sadd("sf:recurring:schedules", "not-json")
        monkeypatch.setattr("redis.from_url", lambda *a, **k: fake)
        monkeypatch.setattr("spiderfoot.tasks.scan.run_scan", MagicMock())
        # Must not raise; nothing triggered.
        assert monitor.trigger_recurring_scans()["triggered"] == 0
