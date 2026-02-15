"""Event Filter Chain for SpiderFoot.

Provides a configurable chain of filters to include/exclude events
based on type, content patterns, risk thresholds, and custom predicates.
Filters are composable and can be applied pre- or post-processing.
"""

from __future__ import annotations

import logging
import re
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.event_filter")


class FilterAction(Enum):
    """Action to take when a filter matches."""
    ALLOW = "allow"
    DENY = "deny"


class FilterResult(Enum):
    """Result of a filter evaluation."""
    PASS = "pass"        # Event passes the filter
    BLOCK = "block"      # Event is blocked
    SKIP = "skip"        # Filter doesn't apply (no opinion)


@dataclass
class FilterStats:
    """Statistics for a single filter."""
    name: str
    evaluated: int = 0
    passed: int = 0
    blocked: int = 0
    skipped: int = 0
    errors: int = 0

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "name": self.name,
            "evaluated": self.evaluated,
            "passed": self.passed,
            "blocked": self.blocked,
            "skipped": self.skipped,
            "errors": self.errors,
        }


class EventFilter(ABC):
    """Base class for event filters."""

    def __init__(self, name: str = "", enabled: bool = True) -> None:
        """Initialize the EventFilter."""
        self.name = name or self.__class__.__name__
        self._enabled = enabled
        self._stats = FilterStats(name=self.name)

    @abstractmethod
    def evaluate(self, event_type: str, data: str, **kwargs) -> FilterResult:
        """Evaluate the filter against an event."""
        ...

    @property
    def stats(self) -> FilterStats:
        """Return the filter statistics."""
        return self._stats

    @property
    def is_enabled(self) -> bool:
        """Return whether the filter is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable this filter."""
        self._enabled = True

    def disable(self) -> None:
        """Disable this filter."""
        self._enabled = False


class TypeFilter(EventFilter):
    """Filter events by event type."""

    def __init__(
        self,
        allowed_types: set[str] | None = None,
        denied_types: set[str] | None = None,
        name: str = "type_filter",
    ) -> None:
        """Initialize the TypeFilter."""
        super().__init__(name=name)
        self.allowed_types = allowed_types
        self.denied_types = denied_types or set()

    def evaluate(self, event_type: str, data: str, **kwargs) -> FilterResult:
        """Evaluate whether an event type is allowed."""
        if event_type in self.denied_types:
            return FilterResult.BLOCK
        if self.allowed_types is not None and event_type not in self.allowed_types:
            return FilterResult.BLOCK
        return FilterResult.PASS


class PatternFilter(EventFilter):
    """Filter events by data content pattern (regex)."""

    def __init__(
        self,
        pattern: str,
        action: FilterAction = FilterAction.DENY,
        name: str = "pattern_filter",
    ) -> None:
        """Initialize the PatternFilter."""
        super().__init__(name=name)
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.action = action

    def evaluate(self, event_type: str, data: str, **kwargs) -> FilterResult:
        """Evaluate whether event data matches the pattern."""
        matches = bool(self.pattern.search(data))
        if matches:
            return FilterResult.BLOCK if self.action == FilterAction.DENY else FilterResult.PASS
        return FilterResult.SKIP


class RiskFilter(EventFilter):
    """Filter events by risk level."""

    def __init__(
        self,
        min_risk: int = 0,
        max_risk: int = 100,
        name: str = "risk_filter",
    ) -> None:
        """Initialize the RiskFilter."""
        super().__init__(name=name)
        self.min_risk = min_risk
        self.max_risk = max_risk

    def evaluate(self, event_type: str, data: str, **kwargs) -> FilterResult:
        """Evaluate whether the event risk level is within range."""
        risk = kwargs.get("risk", 0)
        if risk < self.min_risk or risk > self.max_risk:
            return FilterResult.BLOCK
        return FilterResult.PASS


class PredicateFilter(EventFilter):
    """Filter using a custom predicate function."""

    def __init__(
        self,
        predicate: Callable[..., bool],
        name: str = "predicate_filter",
    ) -> None:
        """Initialize the PredicateFilter."""
        super().__init__(name=name)
        self._predicate = predicate

    def evaluate(self, event_type: str, data: str, **kwargs) -> FilterResult:
        """Evaluate using the custom predicate function."""
        try:
            if self._predicate(event_type, data, **kwargs):
                return FilterResult.PASS
            return FilterResult.BLOCK
        except Exception as e:
            log.error("Predicate filter '%s' error: %s", self.name, e)
            return FilterResult.SKIP


