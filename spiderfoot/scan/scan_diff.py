#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         scan_diff
# Purpose:      Compare SpiderFoot scan results to detect changes
#               between runs. Identifies new, removed, and changed
#               findings for continuous monitoring workflows.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
SpiderFoot Scan Diff

Compare two scan results to find changes::

    from spiderfoot.scan_diff import ScanDiff, ScanSnapshot

    snap_a = ScanSnapshot.from_events(scan_a_events)
    snap_b = ScanSnapshot.from_events(scan_b_events)

    diff = ScanDiff.compare(snap_a, snap_b)
    print(f"Added: {len(diff.added)}")
    print(f"Removed: {len(diff.removed)}")
    print(f"Changed: {len(diff.changed)}")
    print(diff.summary())
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.scan_diff")


class ChangeType(str, Enum):
    """Type of change detected between scans."""
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


@dataclass
class Finding:
    """A normalized scan finding for comparison.

    Findings are identified by (event_type, data) tuples.
    The module source is tracked but not used for identity.
    """
    event_type: str
    data: str
    module: str = ""
    source_event: str = ""
    confidence: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Unique identity key for this finding."""
        return f"{self.event_type}:{self.data}"

    @property
    def fingerprint(self) -> str:
        """Hash of significant attributes for change detection."""
        raw = f"{self.event_type}|{self.data}|{self.confidence}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "module": self.module,
            "source_event": self.source_event,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class Change:
    """A single change between two scans."""
    change_type: ChangeType
    finding: Finding
    previous: Finding | None = None
    detail: str = ""

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        d = {
            "change_type": self.change_type.value,
            "finding": self.finding.to_dict(),
            "detail": self.detail,
        }
        if self.previous:
            d["previous"] = self.previous.to_dict()
        return d


@dataclass
class ScanSnapshot:
    """A snapshot of scan results for comparison."""
    scan_id: str = ""
    target: str = ""
    timestamp: float = field(default_factory=time.time)
    findings: list[Finding] = field(default_factory=list)

    def _index(self) -> dict[str, Finding]:
        """Build a lookup index by finding key."""
        index: dict[str, Finding] = {}
        for f in self.findings:
            index[f.key] = f
        return index

    @property
    def finding_count(self) -> int:
        """Return the number of findings in the snapshot."""
        return len(self.findings)

    @property
    def event_types(self) -> set[str]:
        """Return the set of distinct event types in the snapshot."""
        return {f.event_type for f in self.findings}

    def by_type(self, event_type: str) -> list[Finding]:
        """Get findings of a specific event type."""
        return [f for f in self.findings
                if f.event_type == event_type]

    @classmethod
    def from_events(cls, events: list[dict], *,
                    scan_id: str = "",
                    target: str = "") -> "ScanSnapshot":
        """Create a snapshot from raw event dictionaries.

        Expected format: {"type": "...", "data": "...", ...}
        """
        findings = []
        for event in events:
            event_type = (event.get("type") or
                          event.get("event_type") or
                          event.get("generated_by", ""))
            data = event.get("data", "")

            if not event_type or not data:
                continue

            findings.append(Finding(
                event_type=event_type,
                data=str(data),
                module=event.get("module", ""),
                source_event=event.get("source_event", ""),
                confidence=event.get("confidence", 100),
                metadata={k: v for k, v in event.items()
                         if k not in ("type", "event_type", "data",
                                     "module", "source_event",
                                     "generated_by", "confidence")},
            ))

        return cls(
            scan_id=scan_id,
            target=target,
            findings=findings,
        )

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "scan_id": self.scan_id,
            "target": self.target,
            "timestamp": self.timestamp,
            "finding_count": self.finding_count,
            "findings": [f.to_dict() for f in self.findings],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScanSnapshot":
        """Create a ScanSnapshot from a dictionary."""
        findings = [
            Finding(
                event_type=f["event_type"],
                data=f["data"],
                module=f.get("module", ""),
                source_event=f.get("source_event", ""),
                confidence=f.get("confidence", 100),
                metadata=f.get("metadata", {}),
            )
            for f in data.get("findings", [])
        ]
        return cls(
            scan_id=data.get("scan_id", ""),
            target=data.get("target", ""),
            timestamp=data.get("timestamp", time.time()),
            findings=findings,
        )


@dataclass
class DiffResult:
    """Result of comparing two scan snapshots."""
    baseline_id: str = ""
    current_id: str = ""
    target: str = ""
    timestamp: float = field(default_factory=time.time)
    added: list[Change] = field(default_factory=list)
    removed: list[Change] = field(default_factory=list)
    changed: list[Change] = field(default_factory=list)
    unchanged_count: int = 0

    @property
    def total_changes(self) -> int:
        """Return the total number of changes detected."""
        return len(self.added) + len(self.removed) + len(self.changed)

    @property
    def has_changes(self) -> bool:
        """Check whether any changes were detected."""
        return self.total_changes > 0

    def changes_by_type(self) -> dict[str, list[Change]]:
        """Group all changes by event type."""
        by_type: dict[str, list[Change]] = {}
        for change in self.added + self.removed + self.changed:
            et = change.finding.event_type
            by_type.setdefault(et, []).append(change)
        return by_type

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"Scan Diff: {self.baseline_id} → {self.current_id}",
            f"Target: {self.target}",
            f"",
            f"  Added:     {len(self.added)}",
            f"  Removed:   {len(self.removed)}",
            f"  Changed:   {len(self.changed)}",
            f"  Unchanged: {self.unchanged_count}",
            f"  Total changes: {self.total_changes}",
        ]

        if self.added:
            lines.append("")
            lines.append("New findings:")
            for c in self.added[:20]:
                lines.append(
                    f"  + [{c.finding.event_type}] {c.finding.data[:80]}")
            if len(self.added) > 20:
                lines.append(f"  ... and {len(self.added) - 20} more")

        if self.removed:
            lines.append("")
            lines.append("Removed findings:")
            for c in self.removed[:20]:
                lines.append(
                    f"  - [{c.finding.event_type}] {c.finding.data[:80]}")
            if len(self.removed) > 20:
                lines.append(f"  ... and {len(self.removed) - 20} more")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "baseline_id": self.baseline_id,
            "current_id": self.current_id,
            "target": self.target,
            "timestamp": self.timestamp,
            "summary": {
                "added": len(self.added),
                "removed": len(self.removed),
                "changed": len(self.changed),
                "unchanged": self.unchanged_count,
            },
            "added": [c.to_dict() for c in self.added],
            "removed": [c.to_dict() for c in self.removed],
            "changed": [c.to_dict() for c in self.changed],
        }


class ScanDiff:
    """Compare two scan snapshots and produce a diff."""

    @staticmethod
    def compare(baseline: ScanSnapshot,
                current: ScanSnapshot, *,
                ignore_types: set[str] | None = None
                ) -> DiffResult:
        """Compare baseline and current scan snapshots.

        Args:
            baseline: The reference (older) scan.
            current: The new scan to compare against baseline.
            ignore_types: Event types to exclude from comparison.
        """
        ignore = ignore_types or set()

        baseline_idx = {
            k: v for k, v in baseline._index().items()
            if v.event_type not in ignore
        }
        current_idx = {
            k: v for k, v in current._index().items()
            if v.event_type not in ignore
        }

        baseline_keys = set(baseline_idx.keys())
        current_keys = set(current_idx.keys())

        added_keys = current_keys - baseline_keys
        removed_keys = baseline_keys - current_keys
        common_keys = baseline_keys & current_keys

        result = DiffResult(
            baseline_id=baseline.scan_id,
            current_id=current.scan_id,
            target=current.target or baseline.target,
        )

        # Added
        for key in sorted(added_keys):
            finding = current_idx[key]
            result.added.append(Change(
                change_type=ChangeType.ADDED,
                finding=finding,
                detail=f"New {finding.event_type} finding",
            ))

        # Removed
        for key in sorted(removed_keys):
            finding = baseline_idx[key]
            result.removed.append(Change(
                change_type=ChangeType.REMOVED,
                finding=finding,
                detail=f"No longer detected: {finding.event_type}",
            ))

        # Changed / Unchanged
        unchanged = 0
        for key in sorted(common_keys):
            old = baseline_idx[key]
            new = current_idx[key]

            if old.fingerprint != new.fingerprint:
                result.changed.append(Change(
                    change_type=ChangeType.CHANGED,
                    finding=new,
                    previous=old,
                    detail=f"Changed in {new.event_type}",
                ))
            else:
                unchanged += 1

        result.unchanged_count = unchanged
        return result

    @staticmethod
    def compare_event_lists(baseline_events: list[dict],
                            current_events: list[dict], *,
                            baseline_id: str = "baseline",
                            current_id: str = "current",
                            target: str = "",
                            ignore_types: set[str] | None = None
                            ) -> DiffResult:
        """Convenience: compare raw event lists directly."""
        snap_a = ScanSnapshot.from_events(
            baseline_events, scan_id=baseline_id, target=target)
        snap_b = ScanSnapshot.from_events(
            current_events, scan_id=current_id, target=target)
        return ScanDiff.compare(snap_a, snap_b,
                                ignore_types=ignore_types)
