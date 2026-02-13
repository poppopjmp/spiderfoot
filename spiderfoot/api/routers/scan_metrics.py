"""Scan metrics API router and Prometheus endpoint.

Provides /metrics for Prometheus scraping and JSON metrics API
for the Grafana scan dashboard.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from spiderfoot.scan_metrics import (
    get_metrics,
    get_prometheus_text,
    reset_metrics,
)

logger = logging.getLogger("spiderfoot.api.scan_metrics")

router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse, tags=["metrics"])
async def prometheus_metrics():
    """Prometheus text exposition format metrics endpoint.

    Configure Prometheus to scrape this endpoint:
    ```yaml
    scrape_configs:
      - job_name: 'spiderfoot'
        static_configs:
          - targets: ['spiderfoot-api:5001']
        metrics_path: /api/metrics
    ```
    """
    return get_prometheus_text()


@router.get("/scan-metrics", tags=["metrics"])
async def scan_metrics_json():
    """Get scan metrics in JSON format for dashboards."""
    metrics = get_metrics()
    return {
        "counters": {
            "scans_started": metrics["sf_scans_started_total"],
            "scans_completed": metrics["sf_scans_completed_total"],
            "scans_failed": metrics["sf_scans_failed_total"],
            "scans_aborted": metrics["sf_scans_aborted_total"],
            "events_produced": metrics["sf_events_produced_total"],
            "modules_executed": metrics["sf_modules_executed_total"],
        },
        "gauges": {
            "active_scans": metrics["sf_scans_active"],
            "queued_scans": metrics["sf_scans_queued"],
            "scan_status": metrics["sf_scan_status_counts"],
        },
        "distributions": {
            "scan_durations": _summarize_list(metrics["sf_scan_duration_seconds"]),
            "events_per_scan": _summarize_list(metrics["sf_events_per_scan"]),
        },
        "breakdowns": {
            "events_by_type": dict(
                sorted(metrics["sf_event_type_counts"].items(),
                       key=lambda x: x[1], reverse=True)[:20]
            ),
            "events_by_module": dict(
                sorted(metrics["sf_module_events"].items(),
                       key=lambda x: x[1], reverse=True)[:20]
            ),
        },
    }


@router.post("/scan-metrics/reset", tags=["metrics"])
async def reset_scan_metrics():
    """Reset all scan metrics counters."""
    reset_metrics()
    logger.info("Scan metrics reset")
    return {"status": "reset"}


def _summarize_list(values: list) -> dict:
    """Summarize a list of numeric values."""
    if not values:
        return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p90": 0, "p99": 0}
    nums = sorted(values) if isinstance(values[0], (int, float)) else []
    if not nums:
        return {"count": len(values)}
    n = len(nums)
    return {
        "count": n,
        "min": round(nums[0], 2),
        "max": round(nums[-1], 2),
        "avg": round(sum(nums) / n, 2),
        "p50": round(nums[min(int(n * 0.5), n - 1)], 2),
        "p90": round(nums[min(int(n * 0.9), n - 1)], 2),
        "p99": round(nums[min(int(n * 0.99), n - 1)], 2),
    }
