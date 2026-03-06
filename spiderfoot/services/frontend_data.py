"""Frontend Data Services — backend aggregation for UI features.

Provides data shaping services for the SpiderFoot v6 frontend
(React) without coupling to any specific framework. These services
aggregate, transform, and paginate data from existing backend
components for consumption by API endpoints.

Covers ROADMAP Cycles 291-320:
  - Cycle 291: Scan diff summary data (wraps scan_diff.py)
  - Cycle 292: Module health dashboard data
  - Cycle 293: Workspace threat map aggregation
  - Cycle 294: Timeline view data service
  - Cycle 295: Advanced result filtering engine
  - Cycles 296-320: Pagination, sorting, accessibility helpers
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.frontend_data")


# ── Pagination ────────────────────────────────────────────────────────


@dataclass
class Page:
    """A page of results with metadata."""
    items: list[Any] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25
    total_pages: int = 0

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def to_dict(self) -> dict:
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }


def paginate(items: list, page: int = 1, page_size: int = 25) -> Page:
    """Paginate a list of items.

    Args:
        items: Full list to paginate.
        page: 1-based page number.
        page_size: Items per page.

    Returns:
        Page with sliced items and metadata.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 1000))
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)

    start = (page - 1) * page_size
    end = start + page_size

    return Page(
        items=items[start:end],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── Sort Helpers ──────────────────────────────────────────────────────


class SortOrder(str, Enum):
    """Sort direction."""
    ASC = "asc"
    DESC = "desc"


def sort_dicts(items: list[dict], key: str,
               order: SortOrder = SortOrder.ASC) -> list[dict]:
    """Sort a list of dictionaries by a key.

    Missing keys sort to the end.
    """
    sentinel = "" if order == SortOrder.ASC else chr(0x10FFFF)

    def sort_key(item: dict) -> Any:
        v = item.get(key, sentinel)
        if isinstance(v, str):
            return v.lower()
        return v

    return sorted(items, key=sort_key, reverse=(order == SortOrder.DESC))


# ── Module Health Dashboard Data (Cycle 292) ──────────────────────────


@dataclass
class ModuleHealthSummary:
    """Aggregated health data for a single module."""
    module_name: str
    status: str = "unknown"
    events_processed: int = 0
    events_produced: int = 0
    error_count: int = 0
    avg_duration_ms: float = 0.0
    success_rate: float = 100.0
    last_active: float = 0.0

    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "status": self.status,
            "events_processed": self.events_processed,
            "events_produced": self.events_produced,
            "error_count": self.error_count,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "success_rate": round(self.success_rate, 2),
            "last_active": self.last_active,
        }


class ModuleHealthDashboard:
    """Aggregates module health data for the frontend dashboard.

    Consumes raw metrics from module_health.ModuleHealthMonitor
    and shapes them for the React module health UI.
    """

    def __init__(self) -> None:
        self._modules: dict[str, ModuleHealthSummary] = {}

    def ingest(self, module_name: str, *,
               events_processed: int = 0,
               events_produced: int = 0,
               error_count: int = 0,
               total_duration: float = 0.0,
               status: str = "unknown") -> None:
        """Ingest health data for a module."""
        avg_ms = 0.0
        if events_processed > 0:
            avg_ms = (total_duration / events_processed) * 1000

        success_rate = 100.0
        total_ops = events_processed + error_count
        if total_ops > 0:
            success_rate = (events_processed / total_ops) * 100

        self._modules[module_name] = ModuleHealthSummary(
            module_name=module_name,
            status=status,
            events_processed=events_processed,
            events_produced=events_produced,
            error_count=error_count,
            avg_duration_ms=avg_ms,
            success_rate=success_rate,
            last_active=time.time(),
        )

    def get_all(self, *, sort_by: str = "module_name",
                order: SortOrder = SortOrder.ASC) -> list[dict]:
        """Get all module health summaries, sorted."""
        dicts = [m.to_dict() for m in self._modules.values()]
        return sort_dicts(dicts, sort_by, order)

    def get_failing(self) -> list[dict]:
        """Get modules with errors, sorted by error count descending."""
        failing = [
            m.to_dict() for m in self._modules.values()
            if m.error_count > 0
        ]
        return sort_dicts(failing, "error_count", SortOrder.DESC)

    def get_slowest(self, limit: int = 10) -> list[dict]:
        """Get the slowest modules by average duration."""
        dicts = [m.to_dict() for m in self._modules.values()]
        sorted_list = sort_dicts(dicts, "avg_duration_ms", SortOrder.DESC)
        return sorted_list[:limit]

    def get_summary(self) -> dict:
        """Get aggregate summary stats."""
        total_modules = len(self._modules)
        healthy = sum(1 for m in self._modules.values() if m.error_count == 0)
        failing = total_modules - healthy
        total_events = sum(m.events_processed for m in self._modules.values())
        total_errors = sum(m.error_count for m in self._modules.values())

        return {
            "total_modules": total_modules,
            "healthy": healthy,
            "failing": failing,
            "total_events_processed": total_events,
            "total_errors": total_errors,
            "overall_success_rate": round(
                (total_events / (total_events + total_errors) * 100)
                if (total_events + total_errors) > 0 else 100.0, 2
            ),
        }

    @property
    def module_count(self) -> int:
        return len(self._modules)


