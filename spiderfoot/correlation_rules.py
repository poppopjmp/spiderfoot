"""Event Correlation Rules Engine for SpiderFoot.

Provides a rule-based engine for correlating events based on
configurable conditions, temporal windows, and pattern matching.
Rules can fire actions when conditions are met across multiple events.
"""

import logging
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("spiderfoot.correlation_rules")


class MatchMode(Enum):
    """How conditions in a rule are combined."""
    ALL = "all"    # All conditions must match (AND)
    ANY = "any"    # At least one condition must match (OR)


class ConditionOp(Enum):
    """Comparison operators for conditions."""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    CONTAINS = "contains"
    MATCHES = "matches"     # regex
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"


@dataclass
class Condition:
    """A single condition to evaluate against an event."""
    field: str                  # "event_type", "data", "module", or any metadata key
    op: ConditionOp
    value: Any = None

    def evaluate(self, event: dict) -> bool:
        """Evaluate this condition against an event dict."""
        actual = event.get(self.field)

        if self.op == ConditionOp.EXISTS:
            return actual is not None

        if actual is None:
            return False

        if self.op == ConditionOp.EQUALS:
            return actual == self.value
        elif self.op == ConditionOp.NOT_EQUALS:
            return actual != self.value
        elif self.op == ConditionOp.CONTAINS:
            return self.value in str(actual)
        elif self.op == ConditionOp.MATCHES:
            return bool(re.search(self.value, str(actual), re.IGNORECASE))
        elif self.op == ConditionOp.GREATER_THAN:
            return actual > self.value
        elif self.op == ConditionOp.LESS_THAN:
            return actual < self.value
        elif self.op == ConditionOp.IN:
            return actual in self.value
        elif self.op == ConditionOp.NOT_IN:
            return actual not in self.value

        return False


