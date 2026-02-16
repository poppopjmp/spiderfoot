"""
Health Check API Router for SpiderFoot.

Exposes Kubernetes-compatible health probes and a comprehensive
service status dashboard through FastAPI endpoints.  Wires together
subsystem-specific checks (PostgreSQL, Redis, Celery, Vector.dev,
MinIO, app config) and Prometheus-compatible metrics.

Endpoints:
  GET /health           - Overall health (liveness + readiness)
  GET /health/live      - Liveness probe (is process alive?)
  GET /health/ready     - Readiness probe (can handle traffic?)
  GET /health/startup   - Startup probe (initialization done?)
  GET /health/dashboard - Full subsystem status overview
  GET /health/{name}    - Individual component check
  GET /metrics          - Prometheus exposition format
"""

from __future__ import annotations

import logging
import os
import platform
import sys
import time
from typing import Any

log = logging.getLogger("spiderfoot.api.health")

try:
    from fastapi import APIRouter, HTTPException, Response
    from fastapi.responses import PlainTextResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# -----------------------------------------------------------------------
# Health check providers — lazy imports to avoid hard dependencies
# -----------------------------------------------------------------------


def _check_vector() -> dict[str, Any]:
    """Vector.dev log pipeline health."""
    try:
        from spiderfoot.vector_bootstrap import VectorBootstrap, VectorBootstrapConfig
        # Use VECTOR_API_URL env or Docker service name 'vector' on API port 8687
        api_url = os.environ.get("VECTOR_API_URL", "http://vector:8687")
        cfg = VectorBootstrapConfig(
            vector_api_url=api_url,
            vector_graphql_url=f"{api_url}/graphql",
        )
        vb = VectorBootstrap(config=cfg)
        health = vb.check_health()
        if health.reachable:
            return {
                "status": "up",
                "version": health.version,
                "uptime_seconds": health.uptime_seconds,
            }
        return {
            "status": "down",
            "message": health.error or "Unreachable",
        }
    except ImportError:
        return {"status": "unknown", "message": "VectorBootstrap not available"}
    except Exception as e:
        return {"status": "down", "message": str(e)}


def _check_report_storage() -> dict[str, Any]:
    """Report storage backend health."""
    try:
        from spiderfoot.reporting.report_storage import ReportStore, StoreConfig
        store = ReportStore(StoreConfig())
        # Quick count to verify backend
        count = store.count()
        return {
            "status": "up",
            "backend": store.config.backend.value,
            "report_count": count,
        }
    except ImportError:
        return {"status": "unknown", "message": "ReportStore not available"}
    except Exception as e:
        return {"status": "down", "message": str(e)}


def _check_app_config() -> dict[str, Any]:
    """Application config validation."""
    try:
        from spiderfoot.config.app_config import AppConfig
        cfg = AppConfig()  # defaults
        errors = cfg.validate()
        if errors:
            return {
                "status": "degraded",
                "errors": [str(e) for e in errors[:5]],
            }
        return {"status": "up"}
    except ImportError:
        return {"status": "unknown", "message": "AppConfig not available"}
    except Exception as e:
        return {"status": "down", "message": str(e)}


def _check_scan_hooks() -> dict[str, Any]:
    """Scan lifecycle hooks health and statistics."""
    try:
        from spiderfoot.scan.scan_hooks import get_scan_hooks
        hooks = get_scan_hooks()
        stats = hooks.stats()
        return {
            "status": "up",
            "total_events_fired": stats.get("total_events", 0),
            "listener_count": stats.get("listener_count", 0),
            "recent_events": stats.get("recent_count", 0),
        }
    except ImportError:
        return {"status": "unknown", "message": "scan_hooks module not available"}
    except Exception as e:
        return {"status": "down", "message": str(e)}


def _check_module_timeout() -> dict[str, Any]:
    """Module timeout guard health and statistics."""
    try:
        from spiderfoot.plugins.module_timeout import get_timeout_guard
        guard = get_timeout_guard()
        stats = guard.stats()
        return {
            "status": "up",
            "default_timeout_s": guard.default_timeout,
            "total_guarded": stats.get("total_guarded", 0),
            "total_timeouts": stats.get("total_timeouts", 0),
            "hard_interrupt": guard.hard_interrupt,
        }
    except ImportError:
        return {"status": "unknown", "message": "module_timeout module not available"}
    except Exception as e:
        return {"status": "down", "message": str(e)}


# -----------------------------------------------------------------------
# Prometheus metrics helper
# -----------------------------------------------------------------------

