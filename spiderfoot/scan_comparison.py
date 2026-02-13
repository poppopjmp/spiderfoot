"""
Scan Comparison — side-by-side diff of two SpiderFoot scans.

Provides:
  - Full diff between two scans (new, removed, changed findings)
  - Per-category breakdown (hosts, ports, vulns, emails, etc.)
  - Change scoring for attack surface drift detection
  - Timeline comparison for repeated scans on same target
  - Export-ready diff summaries

v5.6.9
"""
from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

_log = logging.getLogger("spiderfoot.scan_comparison")


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class SeverityLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Event types grouped by reconnaissance category
EVENT_CATEGORIES = {
    "infrastructure": [
        "IP_ADDRESS", "IPV6_ADDRESS", "INTERNET_NAME",
        "DOMAIN_NAME", "SUBDOMAIN", "DNS_TEXT",
    ],
    "network": [
        "TCP_PORT_OPEN", "UDP_PORT_OPEN", "OPERATING_SYSTEM",
        "WEBSERVER_BANNER", "WEBSERVER_HTTPHEADERS",
    ],
    "vulnerabilities": [
        "VULNERABILITY_CVE_CRITICAL", "VULNERABILITY_CVE_HIGH",
        "VULNERABILITY_CVE_MEDIUM", "VULNERABILITY_CVE_LOW",
        "VULNERABILITY_GENERAL",
    ],
    "identity": [
        "EMAILADDR", "HUMAN_NAME", "PHONE_NUMBER",
        "USERNAME", "SOCIAL_MEDIA",
    ],
    "leaks": [
        "EMAILADDR_COMPROMISED", "PASSWORD_COMPROMISED",
        "LEAKSITE_CONTENT", "DARKNET_MENTION_CONTENT",
    ],
    "certificates": [
        "SSL_CERTIFICATE_ISSUED", "SSL_CERTIFICATE_EXPIRING",
        "SSL_CERTIFICATE_EXPIRED", "SSL_CERTIFICATE_MISMATCH",
    ],
    "web_content": [
        "URL_FORM", "URL_UPLOAD", "URL_JAVASCRIPT",
        "WEB_ANALYTICS_ID", "URL_PASSWORD",
    ],
    "whois": [
        "DOMAIN_WHOIS", "NETBLOCK_WHOIS", "DOMAIN_REGISTRAR",
    ],
    "malicious": [
        "MALICIOUS_IPADDR", "MALICIOUS_INTERNET_NAME",
        "MALICIOUS_AFFILIATE_IPADDR", "MALICIOUS_COHOST",
        "BLACKLISTED_IPADDR", "BLACKLISTED_AFFILIATE_IPADDR",
    ],
    "cloud": [
        "CLOUD_STORAGE_BUCKET", "CLOUD_STORAGE_BUCKET_OPEN",
        "PROVIDER_HOSTING",
    ],
}

# Map event types to severity for risk scoring
EVENT_SEVERITY: dict[str, SeverityLevel] = {
    "VULNERABILITY_CVE_CRITICAL": SeverityLevel.CRITICAL,
    "VULNERABILITY_CVE_HIGH": SeverityLevel.HIGH,
    "VULNERABILITY_CVE_MEDIUM": SeverityLevel.MEDIUM,
    "VULNERABILITY_CVE_LOW": SeverityLevel.LOW,
    "SSL_CERTIFICATE_EXPIRED": SeverityLevel.HIGH,
    "SSL_CERTIFICATE_EXPIRING": SeverityLevel.MEDIUM,
    "CLOUD_STORAGE_BUCKET_OPEN": SeverityLevel.HIGH,
    "EMAILADDR_COMPROMISED": SeverityLevel.HIGH,
    "PASSWORD_COMPROMISED": SeverityLevel.CRITICAL,
    "MALICIOUS_IPADDR": SeverityLevel.HIGH,
    "MALICIOUS_INTERNET_NAME": SeverityLevel.HIGH,
    "BLACKLISTED_IPADDR": SeverityLevel.MEDIUM,
    "TCP_PORT_OPEN": SeverityLevel.LOW,
}


@dataclass
class DiffItem:
    """A single diffed finding between two scans."""
    change_type: str  # ChangeType value
    category: str
    event_type: str
    data: str
    severity: str = SeverityLevel.INFO.value

    # Only for CHANGED items
    old_data: str = ""
    old_source: str = ""

    # Source info
    source_module: str = ""
    scan_id: str = ""

    def to_dict(self) -> dict:
        d = {
            "change_type": self.change_type,
            "category": self.category,
            "event_type": self.event_type,
            "data": self.data,
            "severity": self.severity,
            "source_module": self.source_module,
        }
        if self.change_type == ChangeType.CHANGED.value:
            d["old_data"] = self.old_data
        return d


@dataclass
class CategoryDiff:
    """Diff summary for a single category."""
    category: str
    added: int = 0
    removed: int = 0
    changed: int = 0
    unchanged: int = 0
    items: list[dict] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return self.added + self.removed + self.changed

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "added": self.added,
            "removed": self.removed,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "total_changes": self.total_changes,
            "items": self.items,
        }


