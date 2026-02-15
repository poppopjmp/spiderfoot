# -*- coding: utf-8 -*-
# =============================================================================
# SpiderFoot — Celery Monitor Tasks
# =============================================================================
# Subdomain monitoring, change detection, recurring scan triggers.
# =============================================================================

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any

from spiderfoot.celery_app import celery_app

logger = logging.getLogger("sf.tasks.monitor")


@celery_app.task(
    name="spiderfoot.tasks.monitor.check_subdomain_changes",
    queue="monitor",
    bind=True,
    max_retries=1,
    soft_time_limit=600,
    time_limit=900,
)
def check_subdomain_changes(
    self,
    target: str,
    scan_id: str | None = None,
    previous_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect changes in subdomains since last snapshot.

    Compares current subdomains against a stored snapshot and returns
    new, removed, and changed records. Optionally triggers a new scan
    for newly discovered subdomains.
    """
    import redis as redis_lib

    redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
    r = redis_lib.from_url(redis_url)
    snapshot_key = f"sf:monitor:subdomains:{hashlib.sha256(target.encode()).hexdigest()}"

    # Load previous snapshot from Redis if not provided
    if previous_snapshot is None:
        stored = r.get(snapshot_key)
        if stored:
            previous_snapshot = json.loads(stored)
        else:
            previous_snapshot = {"subdomains": [], "timestamp": 0}

    previous_set = set(previous_snapshot.get("subdomains", []))

    # Fetch current subdomains via a lightweight scan
    # For now, we use the database to look up known subdomains
    current_subdomains = _get_current_subdomains(target)
    current_set = set(current_subdomains)

    new_subdomains = sorted(current_set - previous_set)
    removed_subdomains = sorted(previous_set - current_set)

    # Store new snapshot
    snapshot = {
        "subdomains": sorted(current_set),
        "timestamp": time.time(),
        "target": target,
    }
    r.set(snapshot_key, json.dumps(snapshot), ex=86400 * 30)  # 30 day TTL

    changes = {
        "target": target,
        "new": new_subdomains,
        "removed": removed_subdomains,
        "total_current": len(current_set),
        "total_previous": len(previous_set),
        "has_changes": bool(new_subdomains or removed_subdomains),
    }

    if new_subdomains:
        logger.info(
            "monitor.subdomain_changes",
            extra={
                "target": target,
                "new_count": len(new_subdomains),
                "removed_count": len(removed_subdomains),
            },
        )

    return changes


@celery_app.task(
    name="spiderfoot.tasks.monitor.trigger_recurring_scans",
    queue="monitor",
    ignore_result=True,
)
def trigger_recurring_scans() -> dict[str, Any]:
    """Check for recurring scan schedules and trigger due scans.

    Queries the recurring scan configuration and submits scan tasks
    for any that are past their next_run time.
    """
    from spiderfoot.tasks.scan import run_scan

    import redis as redis_lib

    redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
    r = redis_lib.from_url(redis_url)

    schedules_raw = r.smembers("sf:recurring:schedules")
    triggered = 0

    for schedule_bytes in schedules_raw:
        try:
            schedule = json.loads(schedule_bytes)
            next_run = schedule.get("next_run", 0)

            if time.time() >= next_run:
                run_scan.apply_async(
                    kwargs={
                        "scan_name": f"Recurring: {schedule.get('target', 'unknown')}",
                        "scan_target": schedule["target"],
                        "module_list": schedule.get("modules", []),
                        "type_list": schedule.get("types", []),
                        "global_opts": schedule.get("options", {}),
                    },
                    queue="scan",
                )
                triggered += 1

                # Update next_run
                interval = schedule.get("interval_seconds", 86400)
                schedule["next_run"] = time.time() + interval
                schedule["last_run"] = time.time()

                r.srem("sf:recurring:schedules", schedule_bytes)
                r.sadd("sf:recurring:schedules", json.dumps(schedule))

                logger.info(
                    "monitor.recurring_triggered",
                    extra={"target": schedule.get("target"), "next_run": schedule["next_run"]},
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"monitor.invalid_schedule: {e}")

    return {"triggered": triggered}


def _get_current_subdomains(target: str) -> list[str]:
    """Retrieve current known subdomains from the database.

    This queries the SpiderFoot database for all INTERNET_NAME events
    associated with the target.
    """
    try:
        from spiderfoot.db import SpiderFootDb

        dbh = SpiderFootDb({})
        # Query for INTERNET_NAME type events for this target
        results = dbh.search(
            criteria={"type": "INTERNET_NAME"},
            filterFp=True,
        )
        subdomains = []
        for row in results:
            if isinstance(row, dict):
                data = row.get("data", "")
            else:
                data = row[1] if len(row) > 1 else ""
            if data and target in str(data):
                subdomains.append(str(data).strip().lower())
        return subdomains
    except Exception as e:
        logger.warning(f"monitor.subdomain_query_failed: {e}")
        return []
