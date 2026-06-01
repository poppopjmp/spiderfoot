"""Tests for the standalone Celery tasks/helpers in spiderfoot.tasks.scan.

The full run_scan pipeline is integration-tested elsewhere; this module covers
the smaller, side-effecting tasks and DB helpers with Redis and the DB handle
mocked: progress publishing, abort requests, batch submission, and status
updates.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from test.unit.utils.fake_redis import FakeRedis

import spiderfoot.tasks.scan as scan_tasks


class TestUpdateScanProgress:
    def test_writes_hash_and_publishes(self, monkeypatch):
        fake = FakeRedis()
        monkeypatch.setattr("redis.from_url", lambda *a, **k: fake)

        scan_tasks.update_scan_progress.run(
            scan_id="s1", progress=50, modules_completed=5,
            modules_total=10, events_produced=42,
        )

        stored = fake.hgetall("sf:scan:progress:s1")
        assert stored["progress"] == "50"
        assert stored["events_produced"] == "42"
        # A progress event was published for WebSocket subscribers.
        assert fake.published
        channel, payload = fake.published[0]
        assert channel == "sf:scan:events:s1"
        assert json.loads(payload)["progress"] == 50


class TestAbortScan:
    def test_sets_abort_requested_status(self, monkeypatch):
        dbh = MagicMock()
        fake_db_module = MagicMock()
        fake_db_module.SpiderFootDb.return_value = dbh
        with patch.dict("sys.modules", {"spiderfoot.db": fake_db_module}):
            result = scan_tasks.abort_scan.run("s1", {})
        assert result["status"] == "abort-requested"
        dbh.scanInstanceSet.assert_called_once_with("s1", status="ABORT-REQUESTED")

    def test_db_failure_is_swallowed(self, monkeypatch):
        fake_db_module = MagicMock()
        fake_db_module.SpiderFootDb.side_effect = RuntimeError("db down")
        with patch.dict("sys.modules", {"spiderfoot.db": fake_db_module}):
            # Must not raise even if the DB is unavailable.
            result = scan_tasks.abort_scan.run("s1", {})
        assert result["status"] == "abort-requested"


class TestRunBatchScans:
    def test_submits_each_scan(self, monkeypatch):
        submitted_ids = iter(["task-1", "task-2"])

        def fake_apply_async(*args, **kwargs):
            m = MagicMock()
            m.id = next(submitted_ids)
            return m

        monkeypatch.setattr(scan_tasks.run_scan, "apply_async", fake_apply_async)

        scans = [
            {"scan_name": "a", "scan_id": "s1", "target_value": "x",
             "target_type": "IP_ADDRESS", "module_list": [], "global_opts": {}},
            {"scan_name": "b", "scan_id": "s2", "target_value": "y",
             "target_type": "IP_ADDRESS", "module_list": [], "global_opts": {}},
        ]
        result = scan_tasks.run_batch_scans.run(scans)
        assert result["count"] == 2
        assert result["submitted"] == {"s1": "task-1", "s2": "task-2"}


class TestUpdateScanStatusHelper:
    def test_logs_error_event_when_error_given(self):
        dbh = MagicMock()
        fake_db_module = MagicMock()
        fake_db_module.SpiderFootDb.return_value = dbh
        with patch.dict("sys.modules", {"spiderfoot.db": fake_db_module}):
            scan_tasks._update_scan_status("s1", {}, "ERROR-FAILED", error="boom")
        dbh.scanInstanceSet.assert_called_once_with("s1", status="ERROR-FAILED")
        dbh.scanLogEvent.assert_called_once()
        assert "boom" in dbh.scanLogEvent.call_args.args

    def test_no_error_event_when_no_error(self):
        dbh = MagicMock()
        fake_db_module = MagicMock()
        fake_db_module.SpiderFootDb.return_value = dbh
        with patch.dict("sys.modules", {"spiderfoot.db": fake_db_module}):
            scan_tasks._update_scan_status("s1", {}, "FINISHED")
        dbh.scanInstanceSet.assert_called_once_with("s1", status="FINISHED")
        dbh.scanLogEvent.assert_not_called()