@dataclass
class ComparisonResult:
    """Full comparison result between two scans."""
    comparison_id: str = ""
    scan_a_id: str = ""
    scan_b_id: str = ""
    scan_a_target: str = ""
    scan_b_target: str = ""
    scan_a_started: str = ""
    scan_b_started: str = ""
    created_at: float = 0.0

    # Summary counts
    total_added: int = 0
    total_removed: int = 0
    total_changed: int = 0
    total_unchanged: int = 0

    # Risk scoring
    risk_delta: float = 0.0  # Positive = more risk, negative = less
    risk_grade: str = ""     # A-F grade

    # Per-category breakdowns
    categories: dict[str, dict] = field(default_factory=dict)

    # Individual diff items (capped)
    diff_items: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "comparison_id": self.comparison_id,
            "scan_a_id": self.scan_a_id,
            "scan_b_id": self.scan_b_id,
            "scan_a_target": self.scan_a_target,
            "scan_b_target": self.scan_b_target,
            "scan_a_started": self.scan_a_started,
            "scan_b_started": self.scan_b_started,
            "created_at": self.created_at,
            "summary": {
                "added": self.total_added,
                "removed": self.total_removed,
                "changed": self.total_changed,
                "unchanged": self.total_unchanged,
            },
            "risk_delta": round(self.risk_delta, 2),
            "risk_grade": self.risk_grade,
            "categories": self.categories,
            "diff_items": self.diff_items,
        }