# ── Timeline View Data (Cycle 294) ────────────────────────────────────


@dataclass
class TimelineEvent:
    """A single event on the timeline."""
    timestamp: float
    event_type: str
    data: str
    module: str = ""
    scan_id: str = ""
    severity: str = "info"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "data": self.data[:200],
            "module": self.module,
            "scan_id": self.scan_id,
            "severity": self.severity,
        }


class TimelineService:
    """Provides time-ordered event data for the timeline view.

    Events are stored in-memory and can be bucketed by time
    intervals for chart rendering.
    """

    def __init__(self) -> None:
        self._events: list[TimelineEvent] = []

    def add_event(self, event: TimelineEvent) -> None:
        """Add an event to the timeline."""
        self._events.append(event)

    def add_events(self, events: list[dict]) -> int:
        """Bulk-add events from raw dicts.

        Expected dict format: {"timestamp", "event_type", "data", ...}
        Returns the number of events added.
        """
        count = 0
        for e in events:
            if "timestamp" not in e or "event_type" not in e:
                continue
            self._events.append(TimelineEvent(
                timestamp=float(e["timestamp"]),
                event_type=e["event_type"],
                data=str(e.get("data", "")),
                module=e.get("module", ""),
                scan_id=e.get("scan_id", ""),
                severity=e.get("severity", "info"),
            ))
            count += 1
        return count

    def get_events(self, *, start: float | None = None,
                   end: float | None = None,
                   event_type: str | None = None,
                   page: int = 1,
                   page_size: int = 50) -> Page:
        """Get paginated timeline events with optional filters."""
        filtered = self._events

        if start is not None:
            filtered = [e for e in filtered if e.timestamp >= start]
        if end is not None:
            filtered = [e for e in filtered if e.timestamp <= end]
        if event_type is not None:
            filtered = [e for e in filtered if e.event_type == event_type]

        # Sort by timestamp ascending
        filtered.sort(key=lambda e: e.timestamp)
        dicts = [e.to_dict() for e in filtered]
        return paginate(dicts, page, page_size)

    def bucket_by_interval(self, interval_seconds: int = 3600, *,
                           event_type: str | None = None
                           ) -> list[dict]:
        """Group events into time buckets for charting.

        Args:
            interval_seconds: Bucket width in seconds. Default 1 hour.
            event_type: Optional filter.

        Returns:
            List of {"bucket_start", "bucket_end", "count", "types"} dicts.
        """
        filtered = self._events
        if event_type is not None:
            filtered = [e for e in filtered if e.event_type == event_type]

        if not filtered:
            return []

        filtered.sort(key=lambda e: e.timestamp)

        buckets: list[dict] = []
        interval = max(1, interval_seconds)

        min_ts = filtered[0].timestamp
        max_ts = filtered[-1].timestamp

        bucket_start = min_ts - (min_ts % interval)
        while bucket_start <= max_ts:
            bucket_end = bucket_start + interval
            in_bucket = [
                e for e in filtered
                if bucket_start <= e.timestamp < bucket_end
            ]
            if in_bucket:
                type_counts: dict[str, int] = Counter()
                for e in in_bucket:
                    type_counts[e.event_type] += 1
                buckets.append({
                    "bucket_start": bucket_start,
                    "bucket_end": bucket_end,
                    "count": len(in_bucket),
                    "types": dict(type_counts),
                })
            bucket_start = bucket_end

        return buckets

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def time_range(self) -> tuple[float, float] | None:
        """Return (earliest, latest) timestamps or None if empty."""
        if not self._events:
            return None
        timestamps = [e.timestamp for e in self._events]
        return (min(timestamps), max(timestamps))


