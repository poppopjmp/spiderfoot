"""Tests for spiderfoot.multidim_correlation — multi-dimensional analyzer."""

from __future__ import annotations

import pytest
from spiderfoot.multidim_correlation import (
    CorrelationPair,
    DEFAULT_WEIGHTS,
    Dimension,
    DimensionScore,
    EventData,
    MultiDimAnalyzer,
    MultiDimResult,
    _behavioral_score,
    _entity_score,
    _geographic_score,
    _identity_score,
    _network_score,
    _temporal_score,
    harmonic_fusion,
    max_fusion,
    weighted_fusion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ip_event(eid: str, ip: str, scan: str = "s1",
              ts: float = 1700000000.0, **meta) -> EventData:
    return EventData(
        event_id=eid, event_type="IP_ADDRESS", data=ip,
        scan_id=scan, timestamp=ts, metadata=meta,
    )


def _email_event(eid: str, email: str, ts: float = 0.0) -> EventData:
    return EventData(
        event_id=eid, event_type="EMAIL_ADDRESS", data=email,
        timestamp=ts,
    )


def _domain_event(eid: str, domain: str, ts: float = 0.0) -> EventData:
    return EventData(
        event_id=eid, event_type="DOMAIN_NAME", data=domain,
        timestamp=ts,
    )


# ---------------------------------------------------------------------------
# Entity scorer
# ---------------------------------------------------------------------------

class TestEntityScore:
    def test_exact_match(self):
        a = _ip_event("a", "1.2.3.4")
        b = _ip_event("b", "1.2.3.4")
        assert _entity_score(a, b) == 1.0

    def test_partial_overlap(self):
        a = _domain_event("a", "example.com")
        b = _domain_event("b", "sub.example.com")
        assert _entity_score(a, b) == 0.7

    def test_same_type_different_data(self):
        a = _ip_event("a", "1.2.3.4")
        b = _ip_event("b", "5.6.7.8")
        assert _entity_score(a, b) == 0.1

    def test_different_type_different_data(self):
        a = _ip_event("a", "1.2.3.4")
        b = _email_event("b", "user@test.com")
        assert _entity_score(a, b) == 0.0


# ---------------------------------------------------------------------------
# Temporal scorer
# ---------------------------------------------------------------------------

class TestTemporalScore:
    def test_same_time(self):
        a = _ip_event("a", "1.1.1.1", ts=1000.0)
        b = _ip_event("b", "2.2.2.2", ts=1000.0)
        assert _temporal_score(a, b) == 1.0

    def test_within_window(self):
        a = _ip_event("a", "1.1.1.1", ts=1000.0)
        b = _ip_event("b", "2.2.2.2", ts=1900.0)
        score = _temporal_score(a, b, window_seconds=3600.0)
        assert 0 < score < 1

    def test_outside_window(self):
        a = _ip_event("a", "1.1.1.1", ts=1000.0)
        b = _ip_event("b", "2.2.2.2", ts=5000.0)
        assert _temporal_score(a, b, window_seconds=3600.0) == 0.0

    def test_zero_timestamp(self):
        a = _ip_event("a", "1.1.1.1", ts=0.0)
        b = _ip_event("b", "2.2.2.2", ts=1000.0)
        assert _temporal_score(a, b) == 0.0


# ---------------------------------------------------------------------------
# Network scorer
# ---------------------------------------------------------------------------

class TestNetworkScore:
    def test_same_ip(self):
        a = _ip_event("a", "1.2.3.4")
        b = _ip_event("b", "1.2.3.4")
        assert _network_score(a, b) == 1.0

    def test_same_subnet_24(self):
        a = _ip_event("a", "10.0.0.1")
        b = _ip_event("b", "10.0.0.254")
        assert _network_score(a, b) == 0.8

    def test_same_subnet_16(self):
        a = _ip_event("a", "10.0.1.1")
        b = _ip_event("b", "10.0.2.1")
        assert _network_score(a, b) == 0.4

    def test_same_asn(self):
        a = _ip_event("a", "1.1.1.1", asn="AS13335")
        b = _ip_event("b", "8.8.8.8", asn="AS13335")
        assert _network_score(a, b) == 0.6

    def test_no_network(self):
        a = _email_event("a", "user@test.com")
        b = _email_event("b", "other@test.com")
        assert _network_score(a, b) == 0.0


# ---------------------------------------------------------------------------
# Identity scorer
# ---------------------------------------------------------------------------

class TestIdentityScore:
    def test_same_email(self):
        a = _email_event("a", "user@test.com")
        b = _email_event("b", "user@test.com")
        assert _identity_score(a, b) == 1.0

    def test_same_domain_email(self):
        a = _email_event("a", "alice@example.com")
        b = _email_event("b", "bob@example.com")
        assert _identity_score(a, b) == 0.5

    def test_no_identity(self):
        a = _ip_event("a", "1.2.3.4")
        b = _ip_event("b", "5.6.7.8")
        assert _identity_score(a, b) == 0.0


# ---------------------------------------------------------------------------
# Behavioral scorer
# ---------------------------------------------------------------------------

class TestBehavioralScore:
    def test_same_banner(self):
        a = EventData(event_id="a", event_type="WEBSERVER_BANNER",
                       data="Apache/2.4.52")
        b = EventData(event_id="b", event_type="WEBSERVER_BANNER",
                       data="Apache/2.4.52")
        assert _behavioral_score(a, b) == 1.0

    def test_same_type_different(self):
        a = EventData(event_id="a", event_type="WEBSERVER_BANNER",
                       data="Apache/2.4.52")
        b = EventData(event_id="b", event_type="WEBSERVER_BANNER",
                       data="nginx/1.24")
        assert _behavioral_score(a, b) == 0.3


# ---------------------------------------------------------------------------
# Geographic scorer
# ---------------------------------------------------------------------------

class TestGeographicScore:
    def test_same_city(self):
        a = _ip_event("a", "1.1.1.1", country="US", city="NYC")
        b = _ip_event("b", "2.2.2.2", country="US", city="NYC")
        assert _geographic_score(a, b) == 1.0

    def test_same_country(self):
        a = _ip_event("a", "1.1.1.1", country="US", city="NYC")
        b = _ip_event("b", "2.2.2.2", country="US", city="LA")
        assert _geographic_score(a, b) == 0.5

    def test_no_geo(self):
        a = _ip_event("a", "1.1.1.1")
        b = _ip_event("b", "2.2.2.2")
        assert _geographic_score(a, b) == 0.0


# ---------------------------------------------------------------------------
# Fusion methods
# ---------------------------------------------------------------------------

class TestFusion:
    def test_weighted(self):
        scores = [
            DimensionScore(Dimension.ENTITY, 0.8),
            DimensionScore(Dimension.NETWORK, 0.6),
        ]
        fused = weighted_fusion(scores)
        assert 0 < fused < 1

    def test_max_fusion(self):
        scores = [
            DimensionScore(Dimension.ENTITY, 0.3),
            DimensionScore(Dimension.NETWORK, 0.9),
        ]
        assert max_fusion(scores) == 0.9

    def test_max_fusion_empty(self):
        assert max_fusion([]) == 0.0

    def test_harmonic(self):
        scores = [
            DimensionScore(Dimension.ENTITY, 0.8),
            DimensionScore(Dimension.NETWORK, 0.8),
        ]
        h = harmonic_fusion(scores)
        assert abs(h - 0.8) < 1e-6

    def test_harmonic_zero(self):
        scores = [
            DimensionScore(Dimension.ENTITY, 0.0),
            DimensionScore(Dimension.NETWORK, 0.0),
        ]
        assert harmonic_fusion(scores) == 0.0


# ---------------------------------------------------------------------------
# DimensionScore
# ---------------------------------------------------------------------------

class TestDimensionScore:
    def test_to_dict(self):
        ds = DimensionScore(Dimension.ENTITY, 0.85, evidence_count=3)
        d = ds.to_dict()
        assert d["dimension"] == "entity"
        assert d["score"] == 0.85


# ---------------------------------------------------------------------------
# CorrelationPair
# ---------------------------------------------------------------------------

class TestCorrelationPair:
    def test_to_dict(self):
        pair = CorrelationPair(
            event_a_id="a", event_b_id="b",
            fused_score=0.75,
            dimension_scores=[DimensionScore(Dimension.ENTITY, 0.8)],
        )
        d = pair.to_dict()
        assert d["fused_score"] == 0.75
        assert len(d["dimensions"]) == 1


# ---------------------------------------------------------------------------
# MultiDimResult
# ---------------------------------------------------------------------------

class TestMultiDimResult:
    def test_to_dict(self):
        r = MultiDimResult(
            query="test", total_events=10, elapsed_ms=15.5,
            dimension_summary={"entity": 0.8},
        )
        d = r.to_dict()
        assert d["total_events"] == 10


# ---------------------------------------------------------------------------
# MultiDimAnalyzer
# ---------------------------------------------------------------------------

class TestMultiDimAnalyzer:
    def test_analyze_basic(self):
        analyzer = MultiDimAnalyzer()
        events = [
            _ip_event("a", "10.0.0.1", ts=1000.0),
            _ip_event("b", "10.0.0.2", ts=1100.0),
            _ip_event("c", "10.0.0.3", ts=1200.0),
        ]
        result = analyzer.analyze("find correlations", events)
        assert result.total_events == 3
        assert len(result.pairs) > 0
        assert result.elapsed_ms >= 0

    def test_analyze_single_event(self):
        analyzer = MultiDimAnalyzer()
        result = analyzer.analyze("test", [_ip_event("a", "1.1.1.1")])
        assert len(result.pairs) == 0

    def test_analyze_empty(self):
        analyzer = MultiDimAnalyzer()
        result = analyzer.analyze("test", [])
        assert len(result.pairs) == 0

    def test_cross_type_correlation(self):
        analyzer = MultiDimAnalyzer(min_score=0.01)
        events = [
            _ip_event("a", "10.0.0.1"),
            _email_event("b", "admin@example.com"),
            _domain_event("c", "example.com"),
        ]
        result = analyzer.analyze("test", events)
        assert len(result.pairs) > 0

    def test_clustering(self):
        analyzer = MultiDimAnalyzer(min_score=0.01)
        events = [
            _ip_event("a", "10.0.0.1"),
            _ip_event("b", "10.0.0.2"),
            _ip_event("c", "10.0.0.3"),
        ]
        result = analyzer.analyze("test", events)
        # All in same /24 so should cluster
        assert len(result.clusters) >= 1

    def test_dimension_filter(self):
        analyzer = MultiDimAnalyzer()
        events = [
            _ip_event("a", "10.0.0.1", ts=1000.0),
            _ip_event("b", "10.0.0.2", ts=1000.0),
        ]
        result = analyzer.analyze("test", events,
                                  dimensions=[Dimension.TEMPORAL])
        assert result.total_events == 2

    def test_max_fusion_method(self):
        analyzer = MultiDimAnalyzer(fusion_method="max", min_score=0.01)
        events = [
            _ip_event("a", "10.0.0.1"),
            _ip_event("b", "10.0.0.2"),
        ]
        result = analyzer.analyze("test", events)
        assert len(result.pairs) > 0

    def test_harmonic_fusion_method(self):
        analyzer = MultiDimAnalyzer(fusion_method="harmonic", min_score=0.01)
        events = [
            _ip_event("a", "10.0.0.1", ts=1000.0),
            _ip_event("b", "10.0.0.2", ts=1000.0),
        ]
        result = analyzer.analyze("test", events)
        assert len(result.pairs) > 0

    def test_dimension_summary(self):
        analyzer = MultiDimAnalyzer(min_score=0.01)
        events = [
            _ip_event("a", "10.0.0.1"),
            _ip_event("b", "10.0.0.2"),
        ]
        result = analyzer.analyze("test", events)
        assert "network" in result.dimension_summary

    def test_stats(self):
        analyzer = MultiDimAnalyzer()
        s = analyzer.stats()
        assert s["fusion_method"] == "weighted"
        assert "weights" in s
