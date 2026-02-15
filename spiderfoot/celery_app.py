# -*- coding: utf-8 -*-
# =============================================================================
# SpiderFoot — Celery Application Configuration
# =============================================================================
# Central Celery app instance shared by API, workers, and beat scheduler.
#
# Architecture:
#   - Broker:  Redis (same instance used for caching/eventbus)
#   - Backend: Redis (task results + state)
#   - Queues:  scan, report, export, agents, default
#   - Workers: scanner (concurrency=per-scan threads), reporter, generic
#
# Usage:
#   from spiderfoot.celery_app import celery_app
#   celery_app.send_task("spiderfoot.tasks.scan.run_scan", args=[...])
#
# CLI:
#   celery -A spiderfoot.celery_app worker -Q scan -c 3 --hostname=scanner@%h
#   celery -A spiderfoot.celery_app beat --scheduler celery.beat:PersistentScheduler
#   celery -A spiderfoot.celery_app flower --port=5555
# =============================================================================

from __future__ import annotations

import logging
import os

from celery import Celery, signals
from kombu import Exchange, Queue

logger = logging.getLogger("sf.celery")

# ---------------------------------------------------------------------------
# Broker / backend URLs (default to local Redis)
# ---------------------------------------------------------------------------
_REDIS_URL = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
_CELERY_BROKER = os.environ.get("SF_CELERY_BROKER_URL", _REDIS_URL)
_CELERY_BACKEND = os.environ.get("SF_CELERY_RESULT_BACKEND", _REDIS_URL)

# ---------------------------------------------------------------------------
# Celery app instance
# ---------------------------------------------------------------------------
celery_app = Celery(
    "spiderfoot",
    broker=_CELERY_BROKER,
    backend=_CELERY_BACKEND,
)

# ---------------------------------------------------------------------------
# Exchanges & Queues
# ---------------------------------------------------------------------------
_default_exchange = Exchange("sf", type="direct")

celery_app.conf.task_queues = (
    Queue("default",  _default_exchange, routing_key="default"),
    Queue("scan",     _default_exchange, routing_key="scan"),
    Queue("report",   _default_exchange, routing_key="report"),
    Queue("export",   _default_exchange, routing_key="export"),
    Queue("agents",   _default_exchange, routing_key="agents"),
    Queue("monitor",  _default_exchange, routing_key="monitor"),
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "sf"
celery_app.conf.task_default_routing_key = "default"

# ---------------------------------------------------------------------------
# Automatic task routing
# ---------------------------------------------------------------------------
celery_app.conf.task_routes = {
    "spiderfoot.tasks.scan.*":    {"queue": "scan"},
    "spiderfoot.tasks.report.*":  {"queue": "report"},
    "spiderfoot.tasks.export.*":  {"queue": "export"},
    "spiderfoot.tasks.agents.*":  {"queue": "agents"},
    "spiderfoot.tasks.monitor.*": {"queue": "monitor"},
}

# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------
celery_app.conf.accept_content = ["json", "msgpack"]
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"

# ---------------------------------------------------------------------------
# Result backend
# ---------------------------------------------------------------------------
celery_app.conf.result_expires = int(
    os.environ.get("SF_CELERY_RESULT_EXPIRES", 86400 * 7)  # 7 days
)
celery_app.conf.result_extended = True  # Store task name, args, kwargs

# ---------------------------------------------------------------------------
# Worker settings
# ---------------------------------------------------------------------------
celery_app.conf.worker_prefetch_multiplier = int(
    os.environ.get("SF_CELERY_PREFETCH", 1)  # 1 = fair scheduling
)
celery_app.conf.worker_max_tasks_per_child = int(
    os.environ.get("SF_CELERY_MAX_TASKS_PER_CHILD", 50)
)
celery_app.conf.worker_max_memory_per_child = int(
    os.environ.get("SF_CELERY_MAX_MEMORY_MB", 2048)  # 2 GB
) * 1024  # Convert to KB

# Scans can run for hours — don't let the broker think the task is lost
celery_app.conf.broker_transport_options = {
    "visibility_timeout": int(
        os.environ.get("SF_CELERY_VISIBILITY_TIMEOUT", 86400)  # 24h
    ),
}

# ---------------------------------------------------------------------------
# Task execution
# ---------------------------------------------------------------------------
celery_app.conf.task_acks_late = True          # Ack after completion (crash-safe)
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.task_track_started = True      # Track STARTED state
celery_app.conf.task_time_limit = int(
    os.environ.get("SF_CELERY_TASK_TIME_LIMIT", 86400)  # 24h hard limit
)
celery_app.conf.task_soft_time_limit = int(
    os.environ.get("SF_CELERY_TASK_SOFT_TIME_LIMIT", 82800)  # 23h soft limit
)

# ---------------------------------------------------------------------------
# Beat scheduler (periodic tasks)
# ---------------------------------------------------------------------------
celery_app.conf.beat_schedule_filename = os.environ.get(
    "SF_CELERY_BEAT_SCHEDULE_FILE", "/tmp/celerybeat-schedule"
)

# Default periodic tasks (can be overridden via API)
celery_app.conf.beat_schedule = {
    # Cleanup expired task results
    "cleanup-expired-results": {
        "task": "spiderfoot.tasks.maintenance.cleanup_expired_results",
        "schedule": 3600.0,  # Every hour
        "options": {"queue": "default"},
    },
    # Health check all services
    "service-health-check": {
        "task": "spiderfoot.tasks.maintenance.service_health_check",
        "schedule": 300.0,  # Every 5 minutes
        "options": {"queue": "monitor"},
    },
}

# ---------------------------------------------------------------------------
# Task autodiscovery
# ---------------------------------------------------------------------------
celery_app.conf.include = [
    "spiderfoot.tasks.scan",
    "spiderfoot.tasks.report",
    "spiderfoot.tasks.export",
    "spiderfoot.tasks.agents",
    "spiderfoot.tasks.monitor",
    "spiderfoot.tasks.maintenance",
]

# ---------------------------------------------------------------------------
# Signals — structured logging on task lifecycle
# ---------------------------------------------------------------------------

@signals.task_prerun.connect
def _task_prerun(task_id, task, args, kwargs, **kw):
    logger.info(
        "task.started",
        extra={"task_id": task_id, "task_name": task.name},
    )


@signals.task_postrun.connect
def _task_postrun(task_id, task, retval, state, **kw):
    logger.info(
        "task.completed",
        extra={"task_id": task_id, "task_name": task.name, "state": state},
    )


@signals.task_failure.connect
def _task_failure(task_id, exception, traceback, **kw):
    logger.error(
        "task.failed",
        extra={"task_id": task_id, "error": str(exception)},
        exc_info=True,
    )


@signals.task_revoked.connect
def _task_revoked(request, terminated, signum, expired, **kw):
    logger.warning(
        "task.revoked",
        extra={
            "task_id": request.id,
            "terminated": terminated,
            "expired": expired,
        },
    )


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def get_celery_app() -> Celery:
    """Return the singleton Celery app instance."""
    return celery_app


def is_celery_available() -> bool:
    """Check if the Celery broker is reachable."""
    try:
        conn = celery_app.connection()
        conn.ensure_connection(max_retries=1, timeout=3)
        conn.close()
        return True
    except Exception:
        return False
