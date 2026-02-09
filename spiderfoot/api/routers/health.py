"""
Health Check API Router for SpiderFoot.

Exposes Kubernetes-compatible health probes and a comprehensive
service status dashboard through FastAPI endpoints.  Wires together
the existing ``HealthAggregator``, subsystem-specific checks
(EventBus, Vector.dev, module health, report storage), and
Prometheus-compatible metrics.

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
import platform
import sys
import time
from typing import Any, Dict, List, Optional

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

def _get_registry():
    """Get or create a ServiceRegistry. Returns None if unavailable."""
    try:
        from spiderfoot.service_registry import ServiceRegistry
        return ServiceRegistry()
    except Exception:
        return None


def _check_database() -> Dict[str, Any]:
    """Deep database connectivity check (executes SELECT 1)."""
    try:
        registry = _get_registry()
        if registry is None:
            return {"status": "unknown", "message": "ServiceRegistry not available"}
        data_svc = registry.get_optional("data")
        if data_svc is None:
            return {"status": "unknown", "message": "Data service not registered"}
        if not hasattr(data_svc, "dbh") or not data_svc.dbh:
            return {"status": "down", "message": "No database handle"}
        # Attempt actual query
        try:
            if hasattr(data_svc.dbh, "conn"):
                data_svc.dbh.conn.execute("SELECT 1")
            return {"status": "up"}
        except Exception as e:
            return {"status": "down", "message": f"Query failed: {e}"}
    except Exception as e:
        return {"status": "down", "message": str(e)}


def _check_eventbus() -> Dict[str, Any]:
    """EventBus health including circuit breaker and DLQ state."""
    try:
        registry = _get_registry()
        if registry is None:
            return {"status": "unknown", "message": "ServiceRegistry not available"}
        bus = registry.get_optional("event_bus")
        if bus is None:
            return {"status": "unknown", "message": "EventBus not registered"}

        # Check for ResilientEventBus with detailed health
        if hasattr(bus, "health_check"):
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Already in async context
                return {"status": "up", "message": "Resilient bus active"}

            result = asyncio.run(bus.health_check())
            return {
                "status": result.status.value if hasattr(result.status, "value") else str(result.status),
                "backend": getattr(result, "backend", "unknown"),
                "circuit_state": getattr(result, "circuit_state", "unknown"),
                "dlq_size": getattr(result, "dlq_size", 0),
            }

        # Plain bus — just check existence
        connected = getattr(bus, "is_connected", lambda: True)()
        return {
            "status": "up" if connected else "down",
            "backend": type(bus).__name__,
        }
    except Exception as e:
        return {"status": "down", "message": str(e)}


def _check_vector() -> Dict[str, Any]:
    """Vector.dev log pipeline health."""
    try:
        from spiderfoot.vector_bootstrap import VectorBootstrap
        vb = VectorBootstrap()
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


def _check_modules() -> Dict[str, Any]:
    """Module health aggregation from ModuleHealthMonitor."""
    try:
        from spiderfoot.module_health import get_health_monitor
        monitor = get_health_monitor()
        report = monitor.get_report()
        summary = report.get("summary", {})
        total = summary.get("total", 0)
        if total == 0:
            return {"status": "unknown", "message": "No modules registered"}

        healthy = summary.get("healthy", 0)
        unhealthy = summary.get("unhealthy", 0)
        stalled = summary.get("stalled", 0)

        if unhealthy > 0 or stalled > 0:
            status = "degraded" if unhealthy < total // 2 else "down"
        elif healthy < total:
            status = "degraded"
        else:
            status = "up"

        return {
            "status": status,
            "total": total,
            "healthy": healthy,
            "degraded": summary.get("degraded", 0),
            "unhealthy": unhealthy,
            "stalled": stalled,
        }
    except ImportError:
        return {"status": "unknown", "message": "ModuleHealthMonitor not available"}
    except Exception as e:
        return {"status": "down", "message": str(e)}


def _check_report_storage() -> Dict[str, Any]:
    """Report storage backend health."""
    try:
        from spiderfoot.report_storage import ReportStore, StoreConfig
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


def _check_app_config() -> Dict[str, Any]:
    """Application config validation."""
    try:
        from spiderfoot.app_config import AppConfig
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


# -----------------------------------------------------------------------
# Prometheus metrics helper
# -----------------------------------------------------------------------

def _get_metrics_text() -> str:
    """Return Prometheus exposition text."""
    try:
        from spiderfoot.metrics import get_registry
        registry = get_registry()
        return registry.expose()
    except ImportError:
        return "# spiderfoot_metrics_unavailable 1\n"
    except Exception as e:
        return f"# spiderfoot_metrics_error{{error=\"{e}\"}} 1\n"


# -----------------------------------------------------------------------
# Subsystem registry — run all checks
# -----------------------------------------------------------------------

_SUBSYSTEM_CHECKS = {
    "database": _check_database,
    "eventbus": _check_eventbus,
    "modules": _check_modules,
    "report_storage": _check_report_storage,
    "app_config": _check_app_config,
    "vector": _check_vector,
}

_startup_time = time.time()
_startup_complete = False


def run_all_checks() -> Dict[str, Any]:
    """Execute all registered subsystem checks and aggregate."""
    components: Dict[str, Any] = {}
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


def run_single_check(name: str) -> Optional[Dict[str, Any]]:
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
        pass
    router = _StubRouter()
else:
    router = APIRouter()

    @router.get(
        "/health",
        summary="Overall health check",
        description="Combined liveness and readiness. Returns 200 if healthy, 503 if degraded/down.",
    )
    async def health():
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
    async def liveness():
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
    async def readiness():
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
    async def startup_probe():
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
    async def dashboard():
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
    async def component_health(component_name: str):
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
    async def metrics():
        return PlainTextResponse(
            content=_get_metrics_text(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )


# -----------------------------------------------------------------------
# Utility
# -----------------------------------------------------------------------

def _json_dumps(obj: Any) -> str:
    """JSON serialisation without extra dependencies."""
    import json
    return json.dumps(obj, default=str)
