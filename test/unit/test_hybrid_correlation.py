"""Tests for spiderfoot.hybrid_correlation — rules + vector + multi-dim."""
from __future__ import annotations

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from spiderfoot.hybrid_correlation import (
    CorrelationSource,
    HybridConfig,
    HybridCorrelator,
    HybridCorrelationResult,
    HybridFinding,
    _event_overlap,
    _normalize_multidim_result,
    _normalize_rule_result,
    _normalize_vector_result,
    merge_findings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rule_result(rule_id="r1", headline="Test rule", risk="HIGH",
                 groups=None, matched=True):
    return {
        "rule_id": rule_id, "headline": headline, "risk": risk,
        "groups": groups or [], "matched": matched,
    }


def _vector_result(hits=None, analysis="RAG text", risk="MEDIUM",
                   confidence=0.8):
    default_hits = [
        SimpleNamespace(event_id="e1", score=0.9),
        SimpleNamespace(event_id="e2", score=0.7),
    ]
    return SimpleNamespace(
        hits=hits if hits is not None else default_hits,
        analysis=analysis, risk_level=risk, confidence=confidence,
    )


def _multidim_result(pairs=None, clusters=None, dim_summary=None):
    from spiderfoot.multidim_correlation import (
        CorrelationPair, DimensionScore, Dimension, MultiDimResult,
    )
    pairs = pairs if pairs is not None else [
        CorrelationPair(
            event_a_id="a", event_b_id="b", fused_score=0.75,
            dimension_scores=[DimensionScore(Dimension.NETWORK, 0.9)],
        ),
    ]
    clusters = clusters if clusters is not None else [["a", "b"]]
    return MultiDimResult(
        query="test", total_events=2, elapsed_ms=5.0,
        pairs=pairs, clusters=clusters,
        dimension_summary=dim_summary or {"network": 0.9},
    )


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------

class TestNormalizeRules:
    def test_with_groups(self):
        res = _rule_result(groups=[
            {"event_ids": ["e1", "e2"], "count": 2, "key": "k1"},
        ])
        findings = _normalize_rule_result(res)
        assert len(findings) == 1
        assert CorrelationSource.RULES in findings[0].sources
        assert findings[0].risk_level == "HIGH"

    def test_no_groups_matched(self):
        res = _rule_result(groups=[], matched=True)
        findings = _normalize_rule_result(res)
        assert len(findings) == 1

    def test_no_groups_not_matched(self):
        res = _rule_result(groups=[], matched=False)
        findings = _normalize_rule_result(res)
        assert len(findings) == 0


class TestNormalizeVector:
    def test_with_hits(self):
        result = _vector_result()
        findings = _normalize_vector_result(result)
        assert len(findings) == 1
        assert CorrelationSource.VECTOR in findings[0].sources
        assert "e1" in findings[0].event_ids

    def test_no_hits(self):
        result = _vector_result(hits=[])
        findings = _normalize_vector_result(result)
        assert len(findings) == 0


class TestNormalizeMultiDim:
    def test_with_clusters(self):
        result = _multidim_result()
        findings = _normalize_multidim_result(result)
        assert len(findings) == 1
        assert CorrelationSource.MULTIDIM in findings[0].sources
        assert "network" in findings[0].dimensions

    def test_single_element_cluster_skipped(self):
        result = _multidim_result(clusters=[["a"]])
        findings = _normalize_multidim_result(result)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Event overlap + merge
# ---------------------------------------------------------------------------

class TestEventOverlap:
    def test_identical(self):
        a = HybridFinding(finding_id="a", headline="x", event_ids=["1", "2"])
        b = HybridFinding(finding_id="b", headline="y", event_ids=["1", "2"])
        assert _event_overlap(a, b) == 1.0

    def test_partial(self):
        a = HybridFinding(finding_id="a", headline="x",
                          event_ids=["1", "2", "3"])
        b = HybridFinding(finding_id="b", headline="y",
                          event_ids=["2", "3", "4"])
        assert 0 < _event_overlap(a, b) < 1.0

    def test_empty(self):
        a = HybridFinding(finding_id="a", headline="x", event_ids=[])
        b = HybridFinding(finding_id="b", headline="y", event_ids=["1"])
        assert _event_overlap(a, b) == 0.0


class TestMergeFindings:
    def test_no_overlap(self):
        f1 = HybridFinding(finding_id="a", headline="x",
                           confidence=0.8, event_ids=["1"],
                           sources=[CorrelationSource.RULES])
        f2 = HybridFinding(finding_id="b", headline="y",
                           confidence=0.6, event_ids=["2"],
                           sources=[CorrelationSource.VECTOR])
        merged = merge_findings([f1, f2], threshold=0.85)
        assert len(merged) == 2

    def test_full_overlap_merges(self):
        f1 = HybridFinding(finding_id="a", headline="Rule finding",
                           confidence=0.7, event_ids=["1", "2"],
                           sources=[CorrelationSource.RULES])
        f2 = HybridFinding(finding_id="b", headline="Vector finding",
                           confidence=0.6, event_ids=["1", "2"],
                           sources=[CorrelationSource.VECTOR])
        merged = merge_findings([f1, f2], threshold=0.85, boost=0.1)
        assert len(merged) == 1
        assert CorrelationSource.RULES in merged[0].sources
        assert CorrelationSource.VECTOR in merged[0].sources
        assert merged[0].confidence >= 0.7  # boosted

    def test_empty(self):
        assert merge_findings([]) == []

    def test_single(self):
        f = HybridFinding(finding_id="a", headline="x", confidence=0.5)
        assert merge_findings([f]) == [f]


# ---------------------------------------------------------------------------
# HybridCorrelator
# ---------------------------------------------------------------------------

class TestHybridCorrelator:
    def test_rules_only(self):
        factory = MagicMock(return_value={
            "r1": _rule_result(groups=[
                {"event_ids": ["e1"], "count": 1, "key": "k"},
            ]),
        })
        hc = HybridCorrelator(
            config=HybridConfig(enable_vector=False,
                                enable_multidim=False),
            rule_executor_factory=factory,
        )
        result = hc.correlate("scan1")
        assert result.scan_id == "scan1"
        assert result.total_findings > 0
        factory.assert_called_once()

    def test_vector_only(self):
        engine = MagicMock()
        engine.correlate.return_value = _vector_result()
        hc = HybridCorrelator(
            config=HybridConfig(enable_rules=False,
                                enable_multidim=False),
            vector_engine=engine,
        )
        result = hc.correlate("scan1", query="find related")
        assert result.total_findings >= 1

    def test_multidim_only(self):
        from spiderfoot.multidim_correlation import EventData
        analyzer = MagicMock()
        analyzer.analyze.return_value = _multidim_result()
        loader = MagicMock(return_value=[
            EventData(event_id="a", event_type="IP_ADDRESS", data="1.1.1.1"),
            EventData(event_id="b", event_type="IP_ADDRESS", data="1.1.1.2"),
        ])
        hc = HybridCorrelator(
            config=HybridConfig(enable_rules=False, enable_vector=False),
            multidim_analyzer=analyzer,
            event_loader=loader,
        )
        result = hc.correlate("scan1")
        assert result.total_findings >= 1

    def test_all_engines(self):
        factory = MagicMock(return_value={
            "r1": _rule_result(groups=[
                {"event_ids": ["e1", "e2"], "count": 2, "key": "k"},
            ]),
        })
        engine = MagicMock()
        engine.correlate.return_value = _vector_result()
        analyzer = MagicMock()
        analyzer.analyze.return_value = _multidim_result()
        loader = MagicMock(return_value=[])

        hc = HybridCorrelator(
            rule_executor_factory=factory,
            vector_engine=engine,
            multidim_analyzer=analyzer,
            event_loader=loader,
        )
        result = hc.correlate("scan1", query="test")
        assert result.total_findings >= 1
        assert "rules" in result.engine_stats
        assert "vector" in result.engine_stats

    def test_sequential_mode(self):
        factory = MagicMock(return_value={})
        hc = HybridCorrelator(
            config=HybridConfig(parallel=False, enable_vector=False,
                                enable_multidim=False),
            rule_executor_factory=factory,
        )
        result = hc.correlate("scan1")
        assert isinstance(result, HybridCorrelationResult)

    def test_on_finding_callback(self):
        findings_received = []
        factory = MagicMock(return_value={
            "r1": _rule_result(matched=True),
        })
        hc = HybridCorrelator(
            config=HybridConfig(enable_vector=False,
                                enable_multidim=False),
            rule_executor_factory=factory,
        )
        hc.on_finding(lambda f: findings_received.append(f))
        hc.correlate("scan1")
        assert len(findings_received) > 0

    def test_min_confidence_filter(self):
        factory = MagicMock(return_value={
            "r1": _rule_result(matched=True),
        })
        hc = HybridCorrelator(
            config=HybridConfig(enable_vector=False,
                                enable_multidim=False,
                                min_confidence=0.99),
            rule_executor_factory=factory,
        )
        result = hc.correlate("scan1")
        assert result.total_findings == 0

    def test_no_engines_enabled(self):
        hc = HybridCorrelator(
            config=HybridConfig(enable_rules=False, enable_vector=False,
                                enable_multidim=False),
        )
        result = hc.correlate("scan1")
        assert result.total_findings == 0

    def test_result_to_dict(self):
        hc = HybridCorrelator(
            config=HybridConfig(enable_rules=False, enable_vector=False,
                                enable_multidim=False),
        )
        result = hc.correlate("scan1")
        d = result.to_dict()
        assert d["scan_id"] == "scan1"
        assert "elapsed_ms" in d

    def test_finding_to_dict(self):
        f = HybridFinding(
            finding_id="test", headline="Test", confidence=0.8,
            sources=[CorrelationSource.RULES, CorrelationSource.VECTOR],
            dimensions={"entity": 0.9},
        )
        d = f.to_dict()
        assert d["confidence"] == 0.8
        assert "rules" in d["sources"]