def _get_metrics_text() -> str:
    """Return Prometheus exposition text."""
    try:
        from spiderfoot.observability.metrics import get_registry
        registry = get_registry()
        return registry.expose()
    except ImportError:
        return "# spiderfoot_metrics_unavailable 1\n"
    except Exception as e:
        return f"# spiderfoot_metrics_error{{error=\"{e}\"}} 1\n"


# -----------------------------------------------------------------------
# MinIO object storage check
# -----------------------------------------------------------------------

def _check_minio() -> dict[str, Any]:
    """Check MinIO/S3 connectivity and bucket status."""
    try:
        from spiderfoot.storage.minio_manager import get_storage_manager
        mgr = get_storage_manager()
        return mgr.health_check()
    except ImportError:
        return {"status": "unknown", "message": "MinIO storage module not available"}
    except Exception as e:
        return {"status": "down", "message": str(e)}


def _check_redis() -> dict[str, Any]:
    """Check Redis connectivity."""
    try:
        import os
        import redis as redis_lib
        url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
        r = redis_lib.Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
        info = r.info("server")
        r.close()
        return {
            "status": "up",
            "redis_version": info.get("redis_version", "unknown"),
        }
    except ImportError:
        return {"status": "unknown", "message": "redis package not installed"}
    except Exception as e:
        return {"status": "down", "message": str(e)}


def _check_celery() -> dict[str, Any]:
    """Check Celery worker availability via ping."""
    try:
        import os
        import redis as redis_lib
        url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
        r = redis_lib.Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
        # Check if any celery worker keys exist in Redis
        worker_keys = r.keys("celery-task-meta-*")
        # Also check the broker queue length
        queue_len = r.llen("celery") or 0
        r.close()
        return {
            "status": "up",
            "completed_tasks": len(worker_keys),
            "pending_queue": int(queue_len),
        }
    except ImportError:
        return {"status": "unknown", "message": "redis package not installed"}
    except Exception as e:
        return {"status": "down", "message": str(e)}