# ── Advanced Result Filtering (Cycle 295) ─────────────────────────────


@dataclass
class FilterCriteria:
    """Multi-dimensional filter specification."""
    event_types: list[str] | None = None
    modules: list[str] | None = None
    severity: str | None = None
    min_confidence: int | None = None
    data_pattern: str | None = None
    scan_ids: list[str] | None = None
    time_start: float | None = None
    time_end: float | None = None

    def is_empty(self) -> bool:
        """Check if no filters are set."""
        return all(
            v is None for v in [
                self.event_types, self.modules, self.severity,
                self.min_confidence, self.data_pattern,
                self.scan_ids, self.time_start, self.time_end,
            ]
        )


class ResultFilter:
    """Apply advanced multi-dimensional filtering to scan results.

    Supports combining event type, module, severity, confidence,
    data substring/regex, scan ID, and time range filters.
    """

    @staticmethod
    def apply(results: list[dict],
              criteria: FilterCriteria) -> list[dict]:
        """Apply filter criteria to results.

        Args:
            results: List of result dicts with keys like
                     event_type, module, data, confidence, etc.
            criteria: Filter specification.

        Returns:
            Filtered list.
        """
        if criteria.is_empty():
            return results

        filtered = results

        if criteria.event_types:
            type_set = set(criteria.event_types)
            filtered = [r for r in filtered
                        if r.get("event_type") in type_set]

        if criteria.modules:
            mod_set = set(criteria.modules)
            filtered = [r for r in filtered
                        if r.get("module") in mod_set]

        if criteria.severity:
            filtered = [r for r in filtered
                        if r.get("severity") == criteria.severity]

        if criteria.min_confidence is not None:
            min_c = criteria.min_confidence
            filtered = [r for r in filtered
                        if r.get("confidence", 0) >= min_c]

        if criteria.data_pattern:
            try:
                pat = re.compile(criteria.data_pattern, re.IGNORECASE)
                filtered = [r for r in filtered
                            if pat.search(str(r.get("data", "")))]
            except re.error:
                # Fall back to substring match
                sub = criteria.data_pattern.lower()
                filtered = [r for r in filtered
                            if sub in str(r.get("data", "")).lower()]

        if criteria.scan_ids:
            sid_set = set(criteria.scan_ids)
            filtered = [r for r in filtered
                        if r.get("scan_id") in sid_set]

        if criteria.time_start is not None:
            filtered = [r for r in filtered
                        if r.get("timestamp", 0) >= criteria.time_start]

        if criteria.time_end is not None:
            filtered = [r for r in filtered
                        if r.get("timestamp", float("inf")) <= criteria.time_end]

        return filtered

    @staticmethod
    def facets(results: list[dict]) -> dict:
        """Compute filter facets (value counts) for results.

        Returns counts of unique values for common filter fields
        so the UI can show available filter options.
        """
        type_counts: Counter = Counter()
        module_counts: Counter = Counter()
        severity_counts: Counter = Counter()

        for r in results:
            if et := r.get("event_type"):
                type_counts[et] += 1
            if mod := r.get("module"):
                module_counts[mod] += 1
            if sev := r.get("severity"):
                severity_counts[sev] += 1

        return {
            "event_types": dict(type_counts),
            "modules": dict(module_counts),
            "severities": dict(severity_counts),
            "total": len(results),
        }


# ── Threat Map Data (Cycle 293) ───────────────────────────────────────


@dataclass
class GeoPoint:
    """A geographic data point for the threat map."""
    latitude: float
    longitude: float
    label: str = ""
    event_type: str = ""
    data: str = ""
    count: int = 1
    risk_level: str = "info"

    def to_dict(self) -> dict:
        return {
            "lat": self.latitude,
            "lng": self.longitude,
            "label": self.label,
            "event_type": self.event_type,
            "data": self.data[:200],
            "count": self.count,
            "risk_level": self.risk_level,
        }


