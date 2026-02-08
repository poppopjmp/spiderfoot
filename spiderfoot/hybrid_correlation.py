"""Hybrid correlation orchestrator — rules + vector + multi-dim.

Combines three independent correlation engines into a single
orchestrated pipeline:

1. **YAML rule engine** — deterministic pattern matching
2. **Vector similarity** — semantic search via Qdrant + RAG
3. **Multi-dimensional analysis** — 6-axis orthogonal scoring

The orchestrator runs them in parallel (or sequentially) and merges
results into a unified ``HybridCorrelationResult``.

Usage::

    from spiderfoot.hybrid_correlation import HybridCorrelator

    hc = HybridCorrelator(config)
    result = hc.correlate(scan_id="abc123")
    for finding in result.findings:
        print(finding.headline, finding.confidence, finding.sources)
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

log = logging.getLogger("spiderfoot.hybrid_correlation")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class CorrelationSource(Enum):
    """Identifies which engine produced a finding."""

    RULES = "rules"
    VECTOR = "vector"
    MULTIDIM = "multidim"


@dataclass
class HybridConfig:
    """Configuration for the hybrid correlator."""

    # Engine toggles
    enable_rules: bool = True
    enable_vector: bool = True
    enable_multidim: bool = True

    # Execution
    parallel: bool = True
    max_workers: int = 3
    timeout_seconds: float = 60.0

    # Merging
    dedup_threshold: float = 0.85  # similarity above this merges findings
    min_confidence: float = 0.3    # drop findings below this
    boost_multi_source: float = 0.15  # confidence boost for multi-engine hits

    # Vector-specific
    vector_top_k: int = 30
    vector_threshold: float = 0.5

    # Multi-dim specific
    multidim_min_score: float = 0.3
    multidim_fusion: str = "weighted"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class HybridFinding:
    """A single correlation finding from the hybrid pipeline."""

    finding_id: str
    headline: str
    description: str = ""
    risk_level: str = "INFO"        # INFO, LOW, MEDIUM, HIGH, CRITICAL
    confidence: float = 0.0         # 0.0 – 1.0
    sources: List[CorrelationSource] = field(default_factory=list)
    event_ids: List[str] = field(default_factory=list)
    dimensions: Dict[str, float] = field(default_factory=dict)
    raw_scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "headline": self.headline,
            "description": self.description,
            "risk_level": self.risk_level,
            "confidence": round(self.confidence, 4),
            "sources": [s.value for s in self.sources],
            "event_ids": self.event_ids,
            "dimensions": {k: round(v, 4) for k, v in self.dimensions.items()},
            "metadata": self.metadata,
        }


@dataclass
class HybridCorrelationResult:
    """Aggregated result from all engines."""

    scan_id: str
    total_findings: int = 0
    findings: List[HybridFinding] = field(default_factory=list)
    engine_stats: Dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "total_findings": self.total_findings,
            "findings": [f.to_dict() for f in self.findings],
            "engine_stats": self.engine_stats,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


# ---------------------------------------------------------------------------
# Result normalizers (engine-specific → HybridFinding)
# ---------------------------------------------------------------------------

def _normalize_rule_result(rule_result: Dict[str, Any]) -> List[HybridFinding]:
    """Convert a YAML rule engine result dict to HybridFindings."""
    findings: List[HybridFinding] = []
    rule_id = rule_result.get("rule_id", rule_result.get("id", "unknown"))
    headline = rule_result.get("headline", "Rule correlation")
    risk = rule_result.get("risk", "INFO")
    groups = rule_result.get("groups", [])

    for idx, grp in enumerate(groups):
        fid = f"rule_{rule_id}_{idx}"
        event_ids = grp.get("event_ids", [])
        count = grp.get("count", len(event_ids))

        confidence = min(1.0, 0.5 + 0.05 * count)
        desc = grp.get("description", headline)

        findings.append(HybridFinding(
            finding_id=fid,
            headline=headline.format(**grp) if "{" in headline else headline,
            description=desc,
            risk_level=risk.upper(),
            confidence=confidence,
            sources=[CorrelationSource.RULES],
            event_ids=event_ids,
            metadata={"rule_id": rule_id, "group_key": grp.get("key", "")},
        ))

    # If no groups, create a single finding for the rule match
    if not groups and rule_result.get("matched", False):
        findings.append(HybridFinding(
            finding_id=f"rule_{rule_id}_0",
            headline=headline,
            risk_level=risk.upper(),
            confidence=0.5,
            sources=[CorrelationSource.RULES],
            metadata={"rule_id": rule_id},
        ))

    return findings


def _normalize_vector_result(vec_result: Any) -> List[HybridFinding]:
    """Convert a VectorCorrelationResult to HybridFindings."""
    findings: List[HybridFinding] = []

    hits = getattr(vec_result, "hits", [])
    analysis = getattr(vec_result, "analysis", "")
    risk = getattr(vec_result, "risk_level", "INFO")
    confidence = getattr(vec_result, "confidence", 0.0)

    if not hits:
        return findings

    # Group hits into a single finding per query
    event_ids = [h.event_id for h in hits]
    top_score = max(h.score for h in hits) if hits else 0.0

    findings.append(HybridFinding(
        finding_id=f"vector_{hash(tuple(event_ids)) & 0xFFFFFF:06x}",
        headline=f"Vector correlation: {len(hits)} related events found",
        description=analysis or "",
        risk_level=risk,
        confidence=confidence,
        sources=[CorrelationSource.VECTOR],
        event_ids=event_ids,
        raw_scores={"top_similarity": top_score},
        metadata={"hit_count": len(hits)},
    ))

    return findings


def _normalize_multidim_result(md_result: Any) -> List[HybridFinding]:
    """Convert a MultiDimResult to HybridFindings."""
    findings: List[HybridFinding] = []

    pairs = getattr(md_result, "pairs", [])
    clusters = getattr(md_result, "clusters", [])
    dim_summary = getattr(md_result, "dimension_summary", {})

    # One finding per cluster
    for cidx, cluster in enumerate(clusters):
        if len(cluster) < 2:
            continue

        # Find pairs within this cluster
        cluster_set = set(cluster)
        cluster_scores: Dict[str, float] = {}
        max_fused = 0.0
        for p in pairs:
            if p.event_a_id in cluster_set and p.event_b_id in cluster_set:
                max_fused = max(max_fused, p.fused_score)
                for ds in p.dimension_scores:
                    dim_key = ds.dimension.value
                    cluster_scores[dim_key] = max(
                        cluster_scores.get(dim_key, 0.0), ds.score
                    )

        # Map fused score to risk
        if max_fused >= 0.8:
            risk = "HIGH"
        elif max_fused >= 0.5:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        findings.append(HybridFinding(
            finding_id=f"multidim_cluster_{cidx}",
            headline=f"Multi-dimensional cluster of {len(cluster)} events",
            description=f"Top dimensions: {', '.join(cluster_scores.keys())}",
            risk_level=risk,
            confidence=max_fused,
            sources=[CorrelationSource.MULTIDIM],
            event_ids=list(cluster),
            dimensions=cluster_scores,
            metadata={"cluster_index": cidx, "cluster_size": len(cluster)},
        ))

    return findings


# ---------------------------------------------------------------------------
# Finding deduplication / merging
# ---------------------------------------------------------------------------

def _event_overlap(a: HybridFinding, b: HybridFinding) -> float:
    """Compute Jaccard similarity of event ID sets."""
    if not a.event_ids or not b.event_ids:
        return 0.0
    sa = set(a.event_ids)
    sb = set(b.event_ids)
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def merge_findings(findings: List[HybridFinding],
                   threshold: float = 0.85,
                   boost: float = 0.15) -> List[HybridFinding]:
    """Deduplicate and merge overlapping findings.

    Findings with event overlap above *threshold* are merged:
    - Confidence is boosted when multiple engines agree
    - All source engines are listed
    - Event IDs are unioned
    """
    if len(findings) <= 1:
        return findings

    # Sort by confidence descending
    findings = sorted(findings, key=lambda f: f.confidence, reverse=True)
    merged: List[HybridFinding] = []
    used: Set[int] = set()

    for i, primary in enumerate(findings):
        if i in used:
            continue

        # Find overlapping findings
        group = [primary]
        for j in range(i + 1, len(findings)):
            if j in used:
                continue
            if _event_overlap(primary, findings[j]) >= threshold:
                group.append(findings[j])
                used.add(j)

        if len(group) == 1:
            merged.append(primary)
            continue

        # Merge the group
        all_sources: Set[CorrelationSource] = set()
        all_events: Set[str] = set()
        all_dims: Dict[str, float] = {}
        best_confidence = 0.0
        best_risk = "INFO"
        headlines: List[str] = []
        descriptions: List[str] = []

        risk_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
        best_risk_val = 0

        for f in group:
            all_sources.update(f.sources)
            all_events.update(f.event_ids)
            for dim, score in f.dimensions.items():
                all_dims[dim] = max(all_dims.get(dim, 0.0), score)
            if f.confidence > best_confidence:
                best_confidence = f.confidence
            r = risk_order.get(f.risk_level, 0)
            if r > best_risk_val:
                best_risk_val = r
                best_risk = f.risk_level
            headlines.append(f.headline)
            if f.description:
                descriptions.append(f.description)

        # Boost for multi-source agreement
        if len(all_sources) > 1:
            best_confidence = min(1.0, best_confidence + boost)

        merged_finding = HybridFinding(
            finding_id=primary.finding_id,
            headline=headlines[0],
            description="; ".join(descriptions) if descriptions else "",
            risk_level=best_risk,
            confidence=best_confidence,
            sources=sorted(all_sources, key=lambda s: s.value),
            event_ids=sorted(all_events),
            dimensions=all_dims,
            metadata={"merged_count": len(group),
                       "original_headlines": headlines},
        )
        merged.append(merged_finding)

    return merged


# ---------------------------------------------------------------------------
# HybridCorrelator
# ---------------------------------------------------------------------------

class HybridCorrelator:
    """Orchestrates YAML rules + vector similarity + multi-dim analysis.

    Parameters
    ----------
    config : HybridConfig
        Pipeline configuration.
    rule_executor_factory : callable, optional
        ``(scan_id) -> result_dict`` — runs YAML rules for a scan.
    vector_engine : optional
        VectorCorrelationEngine instance (or mock).
    multidim_analyzer : optional
        MultiDimAnalyzer instance (or mock).
    event_loader : callable, optional
        ``(scan_id) -> List[EventData]`` — loads events for multi-dim.
    """

    def __init__(
        self,
        config: Optional[HybridConfig] = None,
        rule_executor_factory: Optional[Callable] = None,
        vector_engine: Any = None,
        multidim_analyzer: Any = None,
        event_loader: Optional[Callable] = None,
    ):
        self.config = config or HybridConfig()
        self._rule_factory = rule_executor_factory
        self._vector_engine = vector_engine
        self._multidim = multidim_analyzer
        self._event_loader = event_loader
        self._callbacks: List[Callable] = []

    def on_finding(self, callback: Callable) -> None:
        """Register callback invoked for each finding."""
        self._callbacks.append(callback)

    def correlate(
        self,
        scan_id: str,
        query: str = "",
        rule_ids: Optional[List[str]] = None,
    ) -> HybridCorrelationResult:
        """Run all enabled engines and merge results.

        Parameters
        ----------
        scan_id : str
            Scan to correlate.
        query : str
            Optional natural-language query for vector/RAG.
        rule_ids : list[str], optional
            Restrict YAML rules to these IDs.

        Returns
        -------
        HybridCorrelationResult
        """
        t0 = time.perf_counter()
        cfg = self.config
        all_findings: List[HybridFinding] = []
        stats: Dict[str, Any] = {}

        tasks: Dict[str, Callable] = {}
        if cfg.enable_rules and self._rule_factory:
            tasks["rules"] = lambda: self._run_rules(scan_id, rule_ids)
        if cfg.enable_vector and self._vector_engine:
            tasks["vector"] = lambda: self._run_vector(scan_id, query)
        if cfg.enable_multidim and self._multidim and self._event_loader:
            tasks["multidim"] = lambda: self._run_multidim(scan_id, query)

        if cfg.parallel and len(tasks) > 1:
            all_findings, stats = self._run_parallel(tasks)
        else:
            all_findings, stats = self._run_sequential(tasks)

        # Filter by minimum confidence
        filtered = [f for f in all_findings if f.confidence >= cfg.min_confidence]

        # Merge overlapping findings
        merged = merge_findings(
            filtered,
            threshold=cfg.dedup_threshold,
            boost=cfg.boost_multi_source,
        )

        # Sort by risk then confidence
        risk_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
        merged.sort(key=lambda f: (risk_order.get(f.risk_level, 0),
                                   f.confidence), reverse=True)

        elapsed = (time.perf_counter() - t0) * 1000

        result = HybridCorrelationResult(
            scan_id=scan_id,
            total_findings=len(merged),
            findings=merged,
            engine_stats=stats,
            elapsed_ms=elapsed,
        )

        # Fire callbacks
        for finding in merged:
            for cb in self._callbacks:
                try:
                    cb(finding)
                except Exception as exc:
                    log.warning("Finding callback error: %s", exc)

        return result

    # -----------------------------------------------------------------------
    # Engine runners
    # -----------------------------------------------------------------------

    def _run_rules(self, scan_id: str,
                   rule_ids: Optional[List[str]]) -> Tuple[List[HybridFinding], Dict]:
        """Execute YAML rule engine."""
        t0 = time.perf_counter()
        findings: List[HybridFinding] = []
        try:
            results = self._rule_factory(scan_id, rule_ids=rule_ids)
            if isinstance(results, dict):
                # results is {rule_id: result_dict}
                for rid, rres in results.items():
                    if isinstance(rres, dict):
                        rres.setdefault("rule_id", rid)
                        findings.extend(_normalize_rule_result(rres))
            elif isinstance(results, list):
                for rres in results:
                    if isinstance(rres, dict):
                        findings.extend(_normalize_rule_result(rres))
        except Exception as exc:
            log.error("Rule engine error: %s", exc)

        elapsed = (time.perf_counter() - t0) * 1000
        return findings, {"rules": {"count": len(findings), "elapsed_ms": round(elapsed, 2)}}

    def _run_vector(self, scan_id: str,
                    query: str) -> Tuple[List[HybridFinding], Dict]:
        """Execute vector correlation engine."""
        t0 = time.perf_counter()
        findings: List[HybridFinding] = []
        try:
            from spiderfoot.vector_correlation import CorrelationStrategy
            result = self._vector_engine.correlate(
                query=query or f"scan:{scan_id}",
                strategy=CorrelationStrategy.SIMILARITY,
                scan_id=scan_id,
            )
            findings = _normalize_vector_result(result)
        except Exception as exc:
            log.error("Vector engine error: %s", exc)

        elapsed = (time.perf_counter() - t0) * 1000
        return findings, {"vector": {"count": len(findings), "elapsed_ms": round(elapsed, 2)}}

    def _run_multidim(self, scan_id: str,
                      query: str) -> Tuple[List[HybridFinding], Dict]:
        """Execute multi-dimensional analyzer."""
        t0 = time.perf_counter()
        findings: List[HybridFinding] = []
        try:
            events = self._event_loader(scan_id)
            result = self._multidim.analyze(query or f"scan:{scan_id}", events)
            findings = _normalize_multidim_result(result)
        except Exception as exc:
            log.error("Multi-dim engine error: %s", exc)

        elapsed = (time.perf_counter() - t0) * 1000
        return findings, {"multidim": {"count": len(findings), "elapsed_ms": round(elapsed, 2)}}

    # -----------------------------------------------------------------------
    # Execution strategies
    # -----------------------------------------------------------------------

    def _run_parallel(self, tasks: Dict[str, Callable]) -> Tuple[List[HybridFinding], Dict]:
        """Run engines in parallel via thread pool."""
        all_findings: List[HybridFinding] = []
        all_stats: Dict[str, Any] = {}

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as pool:
            futures = {pool.submit(fn): name for name, fn in tasks.items()}
            for fut in as_completed(futures, timeout=self.config.timeout_seconds):
                name = futures[fut]
                try:
                    findings, stats = fut.result()
                    all_findings.extend(findings)
                    all_stats.update(stats)
                except Exception as exc:
                    log.error("Engine %s failed: %s", name, exc)
                    all_stats[name] = {"error": str(exc)}

        return all_findings, all_stats

    def _run_sequential(self, tasks: Dict[str, Callable]) -> Tuple[List[HybridFinding], Dict]:
        """Run engines sequentially."""
        all_findings: List[HybridFinding] = []
        all_stats: Dict[str, Any] = {}

        for name, fn in tasks.items():
            try:
                findings, stats = fn()
                all_findings.extend(findings)
                all_stats.update(stats)
            except Exception as exc:
                log.error("Engine %s failed: %s", name, exc)
                all_stats[name] = {"error": str(exc)}

        return all_findings, all_stats
