# -*- coding: utf-8 -*-
# =============================================================================
# SpiderFoot — Celery Scan Tasks
# =============================================================================
# Core scan lifecycle tasks that replace BackgroundTasks / mp.Process.
#
# Each scan runs as a single Celery task on the ``scan`` queue.  The task
# wraps ``SpiderFootScanner`` — module-level threading happens *inside* the
# worker process, but the worker itself is managed by Celery (crash recovery,
# visibility timeout, result backend, state tracking).
#
# Progress updates are pushed to Redis so the API can stream them via
# WebSocket without polling the DB.
# =============================================================================

from __future__ import annotations

import logging
import multiprocessing as mp
import time
import traceback
from typing import Any

from celery import current_task, states
from celery.exceptions import SoftTimeLimitExceeded

from spiderfoot.celery_app import celery_app

logger = logging.getLogger("sf.tasks.scan")


# ---------------------------------------------------------------------------
# Scan execution task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="spiderfoot.tasks.scan.run_scan",
    bind=True,
    queue="scan",
    max_retries=0,           # Scans should not auto-retry
    acks_late=True,          # Only ack on success/failure
    track_started=True,
    reject_on_worker_lost=True,
    time_limit=86400,        # 24h hard limit
    soft_time_limit=82800,   # 23h soft limit
)
def run_scan(
    self,
    scan_name: str,
    scan_id: str,
    target_value: str,
    target_type: str,
    module_list: list[str],
    global_opts: dict[str, Any],
    *,
    engine_name: str | None = None,
) -> dict[str, Any]:
    """Run a SpiderFoot scan inside a Celery worker.

    This is the primary scan entry point — replaces ``BackgroundTasks``
    and ``mp.Process`` from the pre-Celery architecture.

    Args:
        scan_name:    Human-readable scan name.
        scan_id:      Pre-generated scan instance ID.
        target_value: The scan target (domain, IP, email, etc.).
        target_type:  Target type identifier.
        module_list:  List of module names to activate.
        global_opts:  SpiderFoot configuration dict.
        engine_name:  Optional scan engine profile name (logged).

    Returns:
        dict with scan_id, status, duration, and event count.
    """
    start_time = time.time()

    # Update Celery task meta with scan info
    self.update_state(
        state="SCANNING",
        meta={
            "scan_id": scan_id,
            "scan_name": scan_name,
            "target": target_value,
            "engine": engine_name,
            "progress": 0,
            "modules_total": len(module_list),
            "modules_completed": 0,
            "events_produced": 0,
            "started_at": start_time,
        },
    )

    logger.info(
        "scan.starting",
        extra={
            "scan_id": scan_id,
            "target": target_value,
            "modules": len(module_list),
            "engine": engine_name,
            "celery_task_id": self.request.id,
        },
    )

    try:
        # Import here to avoid circular imports at module load time
        from spiderfoot.scan_service.scanner import startSpiderFootScanner

        # Create a logging queue for the scanner subprocess
        log_queue = mp.Queue()

        # Run the scanner — this blocks until the scan completes
        scanner = startSpiderFootScanner(
            log_queue,
            scan_name,
            scan_id,
            target_value,
            target_type,
            module_list,
            global_opts,
        )

        duration = time.time() - start_time

        # Collect final stats
        result = {
            "scan_id": scan_id,
            "scan_name": scan_name,
            "target": target_value,
            "status": "completed",
            "duration_seconds": round(duration, 2),
            "engine": engine_name,
            "celery_task_id": self.request.id,
        }

        logger.info(
            "scan.completed",
            extra={
                "scan_id": scan_id,
                "duration": round(duration, 2),
            },
        )

        # Send completion notification
        try:
            from spiderfoot.notifications import notify, NotificationEvent
            notify(
                event=NotificationEvent.SCAN_COMPLETED,
                title=f"Scan Complete: {scan_name}",
                message=f"Scan '{scan_name}' targeting {target_value} completed in {round(duration, 1)}s.",
                data={"scan_id": scan_id, "target": target_value, "duration": round(duration, 1)},
            )
        except Exception as ne:
            logger.debug("Notification send failed: %s", ne)

        return result

    except SoftTimeLimitExceeded:
        duration = time.time() - start_time
        logger.warning(
            "scan.timeout",
            extra={"scan_id": scan_id, "duration": round(duration, 2)},
        )
        # Try to gracefully stop the scan via DB status update
        _abort_scan_in_db(scan_id, global_opts)
        return {
            "scan_id": scan_id,
            "status": "timeout",
            "duration_seconds": round(duration, 2),
            "error": f"Scan exceeded soft time limit ({self.soft_time_limit}s)",
        }

    except Exception as exc:
        duration = time.time() - start_time
        error_msg = f"{type(exc).__name__}: {exc}"
        tb = traceback.format_exc()

        logger.error(
            "scan.failed",
            extra={
                "scan_id": scan_id,
                "error": error_msg,
                "duration": round(duration, 2),
            },
        )

        # Mark failed in DB
        _update_scan_status(scan_id, global_opts, "ERROR-FAILED", error_msg)

        # Send failure notification
        try:
            from spiderfoot.notifications import notify, NotificationEvent
            notify(
                event=NotificationEvent.SCAN_FAILED,
                title=f"Scan Failed: {scan_name}",
                message=f"Scan '{scan_name}' targeting {target_value} failed: {error_msg}",
                data={"scan_id": scan_id, "target": target_value, "error": error_msg},
            )
        except Exception as ne:
            logger.debug("Notification send failed: %s", ne)

        # Raise so Celery marks the task as FAILURE
        raise