class ModuleFilter(EventFilter):
    """Filter events by source module."""

    def __init__(
        self,
        allowed_modules: set[str] | None = None,
        denied_modules: set[str] | None = None,
        name: str = "module_filter",
    ) -> None:
        """Initialize the ModuleFilter."""
        super().__init__(name=name)
        self.allowed_modules = allowed_modules
        self.denied_modules = denied_modules or set()

    def evaluate(self, event_type: str, data: str, **kwargs) -> FilterResult:
        """Evaluate whether the source module is allowed."""
        module = kwargs.get("module", "")
        if module in self.denied_modules:
            return FilterResult.BLOCK
        if self.allowed_modules is not None and module not in self.allowed_modules:
            return FilterResult.BLOCK
        return FilterResult.PASS


class EventFilterChain:
    """Composable chain of event filters.

    Filters are evaluated in order. The chain can operate in two modes:
    - "all_pass" (default): All filters must pass (AND logic)
    - "any_pass": At least one filter must pass (OR logic)

    Usage:
        chain = EventFilterChain()
        chain.add(TypeFilter(denied_types={"RAW_DATA"}))
        chain.add(RiskFilter(min_risk=30))

        if chain.check("IP_ADDRESS", "1.2.3.4", risk=50):
            # Process the event
            pass
    """

    def __init__(self, mode: str = "all_pass", name: str = "default") -> None:
        """Initialize the EventFilterChain."""
        self.mode = mode  # "all_pass" or "any_pass"
        self.name = name
        self._filters: list[EventFilter] = []
        self._lock = threading.Lock()
        self._total_checked = 0
        self._total_passed = 0
        self._total_blocked = 0

    def add(self, f: EventFilter) -> "EventFilterChain":
        """Add a filter to the chain (chainable)."""
        with self._lock:
            self._filters.append(f)
        return self

    def remove(self, filter_name: str) -> bool:
        """Remove a filter by name."""
        with self._lock:
            before = len(self._filters)
            self._filters = [f for f in self._filters if f.name != filter_name]
            return len(self._filters) < before

    def check(self, event_type: str, data: str, **kwargs) -> bool:
        """Check if an event passes all filters.

        Returns True if the event should be processed, False if blocked.
        """
        with self._lock:
            filters = list(self._filters)

        self._total_checked += 1
        passed_any = False

        for f in filters:
            if not f.is_enabled:
                continue

            f._stats.evaluated += 1
            try:
                result = f.evaluate(event_type, data, **kwargs)
            except Exception as e:
                log.error("Filter '%s' error: %s", f.name, e)
                f._stats.errors += 1
                continue

            if result == FilterResult.PASS:
                f._stats.passed += 1
                passed_any = True
            elif result == FilterResult.BLOCK:
                f._stats.blocked += 1
                if self.mode == "all_pass":
                    self._total_blocked += 1
                    return False
            else:  # SKIP
                f._stats.skipped += 1

        if self.mode == "any_pass" and not passed_any:
            self._total_blocked += 1
            return False

        self._total_passed += 1
        return True

    def check_batch(
        self, events: list[dict]
    ) -> list[bool]:
        """Check multiple events. Each dict should have 'event_type' and 'data'."""
        return [
            self.check(
                e.get("event_type", ""),
                e.get("data", ""),
                **{k: v for k, v in e.items() if k not in ("event_type", "data")},
            )
            for e in events
        ]

    @property
    def filter_count(self) -> int:
        """Return the number of filters in the chain."""
        with self._lock:
            return len(self._filters)

    def get_stats(self) -> dict:
        """Get chain statistics."""
        with self._lock:
            return {
                "name": self.name,
                "mode": self.mode,
                "filter_count": len(self._filters),
                "total_checked": self._total_checked,
                "total_passed": self._total_passed,
                "total_blocked": self._total_blocked,
                "filters": [f.stats.to_dict() for f in self._filters],
            }

    def get_filter_names(self) -> list[str]:
        """Return the names of all filters in the chain."""
        with self._lock:
            return [f.name for f in self._filters]

    def reset_stats(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self._total_checked = 0
            self._total_passed = 0
            self._total_blocked = 0
            for f in self._filters:
                f._stats = FilterStats(name=f.name)

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return self.get_stats()
