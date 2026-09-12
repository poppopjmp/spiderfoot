"""
Scan Progress API Router for SpiderFoot.

Exposes REST and Server-Sent Events (SSE) endpoints for real-time
scan progress monitoring.  Wraps the existing ``ScanProgressTracker``
and provides both pull-based (REST) and push-based (SSE) access
patterns suitable for modern single-page applications.

Endpoints:
  GET /api/scans/{scan_id}/progress          - Current scan progress snapshot
  GET /api/scans/{scan_id}/progress/modules  - Per-module progress breakdown
  GET /api/scans/{scan_id}/progress/history  - Historical progress snapshots
  GET /api/scans/{scan_id}/progress/stream   - SSE stream of progress events
  POST /api/scans/{scan_id}/progress/start   - Create/start a progress tracker
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any, AsyncGenerator

log = logging.getLogger("spiderfoot.api.scan_progress")

try:
    from fastapi import APIRouter, Depends, HTTPException, Request
    from fastapi.responses import StreamingResponse

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    from spiderfoot.scan.scan_progress import (
        ModuleProgress,
        ModuleStatus,
        ProgressSnapshot,
        ScanProgressTracker,
    )

    HAS_TRACKER = True
except ImportError:
    HAS_TRACKER = False


# -----------------------------------------------------------------------
# In-memory tracker registry  (scan_id -> tracker)
# -----------------------------------------------------------------------

_trackers: dict[str, ScanProgressTracker] = {}
_lock = threading.Lock()


def register_tracker(scan_id: str, tracker: ScanProgressTracker) -> None:
    """Register a progress tracker for a running scan."""
    with _lock:
        _trackers[scan_id] = tracker
    log.info("Tracker registered for scan %s", scan_id)


def unregister_tracker(scan_id: str) -> ScanProgressTracker | None:
    """Remove and return the tracker for a completed/cancelled scan."""
    with _lock:
        return _trackers.pop(scan_id, None)


def get_tracker(scan_id: str) -> ScanProgressTracker | None:
    """Look up a tracker by scan ID.  Returns ``None`` if not found."""
    with _lock:
        return _trackers.get(scan_id)


def list_tracked_scans() -> list[str]:
    """Return IDs of all scans currently being tracked."""
    with _lock:
        return list(_trackers.keys())


# -----------------------------------------------------------------------
# Redis fallback (cross-process progress)
# -----------------------------------------------------------------------
#
# _trackers above only ever gets populated in the *same process* that
# calls register_tracker() — but scans run inside sf-celery-worker /
# sf-celery-worker-active containers, while this router runs inside
# sf-api. Those are separate processes, so _trackers is permanently
# empty here regardless of what the worker does. spiderfoot.tasks.scan
# pushes real progress into Redis (key "sf:scan:progress:{scan_id}",
# written by update_scan_progress()) specifically because Redis is the
# one thing both sides can actually reach. This builds a ProgressSnapshot
# from that shared data as a fallback when no in-memory tracker exists.

def _redis_snapshot(scan_id: str) -> "ProgressSnapshot | None":
    """Build a ProgressSnapshot from Redis progress data, if any exists."""
    if not HAS_TRACKER:
        return None
    import os
    try:
        import redis as redis_lib
        redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
        r = redis_lib.from_url(redis_url, decode_responses=True)
        data = r.hgetall(f"sf:scan:progress:{scan_id}")
    except Exception as e:
        log.debug("Redis progress lookup failed for %s: %s", scan_id, e)
        return None

    if not data:
        return None

    def _f(key: str, default: float = 0.0) -> float:
        try:
            return float(data.get(key, default))
        except (TypeError, ValueError):
            return default

    updated_at = _f("updated_at", time.time())
    modules_completed = int(_f("modules_completed"))
    modules_total = int(_f("modules_total"))
    events_total = int(_f("events_produced"))
    progress_pct = _f("progress")

    return ProgressSnapshot(
        timestamp=updated_at,
        overall_pct=progress_pct,
        modules_completed=modules_completed,
        modules_total=modules_total,
        events_total=events_total,
        throughput_eps=0.0,
        eta_seconds=None,
    )


def clear_trackers() -> int:
    """Remove all trackers.  Returns the count removed."""
    with _lock:
        count = len(_trackers)
        _trackers.clear()
    return count


# -----------------------------------------------------------------------
# SSE helpers
# -----------------------------------------------------------------------

_DEFAULT_SSE_INTERVAL = 2.0  # seconds between SSE pushes
_MAX_SSE_DURATION = 3600  # max 1 hour per SSE connection


async def _sse_generator(
    scan_id: str,
    interval: float = _DEFAULT_SSE_INTERVAL,
    timeout: float = _MAX_SSE_DURATION,
):
    """Async generator yielding SSE-formatted progress events.

    Sends ``progress`` events every *interval* seconds and a
    ``complete`` event when the scan finishes.  The stream closes
    after *timeout* seconds or when the tracker is unregistered.
    """
    start = time.monotonic()
    last_pct = -1.0

    while (time.monotonic() - start) < timeout:
        tracker = get_tracker(scan_id)
        if tracker is not None:
            snapshot = tracker.get_snapshot()
        else:
            # No in-memory tracker (the normal case — scans run in a
            # separate worker process) — fall back to Redis, which the
            # worker actually writes to. See _redis_snapshot() above.
            snapshot = _redis_snapshot(scan_id)
            if snapshot is None:
                # Nothing in-memory, nothing in Redis - never tracked at all
                yield _sse_event("complete", {"scan_id": scan_id, "reason": "tracker_removed"})
                return

        data = snapshot.to_dict()
        data["scan_id"] = scan_id

        # Always send if progress changed or on first tick
        pct = snapshot.overall_pct
        if pct != last_pct:
            yield _sse_event("progress", data)
            last_pct = pct

            # Check for completion
            if pct >= 100.0:
                yield _sse_event("complete", data)
                return
        else:
            # Send heartbeat periodically even without progress change
            yield _sse_event("heartbeat", {"scan_id": scan_id, "timestamp": time.time()})

        await asyncio.sleep(interval)

    # Timed out
    yield _sse_event("timeout", {"scan_id": scan_id, "duration_seconds": timeout})


def _sse_event(event_type: str, data: Any) -> str:
    """Format a Server-Sent Event string."""
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


# -----------------------------------------------------------------------
# FastAPI router
# -----------------------------------------------------------------------

if not HAS_FASTAPI:

    class _StubRouter:
        """Stub router for when dependencies are unavailable."""
        pass

    router = _StubRouter()
else:
    from ..dependencies import optional_auth, SafeId

    _auth_dep = Depends(optional_auth)

    router = APIRouter()

    @router.get(
        "/scans/{scan_id}/progress",
        summary="Get current scan progress",
        description=(
            "Returns a point-in-time progress snapshot including "
            "overall percentage, ETA, throughput, and module counts."
        ),
    )
    async def get_progress(scan_id: SafeId, _auth: str | None = _auth_dep) -> dict:
        """Return the current progress snapshot for a scan."""
        tracker = get_tracker(scan_id)
        if tracker is not None:
            snapshot = tracker.get_snapshot()
            data = snapshot.to_dict()
            data["scan_id"] = scan_id
            data["running_modules"] = tracker.get_running_modules()
            data["failed_modules"] = tracker.get_failed_modules()
            data["pending_modules"] = tracker.get_pending_modules()
            return data

        # No in-memory tracker (normal — scans run in a separate worker
        # process) — fall back to Redis. Per-module breakdown isn't
        # available from Redis, so those lists come back empty rather
        # than fabricated.
        snapshot = _redis_snapshot(scan_id)
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail="No active tracker for this scan.",
            )
        data = snapshot.to_dict()
        data["scan_id"] = scan_id
        data["running_modules"] = []
        data["failed_modules"] = []
        data["pending_modules"] = []
        return data

    @router.get(
        "/scans/{scan_id}/progress/modules",
        summary="Per-module progress breakdown",
        description=(
            "Returns detailed progress for each module in the scan "
            "including status, events, and elapsed time."
        ),
    )
    async def get_module_progress(scan_id: SafeId, _auth: str | None = _auth_dep) -> dict:
        """Return per-module progress breakdown for a scan."""
        tracker = get_tracker(scan_id)
        if tracker is None:
            raise HTTPException(
                status_code=404,
                detail="No active tracker for this scan.",
            )
        modules = tracker.get_all_module_progress()
        return {
            "scan_id": scan_id,
            "modules": {
                name: mp.to_dict() for name, mp in modules.items()
            },
            "summary": {
                "total": len(modules),
                "running": sum(
                    1
                    for m in modules.values()
                    if m.status == ModuleStatus.RUNNING
                ),
                "completed": sum(
                    1
                    for m in modules.values()
                    if m.status == ModuleStatus.COMPLETED
                ),
                "failed": sum(
                    1
                    for m in modules.values()
                    if m.status == ModuleStatus.FAILED
                ),
                "pending": sum(
                    1
                    for m in modules.values()
                    if m.status == ModuleStatus.PENDING
                ),
                "skipped": sum(
                    1
                    for m in modules.values()
                    if m.status == ModuleStatus.SKIPPED
                ),
            },
        }

    @router.get(
        "/scans/{scan_id}/progress/history",
        summary="Progress snapshot history",
        description=(
            "Returns the list of recorded progress snapshots for a scan."
        ),
    )
    async def get_progress_history(scan_id: SafeId, _auth: str | None = _auth_dep) -> dict:
        """Return historical progress snapshots for a scan."""
        tracker = get_tracker(scan_id)
        if tracker is None:
            raise HTTPException(
                status_code=404,
                detail="No active tracker for this scan.",
            )
        history = tracker.get_history()
        return {
            "scan_id": scan_id,
            "snapshots": [s.to_dict() for s in history],
            "count": len(history),
        }

    @router.get(
        "/scans/{scan_id}/progress/stream",
        summary="SSE progress stream",
        description=(
            "Server-Sent Events stream of scan progress. "
            "Events: 'progress' (periodic snapshots), "
            "'complete' (scan finished), 'heartbeat', 'timeout'."
        ),
    )
    async def stream_progress(
        scan_id: SafeId,
        request: Request,
        interval: float = _DEFAULT_SSE_INTERVAL,
        _auth: str | None = _auth_dep,
    ) -> StreamingResponse:
        """Stream scan progress updates via Server-Sent Events."""
        # Accept either an in-memory tracker (same-process, e.g. local/dev)
        # or Redis-backed progress (the normal case in this deployment,
        # where scans run in a separate worker process - see
        # _redis_snapshot() above). Only reject if neither has anything.
        if get_tracker(scan_id) is None and _redis_snapshot(scan_id) is None:
            raise HTTPException(
                status_code=404,
                detail="No active tracker for this scan.",
            )

        # Clamp interval to reasonable range
        interval = max(0.5, min(interval, 30.0))

        async def event_stream() -> AsyncGenerator[str, None]:
            """Yield server-sent events for scan progress updates."""
            async for event in _sse_generator(scan_id, interval=interval):
                # Check if client disconnected
                if await request.is_disconnected():
                    return
                yield event

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post(
        "/scans/{scan_id}/progress/start",
        status_code=201,
        summary="Create a progress tracker",
        description=(
            "Initialise a new progress tracker for a scan. "
            "Typically called automatically when a scan starts."
        ),
    )
    async def create_tracker(scan_id: SafeId, modules: list[str] | None = None, _auth: str | None = _auth_dep) -> dict:
        """Create and start a new progress tracker for a scan."""
        if not HAS_TRACKER:
            raise HTTPException(
                status_code=501,
                detail="ScanProgressTracker not available.",
            )

        existing = get_tracker(scan_id)
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Tracker already exists for this scan.",
            )

        tracker = ScanProgressTracker(scan_id=scan_id)
        if modules:
            tracker.register_modules(modules)
        tracker.start()
        register_tracker(scan_id, tracker)

        return {
            "scan_id": scan_id,
            "modules_registered": len(modules) if modules else 0,
            "status": "tracking",
        }

    @router.get(
        "/scans/progress/active",
        summary="List actively tracked scans",
        description="Returns IDs of all scans with active progress trackers.",
    )
    async def list_active_trackers(_auth: str | None = _auth_dep) -> dict:
        """List all scans with active progress trackers."""
        scan_ids = list_tracked_scans()
        summaries = []
        for sid in scan_ids:
            tracker = get_tracker(sid)
            if tracker:
                snap = tracker.get_snapshot()
                summaries.append(
                    {
                        "scan_id": sid,
                        "overall_pct": round(snap.overall_pct, 2),
                        "modules_total": snap.modules_total,
                        "modules_completed": snap.modules_completed,
                    }
                )
        return {"active_scans": summaries, "count": len(summaries)}
