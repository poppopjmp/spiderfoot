"""
Tests for spiderfoot.api.routers.health — Health Check API.

Covers: liveness, readiness, startup probes, individual component
checks, dashboard, Prometheus metrics endpoint, subsystem check
functions, and aggregation logic.
"""
from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest

import spiderfoot.api.routers.health as health_mod
from spiderfoot.api.routers.health import (
    _SUBSYSTEM_CHECKS,
    _check_app_config,
    _check_celery,
    _check_postgresql,
    _check_redis,
    _check_report_storage,
    _check_vector,
    _get_metrics_text,
    mark_startup_complete,
    run_all_checks,
    run_single_check,
)

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from spiderfoot.api.routers.health import router

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def reset_startup():
    """Reset the startup flag between tests."""
    original = health_mod._startup_complete
    health_mod._startup_complete = False
    yield
    health_mod._startup_complete = original


@pytest.fixture
def client():
    if not HAS_FASTAPI:
        pytest.skip("FastAPI not installed")
    app = FastAPI()
    app.include_router(router, tags=["health"])
    return TestClient(app)


# ===================================================================
# Individual subsystem check functions
# ===================================================================

class TestPostgresqlCheck:
    def test_no_dsn(self):
        with patch.dict(os.environ, {"SF_POSTGRES_DSN": ""}):
            result = _check_postgresql()
        assert result["status"] == "unknown"
        assert "SF_POSTGRES_DSN" in result["message"]

    def test_postgresql_up(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [("PostgreSQL 15.2",), (42,)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2 = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        with patch.dict(os.environ, {"SF_POSTGRES_DSN": "postgresql://localhost/sf"}):
            with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
                result = _check_postgresql()
        assert result["status"] == "up"
        assert result["scan_count"] == 42
        assert "PostgreSQL" in result["version"]

    def test_postgresql_connection_fails(self):
        mock_psycopg2 = MagicMock()
        mock_psycopg2.connect.side_effect = RuntimeError("connection refused")
        with patch.dict(os.environ, {"SF_POSTGRES_DSN": "postgresql://localhost/sf"}):
            with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
                result = _check_postgresql()
        assert result["status"] == "down"

    def test_psycopg2_not_installed(self):
        with patch.dict(os.environ, {"SF_POSTGRES_DSN": "postgresql://localhost/sf"}):
            with patch.dict("sys.modules", {"psycopg2": None}):
                result = _check_postgresql()
        assert result["status"] in ("unknown", "down")


class TestRedisCheck:
    def test_redis_up(self):
        mock_redis_instance = MagicMock()
        mock_redis_instance.info.return_value = {"redis_version": "7.0.0"}
        mock_redis_mod = MagicMock()
        mock_redis_mod.Redis.from_url.return_value = mock_redis_instance
        with patch.dict("sys.modules", {"redis": mock_redis_mod}):
            result = _check_redis()
        assert result["status"] == "up"
        assert result["redis_version"] == "7.0.0"

    def test_redis_connection_fails(self):
        mock_redis_mod = MagicMock()
        mock_redis_mod.Redis.from_url.side_effect = ConnectionError("refused")
        with patch.dict("sys.modules", {"redis": mock_redis_mod}):
            result = _check_redis()
        assert result["status"] == "down"

    def test_redis_not_installed(self):
        with patch.dict("sys.modules", {"redis": None}):
            result = _check_redis()
        assert result["status"] in ("unknown", "down")


class TestVectorCheck:
    def test_vector_reachable(self):
        mock_health = MagicMock()
        mock_health.reachable = True
        mock_health.version = "0.30.0"
        mock_health.uptime_seconds = 3600
        mock_vb = MagicMock()
        mock_vb.check_health.return_value = mock_health

        with patch(
            "spiderfoot.vector_bootstrap.VectorBootstrap",
            return_value=mock_vb,
        ):
            result = _check_vector()
        assert result["status"] == "up"
        assert result["version"] == "0.30.0"

    def test_vector_unreachable(self):
        mock_health = MagicMock()
        mock_health.reachable = False
        mock_health.error = "Connection refused"
        mock_vb = MagicMock()
        mock_vb.check_health.return_value = mock_health

        with patch(
            "spiderfoot.vector_bootstrap.VectorBootstrap",
            return_value=mock_vb,
        ):
            result = _check_vector()
        assert result["status"] == "down"
        assert "refused" in result.get("message", "")

    def test_vector_import_error(self):
        with patch.dict("sys.modules", {"spiderfoot.vector_bootstrap": None}):
            result = _check_vector()
        assert result["status"] in ("down", "unknown")


class TestCeleryCheck:
    def test_celery_up(self):
        mock_redis_instance = MagicMock()
        mock_redis_instance.keys.return_value = [b"celery-task-meta-1", b"celery-task-meta-2"]
        mock_redis_instance.llen.return_value = 3
        mock_redis_mod = MagicMock()
        mock_redis_mod.Redis.from_url.return_value = mock_redis_instance
        with patch.dict("sys.modules", {"redis": mock_redis_mod}):
            result = _check_celery()
        assert result["status"] == "up"
        assert result["completed_tasks"] == 2
        assert result["pending_queue"] == 3

    def test_celery_connection_fails(self):
        mock_redis_mod = MagicMock()
        mock_redis_mod.Redis.from_url.side_effect = ConnectionError("refused")
        with patch.dict("sys.modules", {"redis": mock_redis_mod}):
            result = _check_celery()
        assert result["status"] == "down"

    def test_redis_not_installed_for_celery(self):
        with patch.dict("sys.modules", {"redis": None}):
            result = _check_celery()
        assert result["status"] in ("unknown", "down")


class TestReportStorageCheck:
    def test_storage_up(self):
        mock_store = MagicMock()
        mock_store.count.return_value = 5
        mock_store.config.backend.value = "postgresql"

        with patch(
            "spiderfoot.reporting.report_storage.ReportStore",
            return_value=mock_store,
        ):
            result = _check_report_storage()
        assert result["status"] == "up"
        assert result["report_count"] == 5

    def test_storage_error(self):
        with patch(
            "spiderfoot.reporting.report_storage.ReportStore",
            side_effect=RuntimeError("DB locked"),
        ):
            result = _check_report_storage()
        assert result["status"] == "down"
        assert "message" in result


class TestAppConfigCheck:
    def test_config_valid(self):
        result = _check_app_config()
        assert result["status"] == "up"

    def test_config_import_error(self):
        with patch.dict("sys.modules", {"spiderfoot.config.app_config": None}):
            result = _check_app_config()
        assert result["status"] in ("down", "unknown")


# ===================================================================
# Aggregation
# ===================================================================

class TestRunAllChecks:
    def test_all_checks_return_dict(self):
        """Each check should return without throwing (all checks mocked)."""
        mock_checks = {
            "postgresql": lambda: {"status": "up"},
            "redis": lambda: {"status": "up"},
            "celery": lambda: {"status": "up"},
            "vector": lambda: {"status": "up"},
            "minio": lambda: {"status": "up"},
            "app_config": lambda: {"status": "up"},
            "report_storage": lambda: {"status": "up"},
            "scan_hooks": lambda: {"status": "up"},
            "module_timeout": lambda: {"status": "up"},
        }
        with patch.dict(health_mod._SUBSYSTEM_CHECKS, mock_checks, clear=True):
            result = run_all_checks()
        assert "status" in result
        assert "components" in result
        assert "uptime_seconds" in result
        assert isinstance(result["components"], dict)

    def test_overall_up_when_all_up(self):
        checks = {
            "svc_a": lambda: {"status": "up"},
            "svc_b": lambda: {"status": "up"},
        }
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            result = run_all_checks()
        assert result["status"] == "up"

    def test_overall_degraded(self):
        checks = {
            "postgresql": lambda: {"status": "up"},
            "redis": lambda: {"status": "degraded"},
        }
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            result = run_all_checks()
        assert result["status"] == "degraded"

    def test_overall_down(self):
        checks = {
            "postgresql": lambda: {"status": "up"},
            "redis": lambda: {"status": "down"},
        }
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            result = run_all_checks()
        assert result["status"] == "down"

    def test_exception_in_check(self):
        def bad():
            raise RuntimeError("boom")

        checks = {
            "postgresql": bad,
            "redis": lambda: {"status": "up"},
        }
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            result = run_all_checks()
        assert result["status"] == "down"
        assert result["components"]["postgresql"]["status"] == "down"
        assert "Service check failed" in result["components"]["postgresql"]["message"]
        assert result["components"]["redis"]["status"] == "up"

    def test_latency_tracked(self):
        checks = {"svc": lambda: {"status": "up"}}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            result = run_all_checks()
        assert "latency_ms" in result["components"]["svc"]

    def test_uptime_positive(self):
        with patch.dict(_SUBSYSTEM_CHECKS, {}, clear=True):
            result = run_all_checks()
        assert result["uptime_seconds"] >= 0


class TestRunSingleCheck:
    def test_existing_check(self):
        checks = {"test_svc": lambda: {"status": "up"}}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            result = run_single_check("test_svc")
        assert result is not None
        assert result["status"] == "up"
        assert "latency_ms" in result

    def test_nonexistent_check(self):
        with patch.dict(_SUBSYSTEM_CHECKS, {}, clear=True):
            result = run_single_check("nope")
        assert result is None

    def test_exception_handling(self):
        def bad():
            raise ValueError("oops")
        checks = {"bad": bad}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            result = run_single_check("bad")
        assert result["status"] == "down"
        assert "Service check failed" in result["message"]


# ===================================================================
# Startup flag
# ===================================================================

class TestStartupFlag:
    def test_mark_startup(self, reset_startup):
        assert health_mod._startup_complete is False
        mark_startup_complete()
        assert health_mod._startup_complete is True


# ===================================================================
# Prometheus metrics
# ===================================================================

class TestMetrics:
    def test_metrics_returns_string(self):
        text = _get_metrics_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_metrics_import_error(self):
        with patch.dict("sys.modules", {"spiderfoot.observability.metrics": None}):
            text = _get_metrics_text()
        assert "unavailable" in text


# ===================================================================
# FastAPI endpoint tests
# ===================================================================

@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestHealthEndpoints:
    def test_liveness(self, client):
        resp = client.get("/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "up"
        assert "uptime_seconds" in data
        assert "python_version" in data

    def test_startup_not_ready(self, client, reset_startup):
        resp = client.get("/health/startup")
        assert resp.status_code == 503
        data = resp.json()
        assert data["startup_complete"] is False

    def test_startup_ready(self, client, reset_startup):
        mark_startup_complete()
        resp = client.get("/health/startup")
        assert resp.status_code == 200
        data = resp.json()
        assert data["startup_complete"] is True

    def test_health_overall(self, client):
        checks = {"svc": lambda: {"status": "up"}}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "up"

    def test_health_overall_down(self, client):
        checks = {"postgresql": lambda: {"status": "down"}}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            resp = client.get("/health")
        assert resp.status_code == 503

    def test_readiness_up(self, client):
        checks = {"svc": lambda: {"status": "up"}}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            resp = client.get("/health/ready")
        assert resp.status_code == 200

    def test_readiness_degraded_still_200(self, client):
        checks = {"svc": lambda: {"status": "degraded"}}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            resp = client.get("/health/ready")
        assert resp.status_code == 200

    def test_readiness_down_503(self, client):
        checks = {"postgresql": lambda: {"status": "down"}}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            resp = client.get("/health/ready")
        assert resp.status_code == 503

    def test_dashboard(self, client):
        checks = {
            "svc_a": lambda: {"status": "up"},
            "svc_b": lambda: {"status": "up"},
        }
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            resp = client.get("/health/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "subsystems_available" in data
        assert "python" in data
        assert "components" in data

    def test_component_health_found(self, client):
        checks = {"mydb": lambda: {"status": "up"}}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            resp = client.get("/health/mydb")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "up"

    def test_component_health_not_found(self, client):
        with patch.dict(_SUBSYSTEM_CHECKS, {}, clear=True):
            resp = client.get("/health/nonexistent")
        assert resp.status_code == 404

    def test_component_health_down_503(self, client):
        checks = {"broken": lambda: {"status": "down"}}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            resp = client.get("/health/broken")
        assert resp.status_code == 503

    def test_metrics_endpoint(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]

    def test_health_response_format(self, client):
        checks = {"svc": lambda: {"status": "up"}}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert "uptime_seconds" in data
        assert "components" in data
        assert "svc" in data["components"]
        assert "latency_ms" in data["components"]["svc"]