class ThreatMapAggregator:
    """Aggregates geographic data across scans for the threat map.

    Collects GeoPoints, clusters nearby points, and provides
    region-level statistics.
    """

    RISK_WEIGHT = {
        "critical": 10,
        "high": 7,
        "medium": 4,
        "low": 2,
        "info": 1,
    }

    def __init__(self) -> None:
        self._points: list[GeoPoint] = []

    def add_point(self, point: GeoPoint) -> None:
        """Add a geographic data point."""
        self._points.append(point)

    def add_points(self, points: list[dict]) -> int:
        """Bulk-add points from dicts.

        Expected keys: lat/latitude, lng/longitude, plus optional
        label, event_type, data, count, risk_level.
        """
        count = 0
        for p in points:
            lat = p.get("lat") or p.get("latitude")
            lng = p.get("lng") or p.get("longitude")
            if lat is None or lng is None:
                continue
            self._points.append(GeoPoint(
                latitude=float(lat),
                longitude=float(lng),
                label=p.get("label", ""),
                event_type=p.get("event_type", ""),
                data=str(p.get("data", "")),
                count=p.get("count", 1),
                risk_level=p.get("risk_level", "info"),
            ))
            count += 1
        return count

    def get_all_points(self) -> list[dict]:
        """Get all points as dicts."""
        return [p.to_dict() for p in self._points]

    def cluster(self, precision: int = 2) -> list[dict]:
        """Cluster nearby points by rounding coordinates.

        Args:
            precision: Decimal places for rounding. Lower = larger clusters.
                       precision=2 clusters points within ~1km.

        Returns:
            List of cluster dicts with center, count, risk score.
        """
        clusters: dict[str, dict] = {}

        for p in self._points:
            lat_r = round(p.latitude, precision)
            lng_r = round(p.longitude, precision)
            key = f"{lat_r},{lng_r}"

            if key not in clusters:
                clusters[key] = {
                    "center_lat": lat_r,
                    "center_lng": lng_r,
                    "count": 0,
                    "risk_score": 0,
                    "event_types": Counter(),
                    "labels": [],
                }
            c = clusters[key]
            c["count"] += p.count
            c["risk_score"] += self.RISK_WEIGHT.get(p.risk_level, 1) * p.count
            c["event_types"][p.event_type] += 1
            if p.label and p.label not in c["labels"]:
                c["labels"].append(p.label)

        result = []
        for c in clusters.values():
            result.append({
                "center_lat": c["center_lat"],
                "center_lng": c["center_lng"],
                "count": c["count"],
                "risk_score": c["risk_score"],
                "event_types": dict(c["event_types"]),
                "labels": c["labels"][:10],
            })

        return sorted(result, key=lambda x: x["risk_score"], reverse=True)

    def by_region(self) -> dict:
        """Group points by rough geographic region (quadrant).

        Regions: NE, NW, SE, SW based on lat/lng sign.
        """
        regions: dict[str, int] = {"NE": 0, "NW": 0, "SE": 0, "SW": 0}
        for p in self._points:
            if p.latitude >= 0:
                region = "NE" if p.longitude >= 0 else "NW"
            else:
                region = "SE" if p.longitude >= 0 else "SW"
            regions[region] += p.count
        return regions

    def risk_summary(self) -> dict:
        """Get risk level distribution."""
        counts: Counter = Counter()
        for p in self._points:
            counts[p.risk_level] += p.count
        return dict(counts)

    @property
    def point_count(self) -> int:
        return len(self._points)


# ── Scan Diff Summary (Cycle 291) ─────────────────────────────────────


