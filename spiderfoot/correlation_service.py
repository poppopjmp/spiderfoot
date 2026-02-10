#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         correlation_service
# Purpose:      Standalone correlation service for SpiderFoot.
#               Decouples correlation execution from the scanner, supports
#               real-time event-driven triggers via EventBus, and can run
#               as a standalone microservice.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Correlation Service

Provides a service-oriented facade around the existing RuleExecutor
correlation engine, adding:

    - Real-time event-driven correlation via EventBus subscription
    - Scheduled batch correlation for completed scans
    - Integration with DataService (no direct dbh dependency)
    - Prometheus metrics for correlation operations
    - Independent lifecycle (can run as standalone microservice)

Usage (in-process)::

    from spiderfoot.correlation_service import CorrelationService
    svc = CorrelationService.from_config(sf_config)
    svc.start()
    # Trigger correlation for a scan
    results = svc.run_for_scan(scan_id)
    svc.stop()

Usage (microservice)::

    python -m spiderfoot.service_runner --service correlation
"""

import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("spiderfoot.correlation_service")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class CorrelationTrigger(Enum):
    """When correlations should run."""
    MANUAL = "manual"          # Only on explicit request
    ON_SCAN_COMPLETE = "scan"  # After each scan finishes
    REALTIME = "realtime"      # On each event (streaming)


@dataclass
class CorrelationServiceConfig:
    """Configuration for the CorrelationService."""

    # Path to YAML rule files
    rules_dir: str = "correlations"

    # Trigger mode
    trigger: CorrelationTrigger = CorrelationTrigger.ON_SCAN_COMPLETE

    # For realtime mode: batch window (seconds) before evaluating rules
    batch_window: float = 5.0

    # Maximum concurrent correlation evaluations
    max_workers: int = 2

    # Whether to subscribe to event bus for scan completion events
    subscribe_events: bool = True

    # Rule IDs to exclude
    excluded_rules: List[str] = field(default_factory=list)

    # Risk levels to include (empty = all)
    risk_filter: List[str] = field(default_factory=list)

    @classmethod
    def from_config(cls, opts: dict) -> "CorrelationServiceConfig":
        trigger_str = opts.get("_correlation_trigger", "scan")
        try:
            trigger = CorrelationTrigger(trigger_str)
        except ValueError:
            trigger = CorrelationTrigger.ON_SCAN_COMPLETE

        rules_dir = opts.get(
            "_correlation_rules_dir",
            os.environ.get("SF_CORRELATION_RULES_DIR", "correlations")
        )

        excluded = opts.get("_correlation_excluded_rules", "")
        if isinstance(excluded, str):
            excluded = [r.strip() for r in excluded.split(",") if r.strip()]

        risk = opts.get("_correlation_risk_filter", "")
        if isinstance(risk, str):
            risk = [r.strip() for r in risk.split(",") if r.strip()]

        return cls(
            rules_dir=rules_dir,
            trigger=trigger,
            batch_window=float(opts.get("_correlation_batch_window", 5.0)),
            max_workers=int(opts.get("_correlation_max_workers", 2)),
            subscribe_events=opts.get("_correlation_subscribe", True),
            excluded_rules=excluded,
            risk_filter=risk,
        )


# ---------------------------------------------------------------------------
# Correlation Result
# ---------------------------------------------------------------------------

@dataclass
class CorrelationResult:
    """A single correlation finding."""
    rule_id: str
    rule_name: str
    headline: str
    risk: str
    scan_id: str
    event_count: int
    events: List[str] = field(default_factory=list)  # event hashes
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Correlation Service
# ---------------------------------------------------------------------------

class CorrelationService:
    """Service-oriented wrapper around RuleExecutor.

    Manages rule loading, event-driven triggers, and batch execution.
    """

    def __init__(self, config: CorrelationServiceConfig):
        self.config = config
        self._rules: List[dict] = []
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._queue: queue.Queue = queue.Queue()
        self._event_bus_sub = None
        self._results_cache: Dict[str, List[CorrelationResult]] = {}
        self._callbacks: List[Callable[[CorrelationResult], None]] = []

    @classmethod
    def from_config(cls, opts: dict) -> "CorrelationService":
        config = CorrelationServiceConfig.from_config(opts)
        return cls(config)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the correlation service."""
        if self._running:
            return

        self._load_rules()
        self._running = True

        # Start worker thread for processing correlation requests
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="correlation-worker",
            daemon=True,
        )
        self._worker_thread.start()

        # Subscribe to event bus if configured
        if self.config.subscribe_events:
            self._subscribe_events()

        log.info("CorrelationService started (trigger=%s, rules=%d)",
                 self.config.trigger.value, len(self._rules))

    def stop(self) -> None:
        """Stop the correlation service."""
        if not self._running:
            return

        self._running = False
        self._queue.put(None)  # Poison pill

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10.0)

        self._unsubscribe_events()

        log.info("CorrelationService stopped")

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def _load_rules(self) -> None:
        """Load correlation rules from the rules directory."""
        rules_dir = self.config.rules_dir

        if not os.path.isdir(rules_dir):
            log.warning("Correlation rules directory not found: %s",
                        rules_dir)
            self._rules = []
            return

        try:
            from spiderfoot.correlation.rule_loader import RuleLoader
            loader = RuleLoader(rules_dir)
            loaded = loader.load_rules()

            # Apply filters
            filtered = []
            for rule in loaded:
                rule_id = rule.get("id", "")
                if rule_id in self.config.excluded_rules:
                    continue
                risk = rule.get("meta", {}).get("risk", "")
                if self.config.risk_filter and risk not in self.config.risk_filter:
                    continue
                filtered.append(rule)

            self._rules = filtered
            log.info("Loaded %d correlation rules (filtered from %d)",
                     len(filtered), len(loaded))

        except ImportError:
            # Fallback to raw loader
            try:
                from spiderfoot.helpers import SpiderFootHelpers
                raw_rules = SpiderFootHelpers.loadCorrelationRulesRaw(
                    rules_dir)
                self._rules = raw_rules or []
            except Exception as e:
                log.error("Failed to load correlation rules: %s", e)
                self._rules = []

    def reload_rules(self) -> int:
        """Reload rules from disk. Returns count of loaded rules."""
        self._load_rules()
        return len(self._rules)

    @property
    def rules(self) -> List[dict]:
        """Currently loaded rules."""
        return list(self._rules)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    # ------------------------------------------------------------------
    # Rule CRUD  (Cycle 26)
    # ------------------------------------------------------------------

    def get_rule(self, rule_id: str) -> Optional[dict]:
        """Return a single rule by its ``id``, or ``None``."""
        for r in self._rules:
            if r.get("id") == rule_id:
                return dict(r)
        return None

    def add_rule(self, rule: dict) -> dict:
        """Add a rule dict (must contain ``id``).

        Returns the rule as stored.
        """
        import uuid as _uuid

        rule = dict(rule)
        if "id" not in rule or not rule["id"]:
            rule["id"] = str(_uuid.uuid4())
        with self._lock:
            self._rules.append(rule)
        log.info("Added correlation rule %s", rule["id"])
        return rule

    def update_rule(self, rule_id: str, updates: dict) -> Optional[dict]:
        """Merge *updates* into the rule identified by *rule_id*.

        Returns the updated rule dict or ``None`` if not found.
        """
        with self._lock:
            for i, r in enumerate(self._rules):
                if r.get("id") == rule_id:
                    r.update(updates)
                    r["id"] = rule_id  # prevent id overwrite
                    self._rules[i] = r
                    log.info("Updated correlation rule %s", rule_id)
                    return dict(r)
        return None

    def delete_rule(self, rule_id: str) -> bool:
        """Remove a rule by id.  Returns ``True`` if removed."""
        with self._lock:
            before = len(self._rules)
            self._rules = [r for r in self._rules if r.get("id") != rule_id]
            removed = len(self._rules) < before
        if removed:
            log.info("Deleted correlation rule %s", rule_id)
        return removed

    def filter_rules(
        self,
        *,
        risk: Optional[str] = None,
        enabled: Optional[bool] = None,
        tag: Optional[str] = None,
    ) -> List[dict]:
        """Return rules matching optional filters."""
        out: List[dict] = []
        for r in self._rules:
            if risk and r.get("risk", r.get("meta", {}).get("risk", "")).upper() != risk.upper():
                continue
            if enabled is not None and r.get("enabled", True) != enabled:
                continue
            if tag and tag not in r.get("tags", []):
                continue
            out.append(dict(r))
        return out

    # ------------------------------------------------------------------
    # Correlation execution
    # ------------------------------------------------------------------

    def run_for_scan(self, scan_id: str,
                     rule_ids: Optional[List[str]] = None,
                     dbh=None) -> List[CorrelationResult]:
        """Run correlations for a specific scan.

        Args:
            scan_id: The scan to correlate.
            rule_ids: Optional subset of rule IDs to run.
            dbh: Database handle (uses DataService if not provided).

        Returns:
            List of CorrelationResult objects.
        """
        rules = self._rules
        if rule_ids:
            rules = [r for r in rules if r.get("id") in rule_ids]

        if not rules:
            log.info("No rules to run for scan %s", scan_id)
            return []

        results = []

        # Get DB handle
        if dbh is None:
            dbh = self._get_dbh()

        if dbh is None:
            log.error("No database handle available for correlation")
            return []

        try:
            from spiderfoot.correlation.rule_executor import RuleExecutor

            executor = RuleExecutor(dbh, rules, scan_ids=[scan_id])
            raw_results = executor.run()

            for raw in (raw_results or []):
                cr = CorrelationResult(
                    rule_id=raw.get("rule_id", ""),
                    rule_name=raw.get("rule_name", ""),
                    headline=raw.get("title", raw.get("headline", "")),
                    risk=raw.get("risk", ""),
                    scan_id=scan_id,
                    event_count=raw.get("event_count", 0),
                    events=raw.get("events", []),
                )
                results.append(cr)
                self._notify_callbacks(cr)

            # Cache results
            self._results_cache[scan_id] = results

            self._record_metrics(scan_id, results)

            log.info("Correlation complete for scan %s: %d results",
                     scan_id, len(results))

        except ImportError:
            log.warning("Correlation engine not available "
                        "(spiderfoot.correlation not found)")
        except Exception as e:
            log.error("Correlation failed for scan %s: %s", scan_id, e)

        return results

    def submit_scan(self, scan_id: str,
                    rule_ids: Optional[List[str]] = None) -> None:
        """Submit a scan for async correlation (queued)."""
        self._queue.put(("scan", scan_id, rule_ids))

    def get_results(self, scan_id: str) -> List[CorrelationResult]:
        """Get cached results for a scan."""
        return self._results_cache.get(scan_id, [])

    def clear_cache(self, scan_id: Optional[str] = None) -> None:
        """Clear result cache."""
        if scan_id:
            self._results_cache.pop(scan_id, None)
        else:
            self._results_cache.clear()

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_result(self, callback: Callable[[CorrelationResult], None]) -> None:
        """Register a callback for correlation results."""
        self._callbacks.append(callback)

    def _notify_callbacks(self, result: CorrelationResult) -> None:
        for cb in self._callbacks:
            try:
                cb(result)
            except Exception as e:
                log.error("Callback error: %s", e)

    # ------------------------------------------------------------------
    # Event bus integration
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        """Subscribe to event bus for scan completion events."""
        try:
            from spiderfoot.service_registry import ServiceRegistry
            registry = ServiceRegistry.get_instance()
            event_bus = registry.get_optional("event_bus")
            if event_bus is None:
                return

            self._event_bus_sub = event_bus.subscribe(
                "scan.completed",
                self._on_scan_completed,
            )
            log.debug("Subscribed to scan.completed events")

        except Exception as e:
            log.debug("Event bus subscription skipped: %s", e)

    def _unsubscribe_events(self) -> None:
        """Unsubscribe from event bus."""
        if self._event_bus_sub:
            try:
                from spiderfoot.service_registry import ServiceRegistry
                registry = ServiceRegistry.get_instance()
                event_bus = registry.get_optional("event_bus")
                if event_bus:
                    event_bus.unsubscribe(self._event_bus_sub)
            except Exception as e:
                log.debug("optional event_bus lookup failed: %s", e)
            self._event_bus_sub = None

    def _on_scan_completed(self, event: dict) -> None:
        """Handle scan completion event."""
        if self.config.trigger != CorrelationTrigger.ON_SCAN_COMPLETE:
            return

        scan_id = None
        if isinstance(event, dict):
            scan_id = event.get("scan_id") or event.get("data", {}).get("scan_id")
        elif hasattr(event, "data"):
            scan_id = getattr(event.data, "scan_id", None) if hasattr(event.data, "scan_id") else None

        if scan_id:
            log.info("Auto-triggering correlation for completed scan %s",
                     scan_id)
            self.submit_scan(scan_id)

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Background worker that processes queued correlation requests."""
        while self._running:
            try:
                item = self._queue.get(timeout=1.0)
                if item is None:
                    break

                kind, scan_id, rule_ids = item
                if kind == "scan":
                    self.run_for_scan(scan_id, rule_ids)

            except queue.Empty:
                continue
            except Exception as e:
                log.error("Correlation worker error: %s", e)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_dbh(self):
        """Get a database handle via DataService or ServiceRegistry."""
        try:
            from spiderfoot.service_registry import ServiceRegistry
            registry = ServiceRegistry.get_instance()
            data_svc = registry.get_optional("data")
            if data_svc and hasattr(data_svc, "dbh"):
                return data_svc.dbh
        except Exception as e:
            log.debug("optional data service lookup failed: %s", e)

        # Fallback: try to create a direct DB handle
        try:
            from spiderfoot import SpiderFootDb
            opts = {"__database": os.environ.get(
                "SF_DATABASE", "spiderfoot.db")}
            return SpiderFootDb(opts)
        except Exception as e:
            log.error("Cannot obtain database handle: %s", e)
            return None

    def _record_metrics(self, scan_id: str,
                        results: List[CorrelationResult]) -> None:
        """Record Prometheus metrics."""
        try:
            from spiderfoot.metrics import Counter, get_registry

            registry = get_registry()

            # Find or create counter
            corr_counter = None
            for m in registry._metrics.values():
                if m.name == "sf_correlations_total":
                    corr_counter = m
                    break

            if corr_counter is None:
                corr_counter = Counter(
                    "sf_correlations_total",
                    "Correlation results produced",
                    label_names=["risk"],
                )
                registry.register(corr_counter)

            for r in results:
                corr_counter.labels(risk=r.risk).inc()

        except Exception:
            pass

    # ------------------------------------------------------------------
    # Status / API
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """Get service status."""
        return {
            "running": self._running,
            "trigger": self.config.trigger.value,
            "rule_count": len(self._rules),
            "cached_scans": len(self._results_cache),
            "queue_size": self._queue.qsize(),
        }

    def to_dict(self) -> dict:
        """Serialize status for API responses."""
        return self.status()


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_instance: Optional[CorrelationService] = None
_instance_lock = threading.Lock()


def get_correlation_service(opts: Optional[dict] = None) -> CorrelationService:
    """Get or create the singleton CorrelationService."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CorrelationService.from_config(opts or {})
    return _instance
