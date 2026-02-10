"""Scan result aggregator for SpiderFoot.

Aggregates events from a scan into structured summaries:
- Per-type event counts and statistics
- Risk-weighted scoring across findings
- Top-N entities by occurrence
- Timeline of discovery
- Category breakdowns (ENTITY, DESCRIPTOR, DATA, etc.)
- Export-ready summary dicts

Usage::

    from spiderfoot.result_aggregator import ScanResultAggregator

    agg = ScanResultAggregator(scan_id="scan-001")
    agg.add_event("IP_ADDRESS", "192.168.1.1", "sfp_dns",
                  confidence=100, risk=30)
    agg.add_event("MALICIOUS_IPADDR", "192.168.1.1", "sfp_virustotal",
                  confidence=90, risk=80)

    summary = agg.get_summary()
    top_risky = agg.get_top_risk_events(limit=10)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, List, Optional

log = logging.getLogger("spiderfoot.result_aggregator")


@dataclass
class EventRecord:
    """Record of a single event for aggregation."""
    event_type: str
    data: str
    module: str
    confidence: int = 100
    risk: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class TypeStats:
    """Statistics for a single event type."""
    event_type: str
    count: int = 0
    unique_values: int = 0
    avg_confidence: float = 0.0
    avg_risk: float = 0.0
    max_risk: int = 0
    modules: set[str] = field(default_factory=set)
    _confidence_sum: float = 0.0
    _risk_sum: float = 0.0
    _values: set[str] = field(default_factory=set)

    def record(self, data: str, module: str, confidence: int,
               risk: int) -> None:
        self.count += 1
        self._values.add(data)
        self.unique_values = len(self._values)
        self.modules.add(module)
        self._confidence_sum += confidence
        self._risk_sum += risk
        self.avg_confidence = self._confidence_sum / self.count
        self.avg_risk = self._risk_sum / self.count
        if risk > self.max_risk:
            self.max_risk = risk

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "count": self.count,
            "unique_values": self.unique_values,
            "avg_confidence": round(self.avg_confidence, 1),
            "avg_risk": round(self.avg_risk, 1),
            "max_risk": self.max_risk,
            "modules": sorted(self.modules),
        }


class ScanResultAggregator:
    """Aggregates scan results into structured summaries."""

    def __init__(self, scan_id: str = "") -> None:
        self.scan_id = scan_id
        self.start_time = time.time()
        self._events: list[EventRecord] = []
        self._type_stats: dict[str, TypeStats] = {}
        self._module_counts: dict[str, int] = defaultdict(int)
        self._risk_events: list[EventRecord] = []
        self._category_counts: dict[str, int] = defaultdict(int)

    # Category mapping for common event type prefixes
    _CATEGORY_MAP = {
        "MALICIOUS_": "THREAT",
        "BLACKLISTED_": "THREAT",
        "VULNERABILITY_": "VULNERABILITY",
        "DEFACED_": "THREAT",
        "EMAILADDR": "IDENTITY",
        "HUMAN_NAME": "IDENTITY",
        "PERSON_NAME": "IDENTITY",
        "USERNAME": "IDENTITY",
        "PHONE_NUMBER": "IDENTITY",
        "IP_ADDRESS": "INFRASTRUCTURE",
        "IPV6_ADDRESS": "INFRASTRUCTURE",
        "INTERNET_NAME": "INFRASTRUCTURE",
        "DOMAIN_NAME": "INFRASTRUCTURE",
        "NETBLOCK_": "INFRASTRUCTURE",
        "TCP_PORT_": "INFRASTRUCTURE",
        "UDP_PORT_": "INFRASTRUCTURE",
        "SSL_CERTIFICATE_": "CERTIFICATE",
        "URL_": "WEB",
        "TARGET_WEB_": "WEB",
        "WEBSERVER_": "WEB",
        "DNS_": "DNS",
        "BGP_": "NETWORK",
        "SOCIAL_MEDIA": "SOCIAL",
        "ACCOUNT_EXTERNAL": "SOCIAL",
        "CLOUD_STORAGE_": "CLOUD",
        "PROVIDER_": "INFRASTRUCTURE",
        "GEOINFO": "GEOLOCATION",
        "COUNTRY_NAME": "GEOLOCATION",
        "PHYSICAL_": "GEOLOCATION",
    }

    def _categorize(self, event_type: str) -> str:
        """Determine the category of an event type."""
        for prefix, category in self._CATEGORY_MAP.items():
            if event_type.startswith(prefix) or event_type == prefix:
                return category
        return "OTHER"

    def add_event(self, event_type: str, data: str, module: str,
                  confidence: int = 100, risk: int = 0,
                  timestamp: float | None = None) -> None:
        """Add an event to the aggregator.

        Args:
            event_type: Event type string
            data: Event data
            module: Module that produced the event
            confidence: Confidence score 0-100
            risk: Risk score 0-100
            timestamp: Optional timestamp (defaults to now)
        """
        record = EventRecord(
            event_type=event_type,
            data=data,
            module=module,
            confidence=confidence,
            risk=risk,
            timestamp=timestamp or time.time(),
        )
        self._events.append(record)

        # Update type stats
        if event_type not in self._type_stats:
            self._type_stats[event_type] = TypeStats(event_type=event_type)
        self._type_stats[event_type].record(data, module, confidence, risk)

        # Module counts
        self._module_counts[module] += 1

        # Category counts
        category = self._categorize(event_type)
        self._category_counts[category] += 1

        # Track risky events
        if risk > 0:
            self._risk_events.append(record)

    @property
    def total_events(self) -> int:
        return len(self._events)

    @property
    def unique_types(self) -> int:
        return len(self._type_stats)

    @property
    def unique_modules(self) -> int:
        return len(self._module_counts)

    @property
    def duration(self) -> float:
        return time.time() - self.start_time

    @property
    def overall_risk_score(self) -> float:
        """Calculate a weighted risk score for the scan (0-100).

        Higher values indicate more risky findings.
        """
        if not self._risk_events:
            return 0.0

        # Weighted average: higher-risk events count more
        total_weight = 0.0
        weighted_sum = 0.0
        for evt in self._risk_events:
            weight = evt.risk / 100.0  # weight by risk itself
            weighted_sum += evt.risk * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        raw = weighted_sum / total_weight
        return min(100.0, round(raw, 1))

    def get_type_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics per event type."""
        return {
            name: stats.to_dict()
            for name, stats in sorted(self._type_stats.items())
        }

    def get_module_stats(self) -> dict[str, int]:
        """Get event counts per module."""
        return dict(sorted(
            self._module_counts.items(), key=lambda x: x[1], reverse=True
        ))

    def get_category_breakdown(self) -> dict[str, int]:
        """Get event counts per category."""
        return dict(sorted(
            self._category_counts.items(), key=lambda x: x[1], reverse=True
        ))

    def get_top_risk_events(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get the top N highest-risk events."""
        sorted_events = sorted(
            self._risk_events, key=lambda e: e.risk, reverse=True
        )
        return [
            {
                "event_type": e.event_type,
                "data": e.data[:200],  # truncate large data
                "module": e.module,
                "risk": e.risk,
                "confidence": e.confidence,
            }
            for e in sorted_events[:limit]
        ]

    def get_top_entities(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get the most frequently occurring data values."""
        value_counts: dict[str, int] = defaultdict(int)
        for evt in self._events:
            if len(evt.data) <= 200:  # skip raw/large data
                value_counts[evt.data] += 1

        return sorted(
            value_counts.items(), key=lambda x: x[1], reverse=True
        )[:limit]

    def get_timeline(self, buckets: int = 10) -> list[dict[str, Any]]:
        """Get event discovery timeline in time buckets.

        Args:
            buckets: Number of time buckets

        Returns:
            List of dicts with time range and event count
        """
        if not self._events:
            return []

        timestamps = [e.timestamp for e in self._events]
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        span = max_ts - min_ts

        if span == 0:
            return [{"start": min_ts, "end": max_ts,
                     "count": len(self._events)}]

        bucket_size = span / buckets
        timeline = []

        for i in range(buckets):
            start = min_ts + (i * bucket_size)
            end = start + bucket_size
            count = sum(
                1 for e in self._events
                if start <= e.timestamp < end or (i == buckets - 1 and e.timestamp == end)
            )
            timeline.append({
                "bucket": i,
                "start": round(start, 3),
                "end": round(end, 3),
                "count": count,
            })

        return timeline

    def get_summary(self) -> dict[str, Any]:
        """Get a comprehensive scan summary."""
        return {
            "scan_id": self.scan_id,
            "total_events": self.total_events,
            "unique_types": self.unique_types,
            "unique_modules": self.unique_modules,
            "duration_s": round(self.duration, 1),
            "overall_risk_score": self.overall_risk_score,
            "category_breakdown": self.get_category_breakdown(),
            "top_risk_events": self.get_top_risk_events(5),
            "top_entities": self.get_top_entities(5),
            "module_stats": self.get_module_stats(),
        }

    def reset(self) -> None:
        """Reset all aggregation data."""
        self._events.clear()
        self._type_stats.clear()
        self._module_counts.clear()
        self._risk_events.clear()
        self._category_counts.clear()
        self.start_time = time.time()
