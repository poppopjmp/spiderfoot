#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         data_retention
# Purpose:      Automated data retention policies for SpiderFoot.
#               Manages lifecycle of scan results, logs, and cached
#               data with configurable age/size/count-based rules.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Data Retention

Configure automated cleanup of old scan data::

    from spiderfoot.data_retention import (
        RetentionPolicy, RetentionManager, RetentionRule,
    )

    manager = RetentionManager()

    # Keep scan results for 90 days
    manager.add_rule(RetentionRule(
        name="scan_results",
        resource="scans",
        max_age_days=90,
    ))

    # Keep at most 50 scans
    manager.add_rule(RetentionRule(
        name="scan_count",
        resource="scans",
        max_count=50,
    ))

    # Dry-run to preview
    preview = manager.preview()

    # Execute cleanup
    result = manager.enforce()
"""

import logging
import os
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("spiderfoot.data_retention")


class RetentionAction(str, Enum):
    """What to do with expired data."""
    DELETE = "delete"
    ARCHIVE = "archive"
    EXPORT_THEN_DELETE = "export_then_delete"


@dataclass
class RetentionRule:
    """A single retention rule."""
    name: str
    resource: str  # "scans", "logs", "cache", "exports", "audit"
    max_age_days: int = 0       # 0 = no age limit
    max_count: int = 0          # 0 = no count limit
    max_size_mb: float = 0.0    # 0 = no size limit
    action: RetentionAction = RetentionAction.DELETE
    enabled: bool = True
    exclude_pattern: str = ""   # Regex or glob for exclusions

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "resource": self.resource,
            "max_age_days": self.max_age_days,
            "max_count": self.max_count,
            "max_size_mb": self.max_size_mb,
            "action": self.action.value,
            "enabled": self.enabled,
            "exclude_pattern": self.exclude_pattern,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RetentionRule":
        action = data.get("action", "delete")
        try:
            action = RetentionAction(action)
        except ValueError:
            action = RetentionAction.DELETE

        return cls(
            name=data.get("name", ""),
            resource=data.get("resource", ""),
            max_age_days=data.get("max_age_days", 0),
            max_count=data.get("max_count", 0),
            max_size_mb=data.get("max_size_mb", 0.0),
            action=action,
            enabled=data.get("enabled", True),
            exclude_pattern=data.get("exclude_pattern", ""),
        )


@dataclass
class RetentionCandidate:
    """An item identified for retention action."""
    resource: str
    identifier: str
    age_days: float = 0.0
    size_bytes: int = 0
    created_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "resource": self.resource,
            "identifier": self.identifier,
            "age_days": round(self.age_days, 1),
            "size_bytes": self.size_bytes,
        }


@dataclass
class RetentionResult:
    """Result of a retention enforcement run."""
    rule_name: str
    candidates_found: int = 0
    items_processed: int = 0
    items_failed: int = 0
    bytes_freed: int = 0
    dry_run: bool = False
    details: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "rule_name": self.rule_name,
            "candidates_found": self.candidates_found,
            "items_processed": self.items_processed,
            "items_failed": self.items_failed,
            "bytes_freed": self.bytes_freed,
            "dry_run": self.dry_run,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Resource Adapters
# ---------------------------------------------------------------------------

class ResourceAdapter:
    """Interface for listing and removing resources."""

    def list_items(self, resource: str) -> List[RetentionCandidate]:
        """List all items for a resource type."""
        raise NotImplementedError

    def delete_item(self, candidate: RetentionCandidate) -> bool:
        raise NotImplementedError

    def archive_item(self, candidate: RetentionCandidate) -> bool:
        raise NotImplementedError


class FileResourceAdapter(ResourceAdapter):
    """Adapter for file-based resources (logs, exports, cache)."""

    def __init__(self, directories: Optional[Dict[str, str]] = None):
        self._dirs = directories or {}

    def set_directory(self, resource: str, path: str) -> None:
        self._dirs[resource] = path

    def list_items(self, resource: str) -> List[RetentionCandidate]:
        directory = self._dirs.get(resource, "")
        if not directory or not os.path.isdir(directory):
            return []

        items = []
        now = time.time()
        for entry in os.scandir(directory):
            if entry.is_file():
                stat = entry.stat()
                age = (now - stat.st_mtime) / 86400.0
                items.append(RetentionCandidate(
                    resource=resource,
                    identifier=entry.path,
                    age_days=age,
                    size_bytes=stat.st_size,
                    created_at=stat.st_mtime,
                ))

        return sorted(items, key=lambda c: c.created_at)

    def delete_item(self, candidate: RetentionCandidate) -> bool:
        try:
            if os.path.exists(candidate.identifier):
                os.remove(candidate.identifier)
                return True
        except Exception as e:
            log.error("Failed to delete %s: %s",
                     candidate.identifier, e)
        return False

    def archive_item(self, candidate: RetentionCandidate) -> bool:
        # Move to .archive subdirectory
        directory = os.path.dirname(candidate.identifier)
        archive_dir = os.path.join(directory, ".archive")
        os.makedirs(archive_dir, exist_ok=True)

        dest = os.path.join(archive_dir,
                           os.path.basename(candidate.identifier))
        try:
            os.rename(candidate.identifier, dest)
            return True
        except Exception as e:
            log.error("Failed to archive %s: %s",
                     candidate.identifier, e)
            return False


class InMemoryResourceAdapter(ResourceAdapter):
    """Adapter that operates on in-memory item lists (for testing)."""

    def __init__(self):
        self._items: Dict[str, List[RetentionCandidate]] = {}

    def add_items(self, resource: str,
                  items: List[RetentionCandidate]) -> None:
        self._items.setdefault(resource, []).extend(items)

    def list_items(self, resource: str) -> List[RetentionCandidate]:
        items = self._items.get(resource, [])
        return sorted(items, key=lambda c: c.created_at)

    def delete_item(self, candidate: RetentionCandidate) -> bool:
        items = self._items.get(candidate.resource, [])
        for i, item in enumerate(items):
            if item.identifier == candidate.identifier:
                items.pop(i)
                return True
        return False

    def archive_item(self, candidate: RetentionCandidate) -> bool:
        return self.delete_item(candidate)


# ---------------------------------------------------------------------------
# Retention Manager
# ---------------------------------------------------------------------------

class RetentionManager:
    """Manages and enforces data retention policies."""

    def __init__(self, adapter: Optional[ResourceAdapter] = None):
        self._rules: Dict[str, RetentionRule] = {}
        self._adapter = adapter or InMemoryResourceAdapter()
        self._lock = threading.Lock()
        self._history: List[RetentionResult] = []

    @property
    def adapter(self) -> ResourceAdapter:
        return self._adapter

    @adapter.setter
    def adapter(self, value: ResourceAdapter) -> None:
        self._adapter = value

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: RetentionRule) -> None:
        self._rules[rule.name] = rule

    def remove_rule(self, name: str) -> bool:
        return self._rules.pop(name, None) is not None

    def get_rule(self, name: str) -> Optional[RetentionRule]:
        return self._rules.get(name)

    def list_rules(self) -> List[RetentionRule]:
        return list(self._rules.values())

    # ------------------------------------------------------------------
    # Enforcement
    # ------------------------------------------------------------------

    def preview(self, rule_name: Optional[str] = None
                ) -> List[RetentionResult]:
        """Preview what would be cleaned up (dry run)."""
        return self._run(dry_run=True, rule_name=rule_name)

    def enforce(self, rule_name: Optional[str] = None
                ) -> List[RetentionResult]:
        """Execute retention policies."""
        return self._run(dry_run=False, rule_name=rule_name)

    def _run(self, dry_run: bool = True,
             rule_name: Optional[str] = None) -> List[RetentionResult]:
        rules = []
        if rule_name:
            rule = self._rules.get(rule_name)
            if rule:
                rules = [rule]
        else:
            rules = [r for r in self._rules.values() if r.enabled]

        results = []
        for rule in rules:
            result = self._enforce_rule(rule, dry_run=dry_run)
            results.append(result)
            if not dry_run:
                self._history.append(result)

        return results

    def _enforce_rule(self, rule: RetentionRule,
                      dry_run: bool = True) -> RetentionResult:
        result = RetentionResult(
            rule_name=rule.name,
            dry_run=dry_run,
        )

        try:
            items = self._adapter.list_items(rule.resource)
        except Exception as e:
            result.details.append(f"Error listing items: {e}")
            return result

        candidates = self._apply_rule_criteria(rule, items)
        result.candidates_found = len(candidates)

        for candidate in candidates:
            if dry_run:
                result.items_processed += 1
                result.bytes_freed += candidate.size_bytes
                result.details.append(
                    f"Would {rule.action.value}: "
                    f"{candidate.identifier} "
                    f"(age={candidate.age_days:.1f}d, "
                    f"size={candidate.size_bytes}B)")
            else:
                success = self._execute_action(rule, candidate)
                if success:
                    result.items_processed += 1
                    result.bytes_freed += candidate.size_bytes
                    result.details.append(
                        f"{rule.action.value}: {candidate.identifier}")
                else:
                    result.items_failed += 1
                    result.details.append(
                        f"FAILED {rule.action.value}: "
                        f"{candidate.identifier}")

        return result

    def _apply_rule_criteria(self, rule: RetentionRule,
                             items: List[RetentionCandidate]
                             ) -> List[RetentionCandidate]:
        """Determine which items should be cleaned up."""
        candidates = []

        if rule.exclude_pattern:
            import re
            try:
                pattern = re.compile(rule.exclude_pattern)
                items = [i for i in items
                        if not pattern.search(i.identifier)]
            except re.error:
                pass

        # Age-based
        if rule.max_age_days > 0:
            for item in items:
                if item.age_days > rule.max_age_days:
                    candidates.append(item)

        # Count-based (remove oldest first)
        if rule.max_count > 0 and len(items) > rule.max_count:
            excess = len(items) - rule.max_count
            oldest = sorted(items, key=lambda c: c.created_at)[:excess]
            for item in oldest:
                if item not in candidates:
                    candidates.append(item)

        # Size-based
        if rule.max_size_mb > 0:
            total_bytes = sum(i.size_bytes for i in items)
            max_bytes = int(rule.max_size_mb * 1024 * 1024)
            if total_bytes > max_bytes:
                # Remove oldest until under limit
                sorted_items = sorted(
                    items, key=lambda c: c.created_at)
                freed = 0
                for item in sorted_items:
                    if total_bytes - freed <= max_bytes:
                        break
                    if item not in candidates:
                        candidates.append(item)
                    freed += item.size_bytes

        return candidates

    def _execute_action(self, rule: RetentionRule,
                        candidate: RetentionCandidate) -> bool:
        if rule.action == RetentionAction.DELETE:
            return self._adapter.delete_item(candidate)
        elif rule.action == RetentionAction.ARCHIVE:
            return self._adapter.archive_item(candidate)
        elif rule.action == RetentionAction.EXPORT_THEN_DELETE:
            # Archive first, then it's considered deleted
            if self._adapter.archive_item(candidate):
                return True
            return False
        return False

    # ------------------------------------------------------------------
    # History & stats
    # ------------------------------------------------------------------

    @property
    def history(self) -> List[RetentionResult]:
        return list(self._history)

    @property
    def stats(self) -> dict:
        total_processed = sum(r.items_processed for r in self._history)
        total_freed = sum(r.bytes_freed for r in self._history)
        return {
            "rules": len(self._rules),
            "enforcement_runs": len(self._history),
            "total_items_processed": total_processed,
            "total_bytes_freed": total_freed,
        }
