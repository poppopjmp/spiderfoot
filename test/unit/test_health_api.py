"""
Tests for spiderfoot.api.routers.health — Health Check API.

Covers: liveness, readiness, startup probes, individual component
checks, dashboard, Prometheus metrics endpoint, subsystem check
functions, and aggregation logic.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import spiderfoot.api.routers.health as health_mod
from spiderfoot.api.routers.health import (
    _SUBSYSTEM_CHECKS,
    _check_app_config,
    _check_database,
    _check_eventbus,
    _check_modules,
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

class TestDatabaseCheck:
    def test_no_registry(self):
        with patch.object(health_mod, "_get_registry", return_value=None):
            result = _check_database()
        assert result["status"] == "unknown"
        assert "ServiceRegistry" in result["message"]

    def test_no_data_service(self):
        mock_reg = MagicMock()
        mock_reg.get_optional.return_value = None
        with patch.object(health_mod, "_get_registry", return_value=mock_reg):
            result = _check_database()
        assert result["status"] == "unknown"
        assert "not registered" in result["message"]

    def test_no_dbh(self):
        mock_data = MagicMock(spec=["dbh"])
        mock_data.dbh = None
        mock_reg = MagicMock()
        mock_reg.get_optional.return_value = mock_data
        with patch.object(health_mod, "_get_registry", return_value=mock_reg):
            result = _check_database()
        assert result["status"] == "down"

    def test_database_up(self):
        mock_data = MagicMock()
        mock_data.dbh.conn.execute.return_value = None
        mock_reg = MagicMock()
        mock_reg.get_optional.return_value = mock_data
        with patch.object(health_mod, "_get_registry", return_value=mock_reg):
            result = _check_database()
        assert result["status"] == "up"

    def test_database_query_fails(self):
        mock_data = MagicMock()
        mock_data.dbh.conn.execute.side_effect = RuntimeError("disk I/O")
        mock_reg = MagicMock()
        mock_reg.get_optional.return_value = mock_data
        with patch.object(health_mod, "_get_registry", return_value=mock_reg):
            result = _check_database()
        assert result["status"] == "down"
        assert "disk I/O" in result["message"]


class TestEventBusCheck:
    def test_no_registry(self):
        with patch.object(health_mod, "_get_registry", return_value=None):
            result = _check_eventbus()
        assert result["status"] == "unknown"

    def test_no_bus(self):
        mock_reg = MagicMock()
        mock_reg.get_optional.return_value = None
        with patch.object(health_mod, "_get_registry", return_value=mock_reg):
            result = _check_eventbus()
        assert result["status"] == "unknown"

    def test_plain_bus_connected(self):
        mock_bus = MagicMock(spec=[])  # no health_check
        mock_bus.is_connected = MagicMock(return_value=True)
        mock_reg = MagicMock()
        mock_reg.get_optional.return_value = mock_bus
        with patch.object(health_mod, "_get_registry", return_value=mock_reg):
            result = _check_eventbus()
        assert result["status"] == "up"

    def test_plain_bus_disconnected(self):
        mock_bus = MagicMock(spec=[])
        mock_bus.is_connected = MagicMock(return_value=False)
        mock_reg = MagicMock()
        mock_reg.get_optional.return_value = mock_bus
        with patch.object(health_mod, "_get_registry", return_value=mock_reg):
            result = _check_eventbus()
        assert result["status"] == "down"


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


class TestModulesCheck:
    def _make_monitor(self, summary):
        mock = MagicMock()
        mock.get_report.return_value = {"summary": summary}
        return mock

    def test_no_modules_registered(self):
        m = self._make_monitor({"total": 0})
        with patch(
            "spiderfoot.module_health.get_health_monitor",
            return_value=m,
        ):
            result = _check_modules()
        assert result["status"] == "unknown"

    def test_all_healthy(self):
        m = self._make_monitor({
            "total": 10, "healthy": 10,
            "degraded": 0, "unhealthy": 0, "stalled": 0,
        })
        with patch(
            "spiderfoot.module_health.get_health_monitor",
            return_value=m,
        ):
            result = _check_modules()
        assert result["status"] == "up"
        assert result["total"] == 10

    def test_some_unhealthy(self):
        m = self._make_monitor({
            "total": 10, "healthy": 7,
            "degraded": 1, "unhealthy": 2, "stalled": 0,
        })
        with patch(
            "spiderfoot.module_health.get_health_monitor",
            return_value=m,
        ):
            result = _check_modules()
        assert result["status"] == "degraded"

    def test_majority_unhealthy(self):
        m = self._make_monitor({
            "total": 10, "healthy": 2,
            "degraded": 0, "unhealthy": 6, "stalled": 2,
        })
        with patch(
            "spiderfoot.module_health.get_health_monitor",
            return_value=m,
        ):
            result = _check_modules()
        assert result["status"] == "down"


class TestReportStorageCheck:
    def test_storage_up(self):
        mock_store = MagicMock()
        mock_store.count.return_value = 5
        mock_store.config.backend.value = "postgresql"

        with patch(
            "spiderfoot.report_storage.ReportStore",
            return_value=mock_store,
        ):
            result = _check_report_storage()
        assert result["status"] == "up"
        assert result["report_count"] == 5

    def test_storage_error(self):
        with patch(
            "spiderfoot.report_storage.ReportStore",
            side_effect=RuntimeError("DB locked"),
        ):
            result = _check_report_storage()
        assert result["status"] == "down"
        assert "locked" in result.get("message", "")


class TestAppConfigCheck:
    def test_config_valid(self):
        result = _check_app_config()
        assert result["status"] == "up"

    def test_config_import_error(self):
        with patch.dict("sys.modules", {"spiderfoot.app_config": None}):
            result = _check_app_config()
        assert result["status"] in ("down", "unknown")


# ===================================================================
# Aggregation
# ===================================================================

class TestRunAllChecks:
    def test_all_checks_return_dict(self):
        """Each check should return without throwing."""
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
            "svc_a": lambda: {"status": "up"},
            "svc_b": lambda: {"status": "degraded"},
        }
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            result = run_all_checks()
        assert result["status"] == "degraded"

    def test_overall_down(self):
        checks = {
            "svc_a": lambda: {"status": "up"},
            "svc_b": lambda: {"status": "down"},
        }
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            result = run_all_checks()
        assert result["status"] == "down"

    def test_exception_in_check(self):
        def bad():
            raise RuntimeError("boom")

        checks = {
            "svc_bad": bad,
            "svc_ok": lambda: {"status": "up"},
        }
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            result = run_all_checks()
        assert result["status"] == "down"
        assert result["components"]["svc_bad"]["status"] == "down"
        assert "boom" in result["components"]["svc_bad"]["message"]
        assert result["components"]["svc_ok"]["status"] == "up"

    def test_latency_tracked(self):
        checks = {"svc": lambda: {"status": "up"}}
        with patch.dict(_SUBSYSTEM_CHECKS, checks, clear=True):
            result = run_all_checks()
        assert "latency_ms" in result["components"]["svc"]

    def test_uptime_positive(self):
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
        assert "oops" in result["message"]


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
        with patch.dict("sys.modules", {"spiderfoot.metrics": None}):
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
        checks = {"svc": lambda: {"status": "down"}}
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
        checks = {"svc": lambda: {"status": "down"}}
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