class ScanComparator:
    """Compare two SpiderFoot scans and produce a structured diff.

    Usage::

        comparator = ScanComparator()
        result = comparator.compare(scan_a_events, scan_b_events,
                                     scan_a_id="abc", scan_b_id="def")
    """

    MAX_DIFF_ITEMS = 500

    def __init__(self):
        self._history: list[ComparisonResult] = []
        # Build reverse lookup: event_type → category
        self._type_to_category: dict[str, str] = {}
        for cat, types in EVENT_CATEGORIES.items():
            for t in types:
                self._type_to_category[t] = cat

    def compare(
        self,
        scan_a_events: list[dict],
        scan_b_events: list[dict],
        *,
        scan_a_id: str = "",
        scan_b_id: str = "",
        scan_a_target: str = "",
        scan_b_target: str = "",
        scan_a_started: str = "",
        scan_b_started: str = "",
        include_unchanged: bool = False,
        max_items: int | None = None,
    ) -> ComparisonResult:
        """Compare two sets of scan events.

        Args:
            scan_a_events: Events from the baseline scan (older).
              Each event is a dict with at least 'type' and 'data' keys.
            scan_b_events: Events from the comparison scan (newer).
            include_unchanged: Include unchanged items in output.
            max_items: Max diff items to include (default: MAX_DIFF_ITEMS).

        Returns:
            ComparisonResult with full breakdown.
        """
        cap = max_items or self.MAX_DIFF_ITEMS

        # Build fingerprint maps: fingerprint → event_dict
        a_map = self._build_fingerprint_map(scan_a_events)
        b_map = self._build_fingerprint_map(scan_b_events)

        all_fingerprints = set(a_map.keys()) | set(b_map.keys())

        diff_items: list[DiffItem] = []
        category_diffs: dict[str, CategoryDiff] = defaultdict(
            lambda: CategoryDiff(category="other"))

        for fp in all_fingerprints:
            in_a = fp in a_map
            in_b = fp in b_map

            evt = b_map.get(fp) or a_map.get(fp, {})
            event_type = evt.get("type", "UNKNOWN")
            category = self._type_to_category.get(event_type, "other")
            severity = EVENT_SEVERITY.get(
                event_type, SeverityLevel.INFO).value
            data = evt.get("data", "")
            source = evt.get("module", "")

            if category not in category_diffs:
                category_diffs[category] = CategoryDiff(category=category)
            cat_diff = category_diffs[category]

            if in_a and not in_b:
                # Removed in newer scan
                item = DiffItem(
                    change_type=ChangeType.REMOVED.value,
                    category=category,
                    event_type=event_type,
                    data=a_map[fp].get("data", ""),
                    severity=severity,
                    source_module=a_map[fp].get("module", ""),
                    scan_id=scan_a_id,
                )
                diff_items.append(item)
                cat_diff.removed += 1

            elif not in_a and in_b:
                # Added in newer scan
                item = DiffItem(
                    change_type=ChangeType.ADDED.value,
                    category=category,
                    event_type=event_type,
                    data=data,
                    severity=severity,
                    source_module=source,
                    scan_id=scan_b_id,
                )
                diff_items.append(item)
                cat_diff.added += 1

            else:
                # Present in both — check if data changed
                a_data = a_map[fp].get("data", "")
                b_data = b_map[fp].get("data", "")
                if a_data != b_data:
                    item = DiffItem(
                        change_type=ChangeType.CHANGED.value,
                        category=category,
                        event_type=event_type,
                        data=b_data,
                        old_data=a_data,
                        severity=severity,
                        source_module=source,
                        scan_id=scan_b_id,
                    )
                    diff_items.append(item)
                    cat_diff.changed += 1
                else:
                    cat_diff.unchanged += 1
                    if include_unchanged:
                        item = DiffItem(
                            change_type=ChangeType.UNCHANGED.value,
                            category=category,
                            event_type=event_type,
                            data=data,
                            severity=severity,
                            source_module=source,
                        )
                        diff_items.append(item)

        # Sort: critical/high first, then by change type
        severity_order = {
            SeverityLevel.CRITICAL.value: 0,
            SeverityLevel.HIGH.value: 1,
            SeverityLevel.MEDIUM.value: 2,
            SeverityLevel.LOW.value: 3,
            SeverityLevel.INFO.value: 4,
        }
        change_order = {
            ChangeType.ADDED.value: 0,
            ChangeType.REMOVED.value: 1,
            ChangeType.CHANGED.value: 2,
            ChangeType.UNCHANGED.value: 3,
        }
        diff_items.sort(key=lambda d: (
            severity_order.get(d.severity, 9),
            change_order.get(d.change_type, 9),
        ))

        # Compute risk delta
        risk_delta = self._compute_risk_delta(diff_items)

        # Build result
        cid = hashlib.sha256(
            f"{scan_a_id}:{scan_b_id}:{time.time()}".encode()
        ).hexdigest()[:16]

        result = ComparisonResult(
            comparison_id=cid,
            scan_a_id=scan_a_id,
            scan_b_id=scan_b_id,
            scan_a_target=scan_a_target,
            scan_b_target=scan_b_target,
            scan_a_started=scan_a_started,
            scan_b_started=scan_b_started,
            created_at=time.time(),
            total_added=sum(c.added for c in category_diffs.values()),
            total_removed=sum(c.removed for c in category_diffs.values()),
            total_changed=sum(c.changed for c in category_diffs.values()),
            total_unchanged=sum(c.unchanged for c in category_diffs.values()),
            risk_delta=risk_delta,
            risk_grade=self._risk_grade(risk_delta),
            categories={k: v.to_dict() for k, v in category_diffs.items()},
            diff_items=[d.to_dict() for d in diff_items[:cap]],
        )

        self._history.append(result)
        if len(self._history) > 100:
            self._history = self._history[-100:]

        _log.info(
            "Scan comparison %s: +%d -%d ~%d (risk_delta=%.2f %s)",
            cid, result.total_added, result.total_removed,
            result.total_changed, risk_delta, result.risk_grade,
        )

        return result

    @property
    def history(self) -> list[ComparisonResult]:
        return list(self._history)

    def get_comparison(self, comparison_id: str) -> ComparisonResult | None:
        for c in self._history:
            if c.comparison_id == comparison_id:
                return c
        return None

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _build_fingerprint_map(events: list[dict]) -> dict[str, dict]:
        """Build a map of fingerprint → event for dedup matching.

        Fingerprint = hash(event_type + normalized_data).
        """
        result: dict[str, dict] = {}
        for evt in events:
            etype = evt.get("type", "")
            data = evt.get("data", "")
            fp = hashlib.sha256(f"{etype}:{data}".encode()).hexdigest()[:24]
            result[fp] = evt
        return result

    @staticmethod
    def _compute_risk_delta(items: list[DiffItem]) -> float:
        """Compute a numeric risk change score.

        Positive = increased risk, negative = decreased risk.
        Scale: -100 to +100.
        """
        severity_weight = {
            SeverityLevel.CRITICAL.value: 10.0,
            SeverityLevel.HIGH.value: 5.0,
            SeverityLevel.MEDIUM.value: 2.0,
            SeverityLevel.LOW.value: 0.5,
            SeverityLevel.INFO.value: 0.1,
        }
        delta = 0.0
        for item in items:
            w = severity_weight.get(item.severity, 0.1)
            if item.change_type == ChangeType.ADDED.value:
                delta += w
            elif item.change_type == ChangeType.REMOVED.value:
                delta -= w
            elif item.change_type == ChangeType.CHANGED.value:
                delta += w * 0.3  # Changes are partial risk shifts

        # Clamp to [-100, 100]
        return max(-100.0, min(100.0, delta))

    @staticmethod
    def _risk_grade(delta: float) -> str:
        """Convert a risk delta to a letter grade."""
        if delta <= -10:
            return "A"   # Significant risk reduction
        if delta <= -2:
            return "B"   # Moderate risk reduction
        if delta <= 2:
            return "C"   # Minimal change
        if delta <= 10:
            return "D"   # Moderate risk increase
        return "F"       # Significant risk increase

    def get_event_categories(self) -> dict:
        """Return event category definitions."""
        return {
            cat: {
                "event_types": types,
                "count": len(types),
            }
            for cat, types in EVENT_CATEGORIES.items()
        }
