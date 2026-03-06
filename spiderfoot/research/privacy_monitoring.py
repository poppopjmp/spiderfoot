"""Phase 8b — Differential Privacy + Real-Time Passive Monitoring.

Cycles 701-750: Differential privacy for collaborative threat intel.
Cycles 751-800: Continuous monitoring with alerting on new asset discovery.
"""

from __future__ import annotations

import hashlib
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ── Differential Privacy (Cycles 701-750) ─────────────────────────────


@dataclass
class PrivacyStat:
    """A statistic prepared with differential privacy guarantees."""

    name: str
    true_value: float
    noisy_value: float
    epsilon: float
    mechanism: str
    timestamp: float = field(default_factory=time.time)

    @property
    def noise_magnitude(self) -> float:
        return abs(self.noisy_value - self.true_value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.noisy_value,
            "epsilon": self.epsilon,
            "mechanism": self.mechanism,
        }


class LaplaceMechanism:
    """Laplace mechanism for differential privacy."""

    @staticmethod
    def add_noise(value: float, sensitivity: float, epsilon: float) -> float:
        """Add Laplace noise to a value.

        Args:
            value: The true value
            sensitivity: The sensitivity of the query (max change from one record)
            epsilon: Privacy budget (smaller = more private)
        """
        if epsilon <= 0:
            raise ValueError("Epsilon must be positive")
        scale = sensitivity / epsilon
        # Laplace noise via inverse CDF
        u = random.uniform(-0.5, 0.5)
        noise = -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))
        return value + noise

    @staticmethod
    def required_epsilon(
        accuracy: float,
        sensitivity: float,
        confidence: float = 0.95,
    ) -> float:
        """Calculate epsilon needed for desired accuracy at given confidence."""
        if accuracy <= 0 or sensitivity <= 0:
            raise ValueError("Accuracy and sensitivity must be positive")
        return sensitivity * math.log(1 / (1 - confidence)) / accuracy


class PrivacyBudgetTracker:
    """Tracks cumulative privacy budget (epsilon) consumption."""

    def __init__(self, total_budget: float = 10.0) -> None:
        self.total_budget = total_budget
        self._spent: float = 0.0
        self._queries: list[dict[str, Any]] = []

    def spend(self, epsilon: float, query_name: str = "") -> bool:
        """Spend privacy budget. Returns False if insufficient budget."""
        if epsilon <= 0:
            raise ValueError("Epsilon must be positive")
        if self._spent + epsilon > self.total_budget:
            return False
        self._spent += epsilon
        self._queries.append({
            "query": query_name,
            "epsilon": epsilon,
            "cumulative": self._spent,
            "timestamp": time.time(),
        })
        return True

    @property
    def remaining(self) -> float:
        return max(0.0, self.total_budget - self._spent)

    @property
    def spent(self) -> float:
        return self._spent

    @property
    def query_count(self) -> int:
        return len(self._queries)

    def get_history(self) -> list[dict[str, Any]]:
        return list(self._queries)

    def reset(self) -> None:
        self._spent = 0.0
        self._queries.clear()


class PrivateScanStatistics:
    """Generate differentially private scan statistics for sharing.

    Allows organizations to share aggregate scan data without
    exposing specific targets or findings.
    """

    DEFAULT_SENSITIVITY: dict[str, float] = {
        "total_findings": 1.0,
        "unique_domains": 1.0,
        "unique_ips": 1.0,
        "vulnerability_count": 1.0,
        "avg_risk_score": 10.0,  # scale 0-100
        "module_count": 1.0,
        "scan_duration_hours": 1.0,
    }

    def __init__(
        self,
        epsilon: float = 1.0,
        budget_tracker: PrivacyBudgetTracker | None = None,
    ) -> None:
        self.default_epsilon = epsilon
        self.budget = budget_tracker or PrivacyBudgetTracker()
        self._stats: list[PrivacyStat] = []

    def privatize_count(
        self,
        name: str,
        true_count: int,
        epsilon: float | None = None,
    ) -> PrivacyStat | None:
        """Add Laplace noise to a count statistic."""
        eps = epsilon or self.default_epsilon
        if not self.budget.spend(eps, name):
            return None

        noisy = LaplaceMechanism.add_noise(
            float(true_count),
            self.DEFAULT_SENSITIVITY.get(name, 1.0),
            eps,
        )
        # Counts can't be negative
        noisy = max(0.0, round(noisy))

        stat = PrivacyStat(
            name=name,
            true_value=float(true_count),
            noisy_value=noisy,
            epsilon=eps,
            mechanism="laplace",
        )
        self._stats.append(stat)
        return stat

    def privatize_mean(
        self,
        name: str,
        true_mean: float,
        value_range: tuple[float, float] = (0.0, 100.0),
        epsilon: float | None = None,
    ) -> PrivacyStat | None:
        """Add noise to a mean statistic."""
        eps = epsilon or self.default_epsilon
        if not self.budget.spend(eps, name):
            return None

        sensitivity = (value_range[1] - value_range[0])
        noisy = LaplaceMechanism.add_noise(true_mean, sensitivity, eps)
        noisy = max(value_range[0], min(value_range[1], noisy))

        stat = PrivacyStat(
            name=name,
            true_value=true_mean,
            noisy_value=noisy,
            epsilon=eps,
            mechanism="laplace",
        )
        self._stats.append(stat)
        return stat

    def generate_report(self) -> dict[str, Any]:
        """Generate a privacy-preserving report of all collected stats."""
        return {
            "stats": [s.to_dict() for s in self._stats],
            "privacy_budget": {
                "total": self.budget.total_budget,
                "spent": self.budget.spent,
                "remaining": self.budget.remaining,
            },
            "stat_count": len(self._stats),
        }

    def get_stats(self) -> list[PrivacyStat]:
        return list(self._stats)


