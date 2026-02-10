"""Scan Delta Analyzer for SpiderFoot.

An enhanced comparison engine that analyzes deltas between scan
results with risk tracking, trend detection, and categorized
change reporting.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.scan_delta")


class DeltaKind(Enum):
    """Classification of a scan delta."""
    NEW_FINDING = "new_finding"
    RESOLVED = "resolved"
    RISK_INCREASED = "risk_increased"
    RISK_DECREASED = "risk_decreased"
    REAPPEARED = "reappeared"
    STABLE = "stable"


@dataclass
class Finding:
    """A single scan finding for comparison."""
    event_type: str
    data: str
    module: str = ""
    risk: int = 0
    confidence: int = 100
    scan_id: str = ""

    @property
    def fingerprint(self) -> str:
        """Return a unique fingerprint for this finding."""
        return f"{self.event_type}|{self.data}"

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "module": self.module,
            "risk": self.risk,
            "confidence": self.confidence,
            "scan_id": self.scan_id,
        }


@dataclass
class Delta:
    """A single delta between two scans."""
    kind: DeltaKind
    finding: Finding
    previous: Finding | None = None
    risk_change: int = 0
    note: str = ""

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        d = {
            "kind": self.kind.value,
            "finding": self.finding.to_dict(),
            "risk_change": self.risk_change,
        }
        if self.previous:
            d["previous"] = self.previous.to_dict()
        if self.note:
            d["note"] = self.note
        return d


@dataclass
class TrendPoint:
    """A point in a trend series."""
    scan_id: str
    total_findings: int
    risk_score: float
    new_findings: int
    resolved_findings: int


class ScanDeltaAnalyzer:
    """Enhanced scan delta analysis engine.

    Compares scans, tracks risk trends, and categorizes changes.

    Usage:
        analyzer = ScanDeltaAnalyzer()
        result = analyzer.analyze(baseline_findings, current_findings)
        print(result.risk_delta)
        for d in result.new_risks():
            print(f"NEW RISK: {d.finding.event_type} - {d.finding.data}")
    """

    def __init__(
        self,
        risk_threshold: int = 0,
        ignore_types: set[str] | None = None,
        track_modules: bool = True,
    ) -> None:
        """Initialize the ScanDeltaAnalyzer."""
        self.risk_threshold = risk_threshold
        self.ignore_types = ignore_types or set()
        self.track_modules = track_modules
        self._history: list[TrendPoint] = []

    def analyze(
        self,
        baseline: list[Finding],
        current: list[Finding],
    ) -> "DeltaResult":
        """Analyze delta between baseline and current findings."""
        # Build fingerprint maps
        base_map: dict[str, Finding] = {}
        for f in baseline:
            if f.event_type not in self.ignore_types:
                base_map[f.fingerprint] = f

        curr_map: dict[str, Finding] = {}
        for f in current:
            if f.event_type not in self.ignore_types:
                curr_map[f.fingerprint] = f

        deltas: list[Delta] = []

        # Check current against baseline
        for fp, curr_f in curr_map.items():
            if fp not in base_map:
                deltas.append(Delta(
                    kind=DeltaKind.NEW_FINDING,
                    finding=curr_f,
                    note="First seen in current scan",
                ))
            else:
                base_f = base_map[fp]
                risk_diff = curr_f.risk - base_f.risk
                if risk_diff > 0:
                    deltas.append(Delta(
                        kind=DeltaKind.RISK_INCREASED,
                        finding=curr_f,
                        previous=base_f,
                        risk_change=risk_diff,
                        note=f"Risk increased from {base_f.risk} to {curr_f.risk}",
                    ))
                elif risk_diff < 0:
                    deltas.append(Delta(
                        kind=DeltaKind.RISK_DECREASED,
                        finding=curr_f,
                        previous=base_f,
                        risk_change=risk_diff,
                        note=f"Risk decreased from {base_f.risk} to {curr_f.risk}",
                    ))
                else:
                    deltas.append(Delta(
                        kind=DeltaKind.STABLE,
                        finding=curr_f,
                        previous=base_f,
                    ))

        # Check baseline for removed findings
        for fp, base_f in base_map.items():
            if fp not in curr_map:
                deltas.append(Delta(
                    kind=DeltaKind.RESOLVED,
                    finding=base_f,
                    note="No longer present in current scan",
                ))

        return DeltaResult(deltas, baseline, current)

    def analyze_series(
        self,
        scans: list[tuple[str, list[Finding]]],
    ) -> list["DeltaResult"]:
        """Analyze a series of scans for trend detection.

        Args:
            scans: List of (scan_id, findings) tuples in chronological order.

        Returns:
            List of DeltaResult for each consecutive pair.
        """
        results = []
        for i in range(1, len(scans)):
            prev_id, prev_findings = scans[i - 1]
            curr_id, curr_findings = scans[i]
            result = self.analyze(prev_findings, curr_findings)
            results.append(result)

            # Track trend
            self._history.append(TrendPoint(
                scan_id=curr_id,
                total_findings=len(curr_findings),
                risk_score=sum(f.risk for f in curr_findings),
                new_findings=result.summary["new_findings"],
                resolved_findings=result.summary["resolved"],
            ))

        return results

    def get_trend(self) -> list[dict]:
        """Get recorded trend history."""
        return [
            {
                "scan_id": tp.scan_id,
                "total_findings": tp.total_findings,
                "risk_score": tp.risk_score,
                "new_findings": tp.new_findings,
                "resolved_findings": tp.resolved_findings,
            }
            for tp in self._history
        ]


class DeltaResult:
    """Result of a scan delta analysis."""

    def __init__(
        self,
        deltas: list[Delta],
        baseline: list[Finding],
        current: list[Finding],
    ) -> None:
        """Initialize the DeltaResult."""
        self._deltas = deltas
        self._baseline = baseline
        self._current = current

    @property
    def deltas(self) -> list[Delta]:
        """Return a copy of all deltas."""
        return list(self._deltas)

    def new_findings(self) -> list[Delta]:
        """Return deltas for newly discovered findings."""
        return [d for d in self._deltas if d.kind == DeltaKind.NEW_FINDING]

    def resolved(self) -> list[Delta]:
        """Return deltas for resolved findings."""
        return [d for d in self._deltas if d.kind == DeltaKind.RESOLVED]

    def risk_increased(self) -> list[Delta]:
        """Return deltas where risk has increased."""
        return [d for d in self._deltas if d.kind == DeltaKind.RISK_INCREASED]

    def risk_decreased(self) -> list[Delta]:
        """Return deltas where risk has decreased."""
        return [d for d in self._deltas if d.kind == DeltaKind.RISK_DECREASED]

    def stable(self) -> list[Delta]:
        """Return deltas for stable unchanged findings."""
        return [d for d in self._deltas if d.kind == DeltaKind.STABLE]

    def new_risks(self, min_risk: int = 1) -> list[Delta]:
        """Get new findings with risk >= min_risk."""
        return [
            d for d in self._deltas
            if d.kind == DeltaKind.NEW_FINDING
            and d.finding.risk >= min_risk
        ]

    def resolved_risks(self, min_risk: int = 1) -> list[Delta]:
        """Get resolved findings that had risk >= min_risk."""
        return [
            d for d in self._deltas
            if d.kind == DeltaKind.RESOLVED
            and d.finding.risk >= min_risk
        ]

    def by_type(self, event_type: str) -> list[Delta]:
        """Filter deltas by event type."""
        return [d for d in self._deltas if d.finding.event_type == event_type]

    @property
    def risk_delta(self) -> int:
        """Net change in total risk score."""
        old_risk = sum(f.risk for f in self._baseline)
        new_risk = sum(f.risk for f in self._current)
        return new_risk - old_risk

    @property
    def summary(self) -> dict:
        """Return a summary of the delta analysis."""
        return {
            "new_findings": len(self.new_findings()),
            "resolved": len(self.resolved()),
            "risk_increased": len(self.risk_increased()),
            "risk_decreased": len(self.risk_decreased()),
            "stable": len(self.stable()),
            "total_deltas": len(self._deltas),
            "risk_delta": self.risk_delta,
            "baseline_count": len(self._baseline),
            "current_count": len(self._current),
        }

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "summary": self.summary,
            "deltas": [d.to_dict() for d in self._deltas],
        }
