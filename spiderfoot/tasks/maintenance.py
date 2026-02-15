# -*- coding: utf-8 -*-
# =============================================================================
# SpiderFoot — Celery Maintenance Tasks
# =============================================================================
# Periodic housekeeping: cleanup, health checks, monitoring.
# =============================================================================

from __future__ import annotations

import logging
import os
import time
from typing import Any

from spiderfoot.celery_app import celery_app

logger = logging.getLogger("sf.tasks.maintenance")


@celery_app.task(
    name="spiderfoot.tasks.maintenance.cleanup_expired_results",
    queue="default",
    ignore_result=True,
)
def cleanup_expired_results() -> dict[str, Any]:
    """Remove expired Celery task results and stale progress keys from Redis."""
    import redis as redis_lib

    redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
    r = redis_lib.from_url(redis_url)

    # Clean up stale scan progress keys (older than 48h)
    cleaned = 0
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor, match="sf:scan:progress:*", count=100)
        for key in keys:
            updated = r.hget(key, "updated_at")
            if updated:
                try:
                    age = time.time() - float(updated)
                    if age > 172800:  # 48 hours
                        r.delete(key)
                        cleaned += 1
                except (ValueError, TypeError):
                    pass
        if cursor == 0:
            break

    logger.info("maintenance.cleanup", extra={"cleaned_keys": cleaned})
    return {"cleaned_progress_keys": cleaned}


@celery_app.task(
    name="spiderfoot.tasks.maintenance.service_health_check",
    queue="monitor",
    ignore_result=True,
)
def service_health_check() -> dict[str, Any]:
    """Check health of all infrastructure services and log status."""
    import urllib.request
    import json

    services = {
        "api": os.environ.get("SF_API_URL", "http://api:8001/api/docs"),
        "tika": "http://tika:9998/tika",
        "qdrant": "http://qdrant:6333/readyz",
        "loki": "http://loki:3100/ready",
    }

    results = {}
    for name, url in services.items():
        try:
            req = urllib.request.urlopen(url, timeout=5)
            results[name] = {
                "status": "healthy",
                "code": req.getcode(),
            }
        except Exception as e:
            results[name] = {
                "status": "unhealthy",
                "error": str(e),
            }

    healthy = sum(1 for v in results.values() if v["status"] == "healthy")
    total = len(results)

    logger.info(
        "maintenance.health_check",
        extra={"healthy": healthy, "total": total, "results": results},
    )

    return {"services": results, "healthy": healthy, "total": total}


@celery_app.task(
    name="spiderfoot.tasks.maintenance.database_vacuum",
    queue="default",
    soft_time_limit=1800,
    time_limit=3600,
)
def database_vacuum(global_opts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run VACUUM ANALYZE on PostgreSQL to reclaim space and update statistics."""
    import psycopg2

    dsn = os.environ.get(
        "SF_POSTGRES_DSN",
        "postgresql://spiderfoot:changeme@postgres:5432/spiderfoot",
    )

    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("VACUUM ANALYZE;")
        cur.close()
        conn.close()

        logger.info("maintenance.vacuum_completed")
        return {"status": "completed"}

    except Exception as e:
        logger.error(f"maintenance.vacuum_failed: {e}")
        return {"status": "failed", "error": str(e)}
