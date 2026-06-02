"""Tests for spiderfoot.tasks.maintenance — Celery housekeeping tasks.

These tasks talk to Redis / PostgreSQL / HTTP services; the external calls are
mocked so the task bodies run and return their result dicts. This locks in a
previously-fixed bug in this module (an undefined ``log`` reference) by
executing each task end to end.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from test.unit.utils.fake_redis import FakeRedis

import spiderfoot.tasks.maintenance as maint


class TestCleanupExpiredResults:
    def test_removes_stale_progress_keys(self, monkeypatch):
        fake = FakeRedis()
        # One stale key (3 days old) and one fresh key.
        fake.hset("sf:scan:progress:old", "updated_at", str(time.time() - 300000))
        fake.hset("sf:scan:progress:new", "updated_at", str(time.time()))
        monkeypatch.setattr("redis.from_url", lambda *a, **k: fake)

        result = maint.cleanup_expired_results()
        assert result["cleaned_progress_keys"] == 1
        # The fresh key survives; the stale one is gone.
        assert fake.hget("sf:scan:progress:new", "updated_at") is not None
        assert fake.hget("sf:scan:progress:old", "updated_at") is None

    def test_no_keys(self, monkeypatch):
        monkeypatch.setattr("redis.from_url", lambda *a, **k: FakeRedis())
        assert maint.cleanup_expired_results()["cleaned_progress_keys"] == 0


class TestServiceHealthCheck:
    def test_all_healthy(self, monkeypatch):
        resp = MagicMock()
        resp.getcode.return_value = 200
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: resp)

        result = maint.service_health_check()
        assert result["healthy"] == result["total"]
        assert all(v["status"] == "healthy" for v in result["services"].values())

    def test_all_unhealthy(self, monkeypatch):
        def boom(*a, **k):
            raise OSError("connection refused")
        monkeypatch.setattr("urllib.request.urlopen", boom)

        result = maint.service_health_check()
        assert result["healthy"] == 0
        assert all(v["status"] == "unhealthy" for v in result["services"].values())


class TestDatabaseVacuum:
    def test_missing_dsn_returns_error(self, monkeypatch):
        monkeypatch.delenv("SF_POSTGRES_DSN", raising=False)
        result = maint.database_vacuum()
        assert result["status"] == "error"

    def test_vacuum_success(self, monkeypatch):
        monkeypatch.setenv("SF_POSTGRES_DSN", "postgresql://localhost/sf")
        fake_conn = MagicMock()
        fake_psycopg2 = MagicMock()
        fake_psycopg2.connect.return_value = fake_conn
        with patch.dict("sys.modules", {"psycopg2": fake_psycopg2}):
            result = maint.database_vacuum()
        assert result["status"] == "completed"
        fake_conn.cursor.return_value.execute.assert_called_once_with("VACUUM ANALYZE;")

    def test_vacuum_failure(self, monkeypatch):
        monkeypatch.setenv("SF_POSTGRES_DSN", "postgresql://localhost/sf")
        fake_psycopg2 = MagicMock()
        fake_psycopg2.connect.side_effect = RuntimeError("db down")
        with patch.dict("sys.modules", {"psycopg2": fake_psycopg2}):
            result = maint.database_vacuum()
        assert result["status"] == "failed"
        assert "db down" in result["error"]