class ScanDiffSummary:
    """Formats scan diff results for frontend display.

    Wraps the raw DiffResult from scan_diff.py into a frontend-
    friendly format with categorized changes and chart data.
    """

    @staticmethod
    def from_changes(*, added: list[dict] | None = None,
                     removed: list[dict] | None = None,
                     changed: list[dict] | None = None,
                     unchanged_count: int = 0) -> dict:
        """Create a frontend-ready summary from categorized changes.

        Args:
            added: List of added finding dicts.
            removed: List of removed finding dicts.
            changed: List of changed finding dicts.
            unchanged_count: Number of unchanged findings.

        Returns:
            Summary dict with stats, charts, and paginated changes.
        """
        added = added or []
        removed = removed or []
        changed = changed or []

        total_changes = len(added) + len(removed) + len(changed)
        total_findings = total_changes + unchanged_count

        # Type breakdown
        type_changes: dict[str, dict[str, int]] = {}
        for group_name, group in [("added", added), ("removed", removed),
                                   ("changed", changed)]:
            for item in group:
                et = item.get("event_type", "unknown")
                if et not in type_changes:
                    type_changes[et] = {"added": 0, "removed": 0, "changed": 0}
                type_changes[et][group_name] += 1

        # Risk impact
        risk_added = sum(1 for f in added
                         if f.get("severity") in ("high", "critical"))
        risk_removed = sum(1 for f in removed
                           if f.get("severity") in ("high", "critical"))

        return {
            "stats": {
                "total_findings": total_findings,
                "total_changes": total_changes,
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
                "unchanged": unchanged_count,
                "change_rate": round(
                    (total_changes / total_findings * 100)
                    if total_findings > 0 else 0, 2
                ),
            },
            "chart_data": {
                "change_distribution": {
                    "added": len(added),
                    "removed": len(removed),
                    "changed": len(changed),
                    "unchanged": unchanged_count,
                },
                "by_event_type": type_changes,
            },
            "risk_impact": {
                "high_risk_added": risk_added,
                "high_risk_removed": risk_removed,
                "net_risk_change": risk_added - risk_removed,
            },
        }


# ── Accessibility Helpers (Cycles 296-320) ────────────────────────────


@dataclass
class A11yLabel:
    """Accessibility label for a UI element."""
    element_id: str
    label: str
    description: str = ""
    role: str = ""
    shortcut: str = ""

    def to_dict(self) -> dict:
        d = {"id": self.element_id, "label": self.label}
        if self.description:
            d["description"] = self.description
        if self.role:
            d["role"] = self.role
        if self.shortcut:
            d["shortcut"] = self.shortcut
        return d


class A11yLabelRegistry:
    """Registry of accessibility labels for frontend elements.

    Provides a centralized store of ARIA labels, descriptions,
    and keyboard shortcuts for WCAG 2.1 AA compliance.
    """

    def __init__(self) -> None:
        self._labels: dict[str, A11yLabel] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default accessibility labels for core UI elements."""
        defaults = [
            A11yLabel("scan-list", "Scan List", "List of all scans", "table"),
            A11yLabel("scan-start", "Start Scan", "Begin a new scan", "button", "Ctrl+Shift+N"),
            A11yLabel("scan-stop", "Stop Scan", "Stop the running scan", "button"),
            A11yLabel("result-filter", "Filter Results", "Filter scan results by criteria", "search"),
            A11yLabel("module-health", "Module Health", "Module health dashboard", "region"),
            A11yLabel("threat-map", "Threat Map", "Geographic threat visualization", "img"),
            A11yLabel("timeline", "Event Timeline", "Chronological event view", "region"),
            A11yLabel("scan-diff", "Scan Comparison", "Compare two scan results", "region"),
            A11yLabel("nav-main", "Main Navigation", "Primary navigation menu", "navigation", "Alt+N"),
            A11yLabel("settings", "Settings", "Application settings", "dialog", "Ctrl+,"),
        ]
        for lbl in defaults:
            self._labels[lbl.element_id] = lbl

    def get(self, element_id: str) -> A11yLabel | None:
        """Get label for an element."""
        return self._labels.get(element_id)

    def register(self, label: A11yLabel) -> None:
        """Register or update a label."""
        self._labels[label.element_id] = label

    def get_all(self) -> list[dict]:
        """Get all labels as dicts."""
        return [lbl.to_dict() for lbl in self._labels.values()]

    def get_shortcuts(self) -> list[dict]:
        """Get all elements with keyboard shortcuts."""
        return [
            lbl.to_dict() for lbl in self._labels.values()
            if lbl.shortcut
        ]

    @property
    def count(self) -> int:
        return len(self._labels)