def _check_postgresql() -> dict[str, Any]:
    """Direct PostgreSQL connectivity check."""
    try:
        import os
        dsn = os.environ.get("SF_POSTGRES_DSN", "")
        if not dsn:
            return {"status": "unknown", "message": "SF_POSTGRES_DSN not set"}
        import psycopg2
        conn = psycopg2.connect(dsn, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM tbl_scan_instance")
        scan_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {
            "status": "up",
            "version": version.split(",")[0] if version else "unknown",
            "scan_count": scan_count,
        }
    except ImportError:
        return {"status": "unknown", "message": "psycopg2 not installed"}
    except Exception as e:
        return {"status": "down", "message": str(e)}


# -----------------------------------------------------------------------
# Subsystem registry — run all checks
# -----------------------------------------------------------------------

_SUBSYSTEM_CHECKS = {
    "postgresql": _check_postgresql,
    "redis": _check_redis,
    "celery": _check_celery,
    "vector": _check_vector,
    "minio": _check_minio,
    "app_config": _check_app_config,
    "report_storage": _check_report_storage,
    "scan_hooks": _check_scan_hooks,
    "module_timeout": _check_module_timeout,
}

_startup_time = time.time()
_startup_complete = False


# Core subsystems whose failure should affect overall status.
# Optional/auxiliary subsystems report individual status but
# do not drag the overall health to "down".
_CORE_SUBSYSTEMS = {
    "postgresql", "redis", "celery", "minio", "vector",
}


def run_all_checks() -> dict[str, Any]:
    """Execute all registered subsystem checks and aggregate."""
    components: dict[str, Any] = {}
    overall = "up"

    for name, check_fn in _SUBSYSTEM_CHECKS.items():
        t0 = time.monotonic()
        try:
            result = check_fn()
        except Exception as e:
            result = {"status": "down", "message": str(e)}
        elapsed = (time.monotonic() - t0) * 1000
        result["latency_ms"] = round(elapsed, 2)
        components[name] = result

        # Only core subsystems affect the overall status
        if name not in _CORE_SUBSYSTEMS:
            continue

        status = result.get("status", "unknown")
        if status == "down":
            overall = "down"
        elif status == "degraded" and overall == "up":
            overall = "degraded"

    return {
        "status": overall,
        "uptime_seconds": round(time.time() - _startup_time, 1),
        "components": components,
    }


def run_single_check(name: str) -> dict[str, Any] | None:
    """Run a single named check. Returns None if not found."""
    check_fn = _SUBSYSTEM_CHECKS.get(name)
    if check_fn is None:
        return None
    t0 = time.monotonic()
    try:
        result = check_fn()
    except Exception as e:
        result = {"status": "down", "message": str(e)}
    result["latency_ms"] = round((time.monotonic() - t0) * 1000, 2)
    return result


def mark_startup_complete() -> None:
    """Mark application startup as done."""
    global _startup_complete
    _startup_complete = True
    log.info("Health: startup marked complete")


# -----------------------------------------------------------------------
# FastAPI router
# -----------------------------------------------------------------------

if not HAS_FASTAPI:
    class _StubRouter:
        """Stub router for when dependencies are unavailable."""
        pass
    router = _StubRouter()
else:
    router = APIRouter()

    @router.get(
        "/health",
        summary="Overall health check",
        description="Combined liveness and readiness. Returns 200 if healthy, 503 if degraded/down.",
    )
    async def health() -> Response:
        """Return overall health status of all subsystems."""
        result = run_all_checks()
        status_code = 200 if result["status"] == "up" else 503
        return Response(
            content=_json_dumps(result),
            media_type="application/json",
            status_code=status_code,
        )

    @router.get(
        "/health/live",
        summary="Liveness probe",
        description="Returns 200 if the process is alive. Always succeeds.",
    )
    async def liveness() -> dict[str, Any]:
        """Return liveness probe indicating the process is alive."""
        return {
            "status": "up",
            "uptime_seconds": round(time.time() - _startup_time, 1),
            "python_version": platform.python_version(),
        }

    @router.get(
        "/health/ready",
        summary="Readiness probe",
        description="Returns 200 if the service can handle traffic, 503 otherwise.",
    )
    async def readiness() -> Response:
        """Return readiness probe indicating ability to handle traffic."""
        result = run_all_checks()
        status_code = 200 if result["status"] in ("up", "degraded") else 503
        return Response(
            content=_json_dumps(result),
            media_type="application/json",
            status_code=status_code,
        )

    @router.get(
        "/health/startup",
        summary="Startup probe",
        description="Returns 200 once application initialization is complete.",
    )
    async def startup_probe() -> Response:
        """Return startup probe indicating initialization completion."""
        status_code = 200 if _startup_complete else 503
        return Response(
            content=_json_dumps({
                "status": "up" if _startup_complete else "starting",
                "startup_complete": _startup_complete,
                "uptime_seconds": round(time.time() - _startup_time, 1),
            }),
            media_type="application/json",
            status_code=status_code,
        )

    @router.get(
        "/health/dashboard",
        summary="Full health dashboard",
        description="Comprehensive status overview of all subsystems.",
    )
    async def dashboard() -> dict[str, Any]:
        """Return comprehensive status overview of all subsystems."""
        result = run_all_checks()
        result["subsystems_available"] = list(_SUBSYSTEM_CHECKS.keys())
        result["python"] = {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        }
        return result

    @router.get(
        "/health/{component_name}",
        summary="Individual component health",
        description="Check health of a specific subsystem by name.",
    )
    async def component_health(component_name: str) -> Response:
        """Check health of a specific subsystem by name."""
        result = run_single_check(component_name)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown component: {component_name}. "
                       f"Available: {', '.join(_SUBSYSTEM_CHECKS.keys())}",
            )
        status_code = 200 if result.get("status") != "down" else 503
        return Response(
            content=_json_dumps(result),
            media_type="application/json",
            status_code=status_code,
        )

    @router.get(
        "/metrics",
        summary="Prometheus metrics",
        description="Prometheus-compatible metrics in text exposition format.",
    )
    async def metrics() -> PlainTextResponse:
        """Return Prometheus-compatible metrics in text exposition format."""
        return PlainTextResponse(
            content=_get_metrics_text(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @router.get(
        "/version",
        summary="API version info",
        description="Returns current and supported API versions.",
    )
    async def version_info() -> dict[str, Any]:
        """Return current and supported API version information."""
        from spiderfoot.api.versioning import get_version_info
        from spiderfoot import __version__
        info = get_version_info()
        info["app_version"] = __version__
        return info

    @router.get(
        "/health/shutdown",
        summary="Shutdown manager status",
        description="Shows registered services and shutdown state.",
    )
    async def shutdown_status() -> dict[str, Any]:
        """Return shutdown manager status and registered services."""
        from spiderfoot.graceful_shutdown import get_shutdown_coordinator
        mgr = get_shutdown_coordinator()
        return mgr.status()


# -----------------------------------------------------------------------
# Utility
# -----------------------------------------------------------------------

def _json_dumps(obj: Any) -> str:
    """JSON serialisation without extra dependencies."""
    import json
    return json.dumps(obj, default=str)