# ── Secure Aggregation (Cycles 701-750) ──────────────────────────────


@dataclass
class AggregationContribution:
    """A contribution from one organization to the aggregate."""

    org_id: str
    hashed_indicators: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    submitted_at: float = field(default_factory=time.time)


class SecureAggregator:
    """Aggregates threat intel across organizations without exposing raw data.

    Uses hashed indicators and noisy counts to enable sharing.
    """

    def __init__(self, min_contributors: int = 3) -> None:
        self.min_contributors = min_contributors
        self._contributions: dict[str, AggregationContribution] = {}

    def submit(self, contribution: AggregationContribution) -> None:
        self._contributions[contribution.org_id] = contribution

    @staticmethod
    def hash_indicator(indicator: str, salt: str = "") -> str:
        """One-way hash an IoC for privacy-preserving sharing."""
        return hashlib.sha256(f"{salt}:{indicator}".encode()).hexdigest()

    def aggregate_indicators(self) -> dict[str, int]:
        """Count how many orgs saw each hashed indicator."""
        if len(self._contributions) < self.min_contributors:
            return {}

        indicator_counts: dict[str, int] = {}
        for contrib in self._contributions.values():
            for h in contrib.hashed_indicators:
                indicator_counts[h] = indicator_counts.get(h, 0) + 1
        return indicator_counts

    def aggregate_counts(self, epsilon: float = 1.0) -> dict[str, float]:
        """Aggregate counts with differential privacy noise."""
        if len(self._contributions) < self.min_contributors:
            return {}

        totals: dict[str, float] = {}
        for contrib in self._contributions.values():
            for key, val in contrib.counts.items():
                totals[key] = totals.get(key, 0.0) + val

        # Add noise to aggregates
        noisy: dict[str, float] = {}
        for key, val in totals.items():
            noisy[key] = max(0.0, LaplaceMechanism.add_noise(val, 1.0, epsilon))
        return noisy

    @property
    def contributor_count(self) -> int:
        return len(self._contributions)

    def meets_threshold(self) -> bool:
        return len(self._contributions) >= self.min_contributors


# ── Real-Time Passive Monitoring (Cycles 751-800) ─────────────────────


