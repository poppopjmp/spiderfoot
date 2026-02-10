"""Alert rules engine for scan findings.

Provides configurable alerting based on scan events: severity thresholds,
pattern matching, rate-based alerts, and notification channel routing.
"""

from __future__ import annotations

import logging
import re
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.alert_rules")


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertConditionType(Enum):
    """Types of alert conditions."""
    EVENT_TYPE = "event_type"       # Match specific event types
    PATTERN = "pattern"             # Regex pattern on event data
    SEVERITY = "severity"           # Risk score threshold
    RATE = "rate"                   # Event rate threshold
    COUNT = "count"                 # Total event count threshold
    CUSTOM = "custom"               # Custom callable


@dataclass
class AlertCondition:
    """A single condition that can trigger an alert."""
    condition_type: AlertConditionType
    value: Any = None
    operator: str = "gte"  # gte, lte, eq, contains, matches

    def evaluate(self, context: dict) -> bool:
        """Evaluate condition against event context."""
        if self.condition_type == AlertConditionType.EVENT_TYPE:
            return context.get("event_type") == self.value

        elif self.condition_type == AlertConditionType.PATTERN:
            data = context.get("data", "")
            if isinstance(data, str) and isinstance(self.value, str):
                return bool(re.search(self.value, data))
            return False

        elif self.condition_type == AlertConditionType.SEVERITY:
            score = context.get("risk_score", 0)
            return self._compare(score, self.value)

        elif self.condition_type == AlertConditionType.RATE:
            rate = context.get("rate", 0)
            return self._compare(rate, self.value)

        elif self.condition_type == AlertConditionType.COUNT:
            count = context.get("count", 0)
            return self._compare(count, self.value)

        elif self.condition_type == AlertConditionType.CUSTOM:
            if callable(self.value):
                return bool(self.value(context))
            return False

        return False

    def _compare(self, actual: Any, expected: Any) -> bool:
        if self.operator == "gte":
            return actual >= expected
        elif self.operator == "lte":
            return actual <= expected
        elif self.operator == "eq":
            return actual == expected
        elif self.operator == "gt":
            return actual > expected
        elif self.operator == "lt":
            return actual < expected
        return False

    def to_dict(self) -> dict:
        return {
            "condition_type": self.condition_type.value,
            "value": str(self.value) if not isinstance(self.value, (int, float, str, bool, type(None))) else self.value,
            "operator": self.operator,
        }


@dataclass
class Alert:
    """A triggered alert instance."""
    rule_name: str
    severity: AlertSeverity
    message: str
    timestamp: float = field(default_factory=time.time)
    context: dict = field(default_factory=dict)
    acknowledged: bool = False

    def acknowledge(self) -> None:
        self.acknowledged = True

    def to_dict(self) -> dict:
        return {
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
            "context": {k: str(v) for k, v in self.context.items()},
        }


