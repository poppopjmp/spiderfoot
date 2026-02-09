"""
Module output validation.

Validates that events emitted by modules via ``notifyListeners()`` match
the event types declared in their ``producedEvents()`` list.

This is a **runtime safety net** — catching misconfigured modules that
emit undeclared event types, which can break downstream consumers and
produce confusing correlation results.

Modes:
    warn   — Log a warning but allow the event (default, safe for prod)
    strict — Log a warning AND raise an error (for CI/testing)
    off    — No validation overhead at all

Configuration:
    SF_MODULE_OUTPUT_VALIDATION — "warn" | "strict" | "off" (default: "warn")

Usage::

    from spiderfoot.module_output_validator import get_output_validator
    validator = get_output_validator()
    validator.check(module, event)
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger("spiderfoot.module_output_validator")


class UndeclaredEventError(RuntimeError):
    """Raised in strict mode when a module emits an undeclared event type."""
    pass


@dataclass
class ValidationStats:
    """Per-module validation statistics."""
    total_events: int = 0
    valid_events: int = 0
    undeclared_events: int = 0
    undeclared_types: Set[str] = field(default_factory=set)


class ModuleOutputValidator:
    """Validates that module output events match producedEvents() declarations.

    Thread-safe — modules run in concurrent threads.
    """

    # Event types that are always allowed regardless of declarations
    # (ROOT is the seed event, INTERNAL_* are framework-level)
    _ALWAYS_ALLOWED: frozenset = frozenset({
        "ROOT",
        "INITIAL_TARGET",
    })

    def __init__(self, mode: str = "warn"):
        """
        Args:
            mode: "warn", "strict", or "off"
        """
        self._mode = mode.lower()
        if self._mode not in ("warn", "strict", "off"):
            log.warning("Unknown output validation mode '%s', defaulting to 'warn'", mode)
            self._mode = "warn"

        self._lock = Lock()
        self._stats: Dict[str, ValidationStats] = defaultdict(ValidationStats)
        # Cache of producedEvents per module class to avoid repeated calls
        self._produced_cache: Dict[str, Set[str]] = {}

        if self._mode == "off":
            log.debug("Module output validation is disabled")
        else:
            log.info("Module output validation enabled in '%s' mode", self._mode)

    @property
    def mode(self) -> str:
        return self._mode

    def check(self, module: Any, event: Any) -> bool:
        """Validate that *event* is a declared output of *module*.

        Args:
            module: Module instance (has ``__module__``, ``producedEvents()``)
            event:  SpiderFootEvent instance (has ``eventType``)

        Returns:
            True if the event is valid (or validation is off), False otherwise.
        """
        if self._mode == "off":
            return True

        event_type = getattr(event, "eventType", None)
        if event_type is None:
            return True  # Not a proper event — skip

        if event_type in self._ALWAYS_ALLOWED:
            return True

        module_name = self._get_module_name(module)
        allowed = self._get_produced_events(module_name, module)

        with self._lock:
            stats = self._stats[module_name]
            stats.total_events += 1

        if event_type in allowed:
            with self._lock:
                stats.valid_events += 1
            return True

        # Undeclared event type
        with self._lock:
            stats.undeclared_events += 1
            stats.undeclared_types.add(event_type)

        log.warning(
            "Module %s emitted undeclared event type '%s' "
            "(declared: %s)",
            module_name, event_type,
            ", ".join(sorted(allowed)) if allowed else "<none>",
        )

        if self._mode == "strict":
            raise UndeclaredEventError(
                f"Module {module_name} emitted undeclared event type "
                f"'{event_type}'. Declared: {sorted(allowed)}"
            )

        return False

    def get_stats(self, module_name: str | None = None) -> Dict[str, Any]:
        """Return validation statistics.

        Args:
            module_name: If provided, return stats for that module only.

        Returns:
            Dict with per-module or aggregate statistics.
        """
        with self._lock:
            if module_name:
                s = self._stats.get(module_name)
                if not s:
                    return {}
                return {
                    "module": module_name,
                    "total": s.total_events,
                    "valid": s.valid_events,
                    "undeclared": s.undeclared_events,
                    "undeclared_types": sorted(s.undeclared_types),
                }
            # Aggregate
            result = {}
            for name, s in self._stats.items():
                if s.undeclared_events > 0:
                    result[name] = {
                        "total": s.total_events,
                        "valid": s.valid_events,
                        "undeclared": s.undeclared_events,
                        "undeclared_types": sorted(s.undeclared_types),
                    }
            return result

    def get_all_stats(self) -> Dict[str, Any]:
        """Return full stats for every tracked module."""
        with self._lock:
            return {
                name: {
                    "total": s.total_events,
                    "valid": s.valid_events,
                    "undeclared": s.undeclared_events,
                    "undeclared_types": sorted(s.undeclared_types),
                }
                for name, s in self._stats.items()
            }

    def reset_stats(self) -> None:
        """Clear all collected statistics."""
        with self._lock:
            self._stats.clear()
            self._produced_cache.clear()

    def _get_module_name(self, module: Any) -> str:
        """Extract a readable module name."""
        name = getattr(module, "__module__", None)
        if name:
            return name
        cls = type(module)
        return f"{cls.__module__}.{cls.__qualname__}" if hasattr(cls, "__module__") else cls.__name__

    def _get_produced_events(self, module_name: str, module: Any) -> Set[str]:
        """Get (and cache) the set of event types a module declares it produces."""
        if module_name in self._produced_cache:
            return self._produced_cache[module_name]

        produced: Set[str] = set()
        try:
            fn = getattr(module, "producedEvents", None)
            if callable(fn):
                result = fn()
                if isinstance(result, (list, tuple, set, frozenset)):
                    produced = set(result)
        except Exception as exc:
            log.debug("Failed to get producedEvents from %s: %s", module_name, exc)

        # Cache it
        with self._lock:
            self._produced_cache[module_name] = produced

        return produced


# ── Singleton ────────────────────────────────────────────────────────

_instance: Optional[ModuleOutputValidator] = None
_instance_lock = Lock()


def get_output_validator() -> ModuleOutputValidator:
    """Return the singleton ModuleOutputValidator instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                mode = os.environ.get("SF_MODULE_OUTPUT_VALIDATION", "warn")
                _instance = ModuleOutputValidator(mode=mode)
    return _instance