class AlertSeverity(Enum):
    """Severity levels for monitoring alerts."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MonitoringAlert:
    """An alert generated by the monitoring system."""

    alert_id: str
    target: str
    asset_type: str
    description: str
    severity: AlertSeverity
    old_value: str = ""
    new_value: str = ""
    detected_at: float = field(default_factory=time.time)
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "target": self.target,
            "asset_type": self.asset_type,
            "description": self.description,
            "severity": self.severity.value,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "detected_at": self.detected_at,
            "acknowledged": self.acknowledged,
        }


@dataclass
class MonitorTarget:
    """A target being continuously monitored."""

    target_id: str
    target_value: str
    check_interval_seconds: float = 3600.0  # 1 hour default
    last_checked: float = 0.0
    is_active: bool = True
    baseline: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


class AssetBaseline:
    """Tracks the baseline state of assets for change detection."""

    def __init__(self) -> None:
        self._baselines: dict[str, dict[str, set[str]]] = {}

    def set_baseline(
        self,
        target_id: str,
        asset_type: str,
        values: set[str],
    ) -> None:
        if target_id not in self._baselines:
            self._baselines[target_id] = {}
        self._baselines[target_id][asset_type] = set(values)

    def get_baseline(self, target_id: str, asset_type: str) -> set[str]:
        return self._baselines.get(target_id, {}).get(asset_type, set())

    def detect_changes(
        self,
        target_id: str,
        asset_type: str,
        current_values: set[str],
    ) -> dict[str, set[str]]:
        """Compare current values against baseline."""
        baseline = self.get_baseline(target_id, asset_type)
        if not baseline:
            return {"added": current_values, "removed": set()}

        return {
            "added": current_values - baseline,
            "removed": baseline - current_values,
        }

    def has_baseline(self, target_id: str) -> bool:
        return target_id in self._baselines


class PassiveMonitor:
    """Continuous passive monitoring with change detection and alerting.

    Monitors targets at configurable intervals, detects changes in the
    attack surface, and generates alerts for new discoveries.
    """

    SEVERITY_MAP: dict[str, AlertSeverity] = {
        "subdomain": AlertSeverity.MEDIUM,
        "ip_address": AlertSeverity.MEDIUM,
        "open_port": AlertSeverity.HIGH,
        "certificate": AlertSeverity.MEDIUM,
        "email": AlertSeverity.LOW,
        "technology": AlertSeverity.LOW,
        "vulnerability": AlertSeverity.CRITICAL,
        "domain": AlertSeverity.MEDIUM,
    }

    def __init__(self) -> None:
        self._targets: dict[str, MonitorTarget] = {}
        self._baseline = AssetBaseline()
        self._alerts: list[MonitoringAlert] = []
        self._alert_counter = 0
        self._callbacks: list[Callable[[MonitoringAlert], None]] = []

    def add_target(self, target: MonitorTarget) -> None:
        self._targets[target.target_id] = target

    def remove_target(self, target_id: str) -> bool:
        return self._targets.pop(target_id, None) is not None

    def get_target(self, target_id: str) -> MonitorTarget | None:
        return self._targets.get(target_id)

    def get_active_targets(self) -> list[MonitorTarget]:
        return [t for t in self._targets.values() if t.is_active]

    def get_due_targets(self) -> list[MonitorTarget]:
        """Get targets that are due for a check."""
        now = time.time()
        return [
            t
            for t in self._targets.values()
            if t.is_active
            and (now - t.last_checked) >= t.check_interval_seconds
        ]

    def set_baseline(
        self,
        target_id: str,
        asset_type: str,
        values: set[str],
    ) -> None:
        self._baseline.set_baseline(target_id, asset_type, values)

    def check_for_changes(
        self,
        target_id: str,
        asset_type: str,
        current_values: set[str],
    ) -> list[MonitoringAlert]:
        """Check current values against baseline and generate alerts."""
        target = self._targets.get(target_id)
        if not target:
            return []

        changes = self._baseline.detect_changes(target_id, asset_type, current_values)
        alerts: list[MonitoringAlert] = []

        severity = self.SEVERITY_MAP.get(asset_type, AlertSeverity.INFO)

        for added in changes["added"]:
            self._alert_counter += 1
            alert = MonitoringAlert(
                alert_id=f"alert-{self._alert_counter:06d}",
                target=target.target_value,
                asset_type=asset_type,
                description=f"New {asset_type} discovered: {added}",
                severity=severity,
                new_value=added,
            )
            alerts.append(alert)
            self._alerts.append(alert)
            for cb in self._callbacks:
                cb(alert)

        for removed in changes["removed"]:
            self._alert_counter += 1
            alert = MonitoringAlert(
                alert_id=f"alert-{self._alert_counter:06d}",
                target=target.target_value,
                asset_type=asset_type,
                description=f"{asset_type} no longer present: {removed}",
                severity=AlertSeverity.INFO,
                old_value=removed,
            )
            alerts.append(alert)
            self._alerts.append(alert)

        # Update baseline
        self._baseline.set_baseline(target_id, asset_type, current_values)
        target.last_checked = time.time()

        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_alerts(
        self,
        severity: AlertSeverity | None = None,
        unacknowledged_only: bool = False,
    ) -> list[MonitoringAlert]:
        result = self._alerts
        if severity:
            result = [a for a in result if a.severity == severity]
        if unacknowledged_only:
            result = [a for a in result if not a.acknowledged]
        return result

    def register_callback(
        self,
        callback: Callable[[MonitoringAlert], None],
    ) -> None:
        self._callbacks.append(callback)

    def get_status(self) -> dict[str, Any]:
        return {
            "total_targets": len(self._targets),
            "active_targets": len(self.get_active_targets()),
            "due_targets": len(self.get_due_targets()),
            "total_alerts": len(self._alerts),
            "unacknowledged": len(
                [a for a in self._alerts if not a.acknowledged]
            ),
            "alerts_by_severity": {
                s.value: len([a for a in self._alerts if a.severity == s])
                for s in AlertSeverity
            },
        }

    @property
    def target_count(self) -> int:
        return len(self._targets)

    @property
    def alert_count(self) -> int:
        return len(self._alerts)
