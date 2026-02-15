"""Prometheus metrics for SpiderFoot scan operations.

Exposes scan-level metrics for Grafana dashboards including:
- Scan counts by status
- Scan durations
- Event counts by type
- Module execution times
- Active/queued scan gauges
"""

from __future__ import annotations

import time
import logging
from typing import Any

logger = logging.getLogger("spiderfoot.scan_metrics")

# Metric storage (in-memory, scraped by /metrics endpoint)
_metrics: dict[str, Any] = {
    # Counters
    "sf_scans_started_total": 0,
    "sf_scans_completed_total": 0,
    "sf_scans_failed_total": 0,
    "sf_scans_aborted_total": 0,
    "sf_events_produced_total": 0,
    "sf_modules_executed_total": 0,
    # Gauges
    "sf_scans_active": 0,
    "sf_scans_queued": 0,
    # Histograms (approximated as summary)
    "sf_scan_duration_seconds": [],
    "sf_module_duration_seconds": [],
    "sf_events_per_scan": [],
    # Per-module counters
    "sf_module_events": {},
    # Per-event-type counters
    "sf_event_type_counts": {},
    # Per-status counters
    "sf_scan_status_counts": {
        "RUNNING": 0,
        "FINISHED": 0,
        "FAILED": 0,
        "ABORTED": 0,
        "STARTING": 0,
    },
}


def record_scan_started(scan_id: str, target: str) -> None:
    """Record a scan start."""
    _metrics["sf_scans_started_total"] += 1
    _metrics["sf_scans_active"] += 1
    _metrics["sf_scan_status_counts"]["RUNNING"] += 1
    logger.debug("Metric: scan_started scan_id=%s target=%s", scan_id, target)


def record_scan_completed(scan_id: str, duration_seconds: float, event_count: int) -> None:
    """Record a successful scan completion."""
    _metrics["sf_scans_completed_total"] += 1
    _metrics["sf_scans_active"] = max(0, _metrics["sf_scans_active"] - 1)
    _metrics["sf_scan_status_counts"]["FINISHED"] += 1
    _metrics["sf_scan_status_counts"]["RUNNING"] = max(
        0, _metrics["sf_scan_status_counts"]["RUNNING"] - 1
    )
    _metrics["sf_scan_duration_seconds"].append(duration_seconds)
    _metrics["sf_events_per_scan"].append(event_count)
    # Cap histogram lists
    if len(_metrics["sf_scan_duration_seconds"]) > 10000:
        _metrics["sf_scan_duration_seconds"] = _metrics["sf_scan_duration_seconds"][-5000:]
    if len(_metrics["sf_events_per_scan"]) > 10000:
        _metrics["sf_events_per_scan"] = _metrics["sf_events_per_scan"][-5000:]


def record_scan_failed(scan_id: str) -> None:
    _metrics["sf_scans_failed_total"] += 1
    _metrics["sf_scans_active"] = max(0, _metrics["sf_scans_active"] - 1)
    _metrics["sf_scan_status_counts"]["FAILED"] += 1
    _metrics["sf_scan_status_counts"]["RUNNING"] = max(
        0, _metrics["sf_scan_status_counts"]["RUNNING"] - 1
    )


def record_scan_aborted(scan_id: str) -> None:
    _metrics["sf_scans_aborted_total"] += 1
    _metrics["sf_scans_active"] = max(0, _metrics["sf_scans_active"] - 1)
    _metrics["sf_scan_status_counts"]["ABORTED"] += 1
    _metrics["sf_scan_status_counts"]["RUNNING"] = max(
        0, _metrics["sf_scan_status_counts"]["RUNNING"] - 1
    )


def record_event_produced(event_type: str, module: str) -> None:
    """Record an event produced by a module."""
    _metrics["sf_events_produced_total"] += 1
    # Per-type
    if event_type not in _metrics["sf_event_type_counts"]:
        _metrics["sf_event_type_counts"][event_type] = 0
    _metrics["sf_event_type_counts"][event_type] += 1
    # Per-module
    if module not in _metrics["sf_module_events"]:
        _metrics["sf_module_events"][module] = 0
    _metrics["sf_module_events"][module] += 1


def record_module_execution(module: str, duration_seconds: float) -> None:
    """Record a module execution time."""
    _metrics["sf_modules_executed_total"] += 1
    _metrics["sf_module_duration_seconds"].append(
        {"module": module, "duration": duration_seconds}
    )
    if len(_metrics["sf_module_duration_seconds"]) > 10000:
        _metrics["sf_module_duration_seconds"] = _metrics["sf_module_duration_seconds"][-5000:]


def set_queued_scans(count: int) -> None:
    _metrics["sf_scans_queued"] = count


def get_metrics() -> dict[str, Any]:
    """Get all metrics as a dictionary."""
    return dict(_metrics)