@dataclass
class CorrelationMatch:
    """Records a correlation rule match."""
    rule_name: str
    events: List[dict]
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CorrelationRule:
    """A configurable correlation rule.

    Rules match events based on conditions and can track patterns
    across multiple events within time windows.

    Usage:
        rule = CorrelationRule("high_risk_ip")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        rule.add_condition(Condition("risk", ConditionOp.GREATER_THAN, 70))
        rule.set_threshold(count=3, window_seconds=300)
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        mode: MatchMode = MatchMode.ALL,
        enabled: bool = True,
        priority: int = 0,
    ):
        self.name = name
        self.description = description
        self.mode = mode
        self._enabled = enabled
        self.priority = priority

        self._conditions: List[Condition] = []
        self._threshold_count: int = 1
        self._window_seconds: Optional[float] = None
        self._group_by: Optional[str] = None

        # Tracking matched events
        self._matched_events: List[Tuple[float, dict]] = []
        self._group_counts: Dict[str, List[Tuple[float, dict]]] = defaultdict(list)
        self._fire_count = 0

    def add_condition(self, condition: Condition) -> "CorrelationRule":
        self._conditions.append(condition)
        return self

    def set_threshold(self, count: int = 1, window_seconds: Optional[float] = None) -> "CorrelationRule":
        """Set the number of matching events required to fire, optionally within a time window."""
        self._threshold_count = count
        self._window_seconds = window_seconds
        return self

    def set_group_by(self, field_name: str) -> "CorrelationRule":
        """Group events by a field for threshold counting."""
        self._group_by = field_name
        return self

    def evaluate(self, event: dict) -> bool:
        """Evaluate if an event matches this rule's conditions.

        Returns True if conditions match (does not consider threshold).
        """
        if not self._enabled or not self._conditions:
            return False

        results = [c.evaluate(event) for c in self._conditions]

        if self.mode == MatchMode.ALL:
            return all(results)
        else:
            return any(results)

    def process(self, event: dict) -> Optional[CorrelationMatch]:
        """Process an event against this rule.

        Returns a CorrelationMatch if the threshold is reached.
        """
        if not self._enabled:
            return None

        if not self.evaluate(event):
            return None

        now = time.time()

        if self._group_by:
            group_key = str(event.get(self._group_by, "_default"))
            group_events = self._group_counts[group_key]
            group_events.append((now, event))

            # Window pruning
            if self._window_seconds is not None:
                cutoff = now - self._window_seconds
                self._group_counts[group_key] = [
                    (t, e) for t, e in group_events if t >= cutoff
                ]
                group_events = self._group_counts[group_key]

            if len(group_events) >= self._threshold_count:
                self._fire_count += 1
                match = CorrelationMatch(
                    rule_name=self.name,
                    events=[e for _, e in group_events],
                    metadata={"group_key": group_key, "count": len(group_events)},
                )
                self._group_counts[group_key] = []
                return match
        else:
            self._matched_events.append((now, event))

            # Window pruning
            if self._window_seconds is not None:
                cutoff = now - self._window_seconds
                self._matched_events = [
                    (t, e) for t, e in self._matched_events if t >= cutoff
                ]

            if len(self._matched_events) >= self._threshold_count:
                self._fire_count += 1
                match = CorrelationMatch(
                    rule_name=self.name,
                    events=[e for _, e in self._matched_events],
                    metadata={"count": len(self._matched_events)},
                )
                self._matched_events = []
                return match

        return None

    @property
    def fire_count(self) -> int:
        return self._fire_count

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def reset(self) -> None:
        self._matched_events.clear()
        self._group_counts.clear()
        self._fire_count = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "mode": self.mode.value,
            "enabled": self._enabled,
            "priority": self.priority,
            "conditions": len(self._conditions),
            "threshold": self._threshold_count,
            "window_seconds": self._window_seconds,
            "group_by": self._group_by,
            "fire_count": self._fire_count,
        }


class CorrelationEngine:
    """Engine that manages and evaluates correlation rules.

    Usage:
        engine = CorrelationEngine()
        rule = CorrelationRule("multi_ip_scan")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        rule.set_threshold(count=5, window_seconds=60)
        engine.add_rule(rule)

        # Register callback for matches
        engine.on_match(lambda m: print(f"Correlation: {m.rule_name}"))

        # Feed events
        for event in events:
            engine.process(event)
    """

    def __init__(self):
        self._rules: Dict[str, CorrelationRule] = {}
        self._callbacks: List[Callable[[CorrelationMatch], None]] = []
        self._matches: List[CorrelationMatch] = []
        self._events_processed = 0
        self._lock = threading.Lock()

    def add_rule(self, rule: CorrelationRule) -> "CorrelationEngine":
        with self._lock:
            self._rules[rule.name] = rule
        return self

    def remove_rule(self, name: str) -> bool:
        with self._lock:
            return self._rules.pop(name, None) is not None

    def get_rule(self, name: str) -> Optional[CorrelationRule]:
        return self._rules.get(name)

    def on_match(self, callback: Callable[[CorrelationMatch], None]) -> None:
        self._callbacks.append(callback)

    def process(self, event: dict) -> List[CorrelationMatch]:
        """Process an event against all rules. Returns any matches."""
        self._events_processed += 1
        matches = []

        with self._lock:
            rules = sorted(self._rules.values(), key=lambda r: -r.priority)

        for rule in rules:
            match = rule.process(event)
            if match is not None:
                matches.append(match)
                self._matches.append(match)
                for cb in self._callbacks:
                    try:
                        cb(match)
                    except Exception as e:
                        log.error("Correlation callback error: %s", e)

        return matches

    def process_batch(self, events: List[dict]) -> List[CorrelationMatch]:
        """Process multiple events. Returns all matches."""
        all_matches = []
        for event in events:
            all_matches.extend(self.process(event))
        return all_matches

    @property
    def rule_count(self) -> int:
        with self._lock:
            return len(self._rules)

    @property
    def rule_names(self) -> List[str]:
        with self._lock:
            return sorted(self._rules.keys())

    @property
    def events_processed(self) -> int:
        return self._events_processed

    @property
    def total_matches(self) -> int:
        return len(self._matches)

    def get_matches(self, rule_name: Optional[str] = None) -> List[CorrelationMatch]:
        if rule_name:
            return [m for m in self._matches if m.rule_name == rule_name]
        return list(self._matches)

    def reset(self) -> None:
        with self._lock:
            for rule in self._rules.values():
                rule.reset()
            self._matches.clear()
            self._events_processed = 0

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "rules": {name: r.to_dict() for name, r in self._rules.items()},
                "events_processed": self._events_processed,
                "total_matches": len(self._matches),
            }