class AlertRule:
    """A rule that evaluates conditions and produces alerts.

    Args:
        name: Unique rule name.
        severity: Alert severity when triggered.
        message_template: Template string for alert message (supports {key} placeholders).
        conditions: List of conditions (all must match by default).
        match_any: If True, any condition triggers; if False, all must match.
        cooldown_seconds: Minimum time between alerts from this rule.
        max_alerts: Maximum alerts this rule can produce (0=unlimited).
        enabled: Whether rule is active.
    """

    def __init__(
        self,
        name: str,
        severity: AlertSeverity = AlertSeverity.MEDIUM,
        message_template: str = "Alert: {rule_name}",
        conditions: list[AlertCondition] | None = None,
        match_any: bool = False,
        cooldown_seconds: float = 0.0,
        max_alerts: int = 0,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.severity = severity
        self.message_template = message_template
        self.conditions = conditions or []
        self.match_any = match_any
        self.cooldown_seconds = cooldown_seconds
        self.max_alerts = max_alerts
        self.enabled = enabled
        self._alert_count = 0
        self._last_alert_time = 0.0

    def add_condition(self, condition: AlertCondition) -> "AlertRule":
        self.conditions.append(condition)
        return self

    def evaluate(self, context: dict) -> Alert | None:
        """Evaluate rule against context. Returns Alert if triggered, None otherwise."""
        if not self.enabled:
            return None

        if not self.conditions:
            return None

        # Check max alerts
        if self.max_alerts > 0 and self._alert_count >= self.max_alerts:
            return None

        # Check cooldown
        if self.cooldown_seconds > 0:
            elapsed = time.time() - self._last_alert_time
            if elapsed < self.cooldown_seconds:
                return None

        # Evaluate conditions
        if self.match_any:
            triggered = any(c.evaluate(context) for c in self.conditions)
        else:
            triggered = all(c.evaluate(context) for c in self.conditions)

        if not triggered:
            return None

        # Build message
        msg_context = {"rule_name": self.name, **context}
        try:
            message = self.message_template.format(**msg_context)
        except (KeyError, IndexError):
            message = self.message_template

        self._alert_count += 1
        self._last_alert_time = time.time()

        return Alert(
            rule_name=self.name,
            severity=self.severity,
            message=message,
            context=context,
        )

    @property
    def alert_count(self) -> int:
        return self._alert_count

    def reset(self) -> None:
        self._alert_count = 0
        self._last_alert_time = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "severity": self.severity.value,
            "enabled": self.enabled,
            "match_any": self.match_any,
            "cooldown_seconds": self.cooldown_seconds,
            "max_alerts": self.max_alerts,
            "alert_count": self._alert_count,
            "conditions": [c.to_dict() for c in self.conditions],
        }


class AlertEngine:
    """Manages alert rules and processes events against them.

    Args:
        max_history: Maximum number of triggered alerts to retain.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._rules: dict[str, AlertRule] = {}
        self._alerts: list[Alert] = []
        self._max_history = max_history
        self._handlers: list[Callable[[Alert], None]] = []
        self._lock = threading.RLock()

    def add_rule(self, rule: AlertRule) -> "AlertEngine":
        """Register an alert rule."""
        with self._lock:
            self._rules[rule.name] = rule
        return self

    def remove_rule(self, name: str) -> bool:
        with self._lock:
            return self._rules.pop(name, None) is not None

    def get_rule(self, name: str) -> AlertRule | None:
        return self._rules.get(name)

    def add_handler(self, handler: Callable[[Alert], None]) -> "AlertEngine":
        """Add a callback invoked when an alert fires."""
        self._handlers.append(handler)
        return self

    def process_event(self, context: dict) -> list[Alert]:
        """Evaluate all rules against an event context. Returns triggered alerts."""
        triggered = []
        with self._lock:
            for rule in self._rules.values():
                alert = rule.evaluate(context)
                if alert:
                    triggered.append(alert)
                    self._alerts.append(alert)

            # Trim history
            if len(self._alerts) > self._max_history:
                self._alerts = self._alerts[-self._max_history:]

        # Call handlers outside lock
        for alert in triggered:
            for handler in self._handlers:
                try:
                    handler(alert)
                except Exception as e:
                    log.debug("handler(alert) callback failed: %s", e)

        return triggered

    @property
    def alerts(self) -> list[Alert]:
        return list(self._alerts)

    def get_alerts_by_severity(self, severity: AlertSeverity) -> list[Alert]:
        return [a for a in self._alerts if a.severity == severity]

    def get_unacknowledged(self) -> list[Alert]:
        return [a for a in self._alerts if not a.acknowledged]

    def acknowledge_all(self) -> None:
        for a in self._alerts:
            a.acknowledge()

    def clear_alerts(self) -> None:
        with self._lock:
            self._alerts.clear()

    def reset(self) -> None:
        """Reset all rules and clear alerts."""
        with self._lock:
            for rule in self._rules.values():
                rule.reset()
            self._alerts.clear()

    @property
    def rules(self) -> list[AlertRule]:
        return list(self._rules.values())

    def summary(self) -> dict:
        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            "total_alerts": len(self._alerts),
            "unacknowledged": len(self.get_unacknowledged()),
            "by_severity": {
                s.value: len(self.get_alerts_by_severity(s))
                for s in AlertSeverity
            },
        }

    def to_dict(self) -> dict:
        return {
            "rules": {name: r.to_dict() for name, r in self._rules.items()},
            "alert_count": len(self._alerts),
            "summary": self.summary(),
        }
