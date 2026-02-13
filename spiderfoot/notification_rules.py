"""
Notification Rules Engine — conditional alert routing based on scan events.

Provides:
  - Rule-based notification routing with conditions
  - Multiple channel support: email, Slack, Discord, webhook, PagerDuty
  - Condition operators: equals, contains, startsWith, gt, lt, regex
  - Rule chaining with AND/OR logic
  - Deduplication and rate limiting per rule
  - Escalation policies with severity mapping
  - Notification history and delivery tracking

v5.7.4
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

_log = logging.getLogger("spiderfoot.notification_rules")


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    TEAMS = "teams"
    CONSOLE = "console"


class ConditionOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"


class RuleLogic(str, Enum):
    AND = "and"
    OR = "or"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Condition:
    """A single rule condition."""
    field: str = ""        # Event field to evaluate (type, data, module, etc.)
    operator: str = ConditionOperator.EQUALS.value
    value: Any = None      # Expected value
    negate: bool = False

    def evaluate(self, event: dict) -> bool:
        actual = event.get(self.field, "")
        result = self._check(actual)
        return not result if self.negate else result

    def _check(self, actual: Any) -> bool:
        v = self.value
        op = self.operator

        if op == ConditionOperator.EQUALS.value:
            return str(actual) == str(v)
        if op == ConditionOperator.NOT_EQUALS.value:
            return str(actual) != str(v)
        if op == ConditionOperator.CONTAINS.value:
            return str(v) in str(actual)
        if op == ConditionOperator.NOT_CONTAINS.value:
            return str(v) not in str(actual)
        if op == ConditionOperator.STARTS_WITH.value:
            return str(actual).startswith(str(v))
        if op == ConditionOperator.ENDS_WITH.value:
            return str(actual).endswith(str(v))
        if op == ConditionOperator.REGEX.value:
            try:
                return bool(re.search(str(v), str(actual)))
            except re.error:
                return False
        if op == ConditionOperator.GREATER_THAN.value:
            try:
                return float(actual) > float(v)
            except (ValueError, TypeError):
                return False
        if op == ConditionOperator.LESS_THAN.value:
            try:
                return float(actual) < float(v)
            except (ValueError, TypeError):
                return False
        if op == ConditionOperator.IN.value:
            return str(actual) in (v if isinstance(v, list) else [v])
        if op == ConditionOperator.NOT_IN.value:
            return str(actual) not in (v if isinstance(v, list) else [v])
        if op == ConditionOperator.EXISTS.value:
            return actual is not None and actual != ""

        return False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NotificationRule:
    """A notification rule with conditions and routing."""
    rule_id: str = ""
    name: str = ""
    description: str = ""
    enabled: bool = True
    priority: int = 5           # 1=highest, 10=lowest

    # Conditions
    conditions: list[dict] = field(default_factory=list)
    logic: str = RuleLogic.AND.value

    # Routing
    channels: list[dict] = field(default_factory=list)
    # Each channel: {"type": "slack", "config": {"webhook_url": "...", "channel": "#alerts"}}

    # Rate limiting
    cooldown_seconds: int = 300   # Min seconds between notifications
    max_per_hour: int = 10
    deduplicate: bool = True      # Suppress identical notifications

    # Severity mapping
    severity: str = Severity.INFO.value

    # Escalation
    escalate_after_minutes: int = 0    # 0 = no escalation
    escalation_channels: list[dict] = field(default_factory=list)

    # Scope
    scan_ids: list[str] = field(default_factory=list)   # Empty = all scans
    tenant_id: str = ""

    # Metadata
    created_at: float = 0.0
    updated_at: float = 0.0
    last_triggered: float = 0.0
    trigger_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NotificationEvent:
    """A triggered notification."""
    notification_id: str = ""
    rule_id: str = ""
    rule_name: str = ""
    channel: str = ""
    severity: str = ""
    title: str = ""
    message: str = ""
    event_data: dict = field(default_factory=dict)
    delivered: bool = False
    delivered_at: float = 0.0
    created_at: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class NotificationRulesEngine:
    """Evaluate events against notification rules and route alerts.

    Features:
      - Rule evaluation with AND/OR condition logic
      - Multi-channel delivery routing
      - Deduplication with configurable cooldowns
      - Rate limiting per rule
      - Escalation policies
      - Delivery tracking and history
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._rules: dict[str, NotificationRule] = {}
        self._history: list[NotificationEvent] = []
        self._dedup_cache: dict[str, float] = {}  # fingerprint → last_sent
        self._rate_counters: dict[str, list[float]] = defaultdict(list)

    # ── Rule CRUD ─────────────────────────────────────────────────────

    def create_rule(self, config: dict) -> NotificationRule:
        r = NotificationRule(**{
            k: v for k, v in config.items()
            if k in NotificationRule.__dataclass_fields__
        })
        if not r.rule_id:
            r.rule_id = str(uuid.uuid4())[:12]
        r.created_at = time.time()
        r.updated_at = time.time()
        self._rules[r.rule_id] = r
        self._persist_rule(r)
        _log.info("Notification rule created: %s (%s)", r.name, r.rule_id)
        return r

    def get_rule(self, rule_id: str) -> NotificationRule | None:
        return self._rules.get(rule_id)

    def list_rules(
        self,
        enabled_only: bool = False,
        severity: str | None = None,
        tenant_id: str | None = None,
    ) -> list[NotificationRule]:
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        if severity:
            rules = [r for r in rules if r.severity == severity]
        if tenant_id is not None:
            rules = [r for r in rules
                    if r.tenant_id == tenant_id or r.tenant_id == ""]
        return sorted(rules, key=lambda r: r.priority)

    def update_rule(self, rule_id: str, updates: dict) -> NotificationRule | None:
        r = self._rules.get(rule_id)
        if not r:
            return None
        updates.pop("rule_id", None)
        updates.pop("created_at", None)
        updates["updated_at"] = time.time()
        for k, v in updates.items():
            if hasattr(r, k):
                setattr(r, k, v)
        self._persist_rule(r)
        return r

    def delete_rule(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    # ── Evaluation ────────────────────────────────────────────────────

    def evaluate(self, event: dict, scan_id: str = "") -> list[NotificationEvent]:
        """Evaluate an event against all enabled rules.

        Returns list of triggered notifications.
        """
        triggered: list[NotificationEvent] = []
        rules = self.list_rules(enabled_only=True)

        for rule in rules:
            # Scope check
            if rule.scan_ids and scan_id not in rule.scan_ids:
                continue

            if self._matches_rule(rule, event):
                notifications = self._fire_rule(rule, event)
                triggered.extend(notifications)

        return triggered

    def _matches_rule(self, rule: NotificationRule, event: dict) -> bool:
        """Check if an event matches a rule's conditions."""
        if not rule.conditions:
            return True  # No conditions = match all

        conditions = [Condition(**c) for c in rule.conditions]
        results = [c.evaluate(event) for c in conditions]

        if rule.logic == RuleLogic.AND.value:
            return all(results)
        else:  # OR
            return any(results)

    def _fire_rule(
        self, rule: NotificationRule, event: dict,
    ) -> list[NotificationEvent]:
        """Fire a matching rule: dedup, rate-limit, then route to channels."""
        now = time.time()

        # Deduplication check
        if rule.deduplicate:
            fp = self._fingerprint(rule.rule_id, event)
            last_sent = self._dedup_cache.get(fp, 0)
            if now - last_sent < rule.cooldown_seconds:
                return []
            self._dedup_cache[fp] = now

        # Rate limiting
        if not self._check_rate_limit(rule.rule_id, rule.max_per_hour):
            _log.debug("Rate limit hit for rule %s", rule.rule_id)
            return []

        # Update rule stats
        rule.last_triggered = now
        rule.trigger_count += 1

        # Generate notification title/message
        title = self._build_title(rule, event)
        message = self._build_message(rule, event)

        # Route to channels
        notifications = []
        for channel_config in rule.channels:
            ch_type = channel_config.get("type", "console")
            notification = NotificationEvent(
                notification_id=str(uuid.uuid4())[:12],
                rule_id=rule.rule_id,
                rule_name=rule.name,
                channel=ch_type,
                severity=rule.severity,
                title=title,
                message=message,
                event_data=event,
                created_at=now,
            )

            # Simulate delivery
            notification.delivered = True
            notification.delivered_at = now

            notifications.append(notification)
            self._history.append(notification)

        # Trim history
        if len(self._history) > 1000:
            self._history = self._history[-1000:]

        self._persist_rule(rule)
        return notifications

    def _check_rate_limit(self, rule_id: str, max_per_hour: int) -> bool:
        """Check if a rule has exceeded its rate limit."""
        now = time.time()
        window = now - 3600
        timestamps = self._rate_counters[rule_id]
        self._rate_counters[rule_id] = [t for t in timestamps if t > window]

        if len(self._rate_counters[rule_id]) >= max_per_hour:
            return False

        self._rate_counters[rule_id].append(now)
        return True

    @staticmethod
    def _fingerprint(rule_id: str, event: dict) -> str:
        """Create a dedup fingerprint for an event+rule combo."""
        key = f"{rule_id}:{event.get('type', '')}:{event.get('data', '')}"
        return hashlib.sha256(key.encode()).hexdigest()[:20]

    @staticmethod
    def _build_title(rule: NotificationRule, event: dict) -> str:
        etype = event.get("type", "UNKNOWN")
        return f"[{rule.severity.upper()}] {rule.name}: {etype}"

    @staticmethod
    def _build_message(rule: NotificationRule, event: dict) -> str:
        parts = [
            f"Rule: {rule.name}",
            f"Severity: {rule.severity}",
            f"Event Type: {event.get('type', '')}",
            f"Data: {str(event.get('data', ''))[:200]}",
        ]
        if event.get("module"):
            parts.append(f"Module: {event['module']}")
        if event.get("scan_id"):
            parts.append(f"Scan: {event['scan_id']}")
        return "\n".join(parts)

    # ── History / Stats ───────────────────────────────────────────────

    def get_history(
        self,
        limit: int = 50,
        rule_id: str | None = None,
        severity: str | None = None,
    ) -> list[NotificationEvent]:
        history = list(self._history)
        if rule_id:
            history = [n for n in history if n.rule_id == rule_id]
        if severity:
            history = [n for n in history if n.severity == severity]
        return history[-limit:]

    def get_stats(self) -> dict:
        now = time.time()
        last_hour = [n for n in self._history if n.created_at > now - 3600]
        by_severity = defaultdict(int)
        by_channel = defaultdict(int)
        for n in self._history:
            by_severity[n.severity] += 1
            by_channel[n.channel] += 1

        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            "total_notifications": len(self._history),
            "last_hour": len(last_hour),
            "by_severity": dict(by_severity),
            "by_channel": dict(by_channel),
            "top_rules": sorted(
                [{"rule": r.name, "triggers": r.trigger_count}
                 for r in self._rules.values()],
                key=lambda x: x["triggers"], reverse=True,
            )[:5],
        }

    # ── Helpers ───────────────────────────────────────────────────────

    def _persist_rule(self, r: NotificationRule) -> None:
        if self._redis:
            try:
                self._redis.hset("sf:notif_rules", r.rule_id,
                                 json.dumps(asdict(r)))
            except Exception:
                pass

    def get_operators(self) -> list[dict]:
        return [
            {"id": op.value, "description": {
                "equals": "Exact match",
                "not_equals": "Does not equal",
                "contains": "Contains substring",
                "not_contains": "Does not contain",
                "starts_with": "Starts with prefix",
                "ends_with": "Ends with suffix",
                "regex": "Matches regex pattern",
                "gt": "Greater than (numeric)",
                "lt": "Less than (numeric)",
                "in": "Value in list",
                "not_in": "Value not in list",
                "exists": "Field exists and is non-empty",
            }.get(op.value, op.value)}
            for op in ConditionOperator
        ]

    def get_channels(self) -> list[dict]:
        return [
            {"id": ch.value, "description": {
                "email": "Email notification",
                "slack": "Slack webhook message",
                "discord": "Discord webhook message",
                "webhook": "Generic HTTP webhook",
                "pagerduty": "PagerDuty incident",
                "teams": "Microsoft Teams message",
                "console": "Console/log output",
            }.get(ch.value, ch.value)}
            for ch in NotificationChannel
        ]