def get_prometheus_text() -> str:
    """Format metrics in Prometheus text exposition format."""
    lines: list[str] = []

    # Counters
    lines.append("# HELP sf_scans_started_total Total number of scans started")
    lines.append("# TYPE sf_scans_started_total counter")
    lines.append(f"sf_scans_started_total {_metrics['sf_scans_started_total']}")

    lines.append("# HELP sf_scans_completed_total Total scans completed successfully")
    lines.append("# TYPE sf_scans_completed_total counter")
    lines.append(f"sf_scans_completed_total {_metrics['sf_scans_completed_total']}")

    lines.append("# HELP sf_scans_failed_total Total scans that failed")
    lines.append("# TYPE sf_scans_failed_total counter")
    lines.append(f"sf_scans_failed_total {_metrics['sf_scans_failed_total']}")

    lines.append("# HELP sf_scans_aborted_total Total scans aborted")
    lines.append("# TYPE sf_scans_aborted_total counter")
    lines.append(f"sf_scans_aborted_total {_metrics['sf_scans_aborted_total']}")

    lines.append("# HELP sf_events_produced_total Total events produced")
    lines.append("# TYPE sf_events_produced_total counter")
    lines.append(f"sf_events_produced_total {_metrics['sf_events_produced_total']}")

    lines.append("# HELP sf_modules_executed_total Total module executions")
    lines.append("# TYPE sf_modules_executed_total counter")
    lines.append(f"sf_modules_executed_total {_metrics['sf_modules_executed_total']}")

    # Gauges
    lines.append("# HELP sf_scans_active Currently running scans")
    lines.append("# TYPE sf_scans_active gauge")
    lines.append(f"sf_scans_active {_metrics['sf_scans_active']}")

    lines.append("# HELP sf_scans_queued Scans waiting in queue")
    lines.append("# TYPE sf_scans_queued gauge")
    lines.append(f"sf_scans_queued {_metrics['sf_scans_queued']}")

    # Per-status gauge
    lines.append("# HELP sf_scan_status_count Scans by status")
    lines.append("# TYPE sf_scan_status_count gauge")
    for status, count in _metrics["sf_scan_status_counts"].items():
        lines.append(f'sf_scan_status_count{{status="{status}"}} {count}')

    # Per-event-type counter
    lines.append("# HELP sf_event_type_total Events by type")
    lines.append("# TYPE sf_event_type_total counter")
    for etype, count in sorted(_metrics["sf_event_type_counts"].items()):
        lines.append(f'sf_event_type_total{{type="{etype}"}} {count}')

    # Per-module counter
    lines.append("# HELP sf_module_events_total Events produced per module")
    lines.append("# TYPE sf_module_events_total counter")
    for module, count in sorted(_metrics["sf_module_events"].items()):
        lines.append(f'sf_module_events_total{{module="{module}"}} {count}')

    # Scan duration histogram summary
    durations = _metrics["sf_scan_duration_seconds"]
    if durations:
        lines.append("# HELP sf_scan_duration_seconds Scan duration histogram")
        lines.append("# TYPE sf_scan_duration_seconds summary")
        sorted_d = sorted(durations)
        n = len(sorted_d)
        lines.append(f"sf_scan_duration_seconds_count {n}")
        lines.append(f"sf_scan_duration_seconds_sum {sum(sorted_d):.2f}")
        for q in (0.5, 0.9, 0.95, 0.99):
            idx = min(int(n * q), n - 1)
            lines.append(f'sf_scan_duration_seconds{{quantile="{q}"}} {sorted_d[idx]:.2f}')

    # Events per scan summary
    eps = _metrics["sf_events_per_scan"]
    if eps:
        lines.append("# HELP sf_events_per_scan Events per scan summary")
        lines.append("# TYPE sf_events_per_scan summary")
        sorted_e = sorted(eps)
        n = len(sorted_e)
        lines.append(f"sf_events_per_scan_count {n}")
        lines.append(f"sf_events_per_scan_sum {sum(sorted_e)}")
        for q in (0.5, 0.9, 0.99):
            idx = min(int(n * q), n - 1)
            lines.append(f'sf_events_per_scan{{quantile="{q}"}} {sorted_e[idx]}')

    lines.append("")
    return "\n".join(lines)


def reset_metrics() -> None:
    """Reset all metrics (for testing)."""
    _metrics["sf_scans_started_total"] = 0
    _metrics["sf_scans_completed_total"] = 0
    _metrics["sf_scans_failed_total"] = 0
    _metrics["sf_scans_aborted_total"] = 0
    _metrics["sf_events_produced_total"] = 0
    _metrics["sf_modules_executed_total"] = 0
    _metrics["sf_scans_active"] = 0
    _metrics["sf_scans_queued"] = 0
    _metrics["sf_scan_duration_seconds"] = []
    _metrics["sf_module_duration_seconds"] = []
    _metrics["sf_events_per_scan"] = []
    _metrics["sf_module_events"] = {}
    _metrics["sf_event_type_counts"] = {}
    _metrics["sf_scan_status_counts"] = {
        "RUNNING": 0, "FINISHED": 0, "FAILED": 0,
        "ABORTED": 0, "STARTING": 0,
    }