# ---------------------------------------------------------------------------
# Scan abort task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="spiderfoot.tasks.scan.abort_scan",
    queue="scan",
)
def abort_scan(scan_id: str, global_opts: dict[str, Any] | None = None) -> dict:
    """Request a running scan to abort.

    Sets the DB status to ``ABORT-REQUESTED`` which the scanner's
    ``waitForThreads()`` loop checks on each iteration.
    """
    logger.info("scan.abort_requested", extra={"scan_id": scan_id})
    _abort_scan_in_db(scan_id, global_opts or {})
    return {"scan_id": scan_id, "status": "abort-requested"}


# ---------------------------------------------------------------------------
# Batch / multi-scan task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="spiderfoot.tasks.scan.run_batch_scans",
    queue="scan",
)
def run_batch_scans(
    scans: list[dict[str, Any]],
) -> dict[str, Any]:
    """Submit multiple scans as individual Celery tasks.

    Each scan dict must contain: scan_name, scan_id, target_value,
    target_type, module_list, global_opts.

    Returns dict with submitted task IDs.
    """
    submitted = {}
    for scan_spec in scans:
        result = run_scan.apply_async(
            args=[
                scan_spec["scan_name"],
                scan_spec["scan_id"],
                scan_spec["target_value"],
                scan_spec["target_type"],
                scan_spec["module_list"],
                scan_spec["global_opts"],
            ],
            kwargs={"engine_name": scan_spec.get("engine_name")},
        )
        submitted[scan_spec["scan_id"]] = result.id

    logger.info(
        "scan.batch_submitted",
        extra={"count": len(submitted)},
    )

    return {"submitted": submitted, "count": len(submitted)}


# ---------------------------------------------------------------------------
# Scan progress update (called from within scanner via Redis pubsub)
# ---------------------------------------------------------------------------

@celery_app.task(
    name="spiderfoot.tasks.scan.update_progress",
    queue="scan",
    ignore_result=True,
)
def update_scan_progress(
    scan_id: str,
    progress: int,
    modules_completed: int,
    modules_total: int,
    events_produced: int,
) -> None:
    """Lightweight task to update scan progress in Redis.

    Called periodically by the scanner to push progress updates
    that the WebSocket API can broadcast to connected clients.
    """
    import redis as redis_lib
    import json
    import os

    redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
    r = redis_lib.from_url(redis_url)

    progress_data = {
        "scan_id": scan_id,
        "progress": progress,
        "modules_completed": modules_completed,
        "modules_total": modules_total,
        "events_produced": events_produced,
        "updated_at": time.time(),
    }

    # Store in Redis hash for quick lookup
    r.hset(f"sf:scan:progress:{scan_id}", mapping={
        k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        for k, v in progress_data.items()
    })
    r.expire(f"sf:scan:progress:{scan_id}", 86400)

    # Publish for WebSocket subscribers
    r.publish(f"sf:scan:events:{scan_id}", json.dumps(progress_data))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _abort_scan_in_db(scan_id: str, opts: dict) -> None:
    """Set scan status to ABORT-REQUESTED in the database."""
    try:
        from spiderfoot.db import SpiderFootDb
        dbh = SpiderFootDb(opts)
        dbh.scanInstanceSet(scan_id, status="ABORT-REQUESTED")
    except Exception as e:
        logger.error(f"Failed to set abort status for {scan_id}: {e}")


def _update_scan_status(
    scan_id: str, opts: dict, status: str, error: str = ""
) -> None:
    """Update scan status in the database."""
    try:
        from spiderfoot.db import SpiderFootDb
        dbh = SpiderFootDb(opts)
        dbh.scanInstanceSet(scan_id, status=status)
        if error:
            dbh.scanError(scan_id, error)
    except Exception as e:
        logger.error(f"Failed to update status for {scan_id}: {e}")
