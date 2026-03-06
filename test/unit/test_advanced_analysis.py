"""Tests for spiderfoot.research.risk_scoring (Phase 8c, Cycles 801-1000)."""

import pytest
from spiderfoot.research.risk_scoring import (
    EntityNode,
    EntityEdge,
    GraphRiskScorer,
    ParsedQuery,
    NaturalLanguageParser,
    FeedbackType,
    FindingFeedback,
    ModuleFPStats,
    FalsePositiveReducer,
)


# ── GraphRiskScorer ───────────────────────────────────────────────────


class TestEntityNode:
    def test_feature_vector(self):
        n = EntityNode("n1", "domain", "example.com",
                        features={"a": 1.0, "b": 2.0})
        assert n.feature_vector() == [1.0, 2.0]

    def test_defaults(self):
        n = EntityNode("n1", "domain", "example.com")
        assert n.risk_score == 0.0
        assert n.neighbors == []


class TestGraphRiskScorer:
    def _scorer_with_network(self) -> GraphRiskScorer:
        s = GraphRiskScorer(propagation_rounds=3)
        s.add_node(EntityNode("d1", "domain", "example.com"))
        s.add_node(EntityNode("ip1", "ip_address", "1.2.3.4"))
        s.add_node(EntityNode("v1", "vulnerability", "CVE-2024-001"))
        s.add_edge(EntityEdge("d1", "ip1", "resolves_to"))
        s.add_edge(EntityEdge("ip1", "v1", "exposes"))
        return s

    def test_add_node(self):
        s = GraphRiskScorer()
        s.add_node(EntityNode("n1", "domain", "example.com"))
        assert s.node_count == 1

    def test_add_edge(self):
        s = GraphRiskScorer()
        s.add_node(EntityNode("n1", "domain", "a.com"))
        s.add_node(EntityNode("n2", "ip_address", "1.2.3.4"))
        s.add_edge(EntityEdge("n1", "n2", "resolves_to"))
        assert s.edge_count == 1

    def test_base_risk_assignment(self):
        s = GraphRiskScorer()
        s.add_node(EntityNode("v1", "vulnerability", "CVE-001"))
        node = s.get_node("v1")
        assert node.risk_score == 0.9

    def test_propagation(self):
        s = self._scorer_with_network()
        scores = s.propagate_risk()
        # Domain near vulnerability should have higher risk than baseline
        assert scores["d1"] > 0.15  # base for domain is 0.15

    def test_vulnerability_stays_high(self):
        s = self._scorer_with_network()
        scores = s.propagate_risk()
        assert scores["v1"] > 0.5  # Stays elevated above medium risk

    def test_top_risks(self):
        s = self._scorer_with_network()
        s.propagate_risk()
        top = s.get_top_risks(2)
        assert len(top) == 2
        assert top[0][1] >= top[1][1]

    def test_risk_distribution(self):
        s = self._scorer_with_network()
        s.propagate_risk()
        dist = s.get_risk_distribution()
        total = sum(dist.values())
        assert total == 3

    def test_isolated_node(self):
        s = GraphRiskScorer()
        s.add_node(EntityNode("n1", "email", "user@test.com"))
        scores = s.propagate_risk()
        assert scores["n1"] == 0.1  # Base risk for email

    def test_damping_factor(self):
        s1 = GraphRiskScorer(propagation_rounds=5, damping_factor=0.9)
        s2 = GraphRiskScorer(propagation_rounds=5, damping_factor=0.5)
        for s in (s1, s2):
            s.add_node(EntityNode("d1", "domain", "a.com"))
            s.add_node(EntityNode("v1", "vulnerability", "CVE-001"))
            s.add_edge(EntityEdge("d1", "v1", "exposes"))
        scores1 = s1.propagate_risk()
        scores2 = s2.propagate_risk()
        # Higher damping → more emphasis on own score
        # Domain with damping=0.5 absorbs more risk from vulnerability
        assert scores2["d1"] > scores1["d1"]


# ── NaturalLanguageParser ─────────────────────────────────────────────


class TestNaturalLanguageParser:
    def _parser(self) -> NaturalLanguageParser:
        return NaturalLanguageParser()

    def test_find_emails(self):
        p = self._parser()
        result = p.parse("Find all email addresses for example.com")
        assert result.intent == "find"
        assert result.target == "example.com"
        assert "email" in result.entity_types
        assert "sfp_email" in result.modules

    def test_scan_ports(self):
        p = self._parser()
        result = p.parse("Scan example.com for open ports")
        assert result.intent == "scan"
        assert "open_port" in result.entity_types

    def test_monitor_query(self):
        p = self._parser()
        result = p.parse("Monitor example.com for new subdomains")
        assert result.intent == "monitor"
        assert "subdomain" in result.entity_types

    def test_ip_target(self):
        p = self._parser()
        result = p.parse("Scan 192.168.1.1 for vulnerabilities")
        assert result.target == "192.168.1.1"

    def test_passive_constraint(self):
        p = self._parser()
        result = p.parse("Find subdomains for example.com using passive methods")
        assert result.constraints.get("passive_only") is True

    def test_thorough_constraint(self):
        p = self._parser()
        result = p.parse("Do a thorough scan of example.com")
        assert result.constraints.get("thorough") is True

    def test_confidence_scoring(self):
        p = self._parser()
        clear = p.parse("Find all subdomains for example.com")
        vague = p.parse("look around")
        assert clear.confidence > vague.confidence

    def test_to_dict(self):
        p = self._parser()
        result = p.parse("Find emails for example.com")
        d = result.to_dict()
        assert d["intent"] == "find"
        assert d["target"] == "example.com"

    def test_suggest_no_target(self):
        p = self._parser()
        result = p.parse("find something")
        suggestions = p.suggest_refinements(result)
        assert any("target" in s.lower() for s in suggestions)

    def test_certificate_query(self):
        p = self._parser()
        result = p.parse("Check SSL certificates for example.com")
        assert "certificate" in result.entity_types
        assert "sfp_ssl" in result.modules

    def test_multi_entity(self):
        p = self._parser()
        result = p.parse("Find emails and subdomains for example.com")
        assert "email" in result.entity_types
        assert "subdomain" in result.entity_types

    def test_default_entities(self):
        p = self._parser()
        result = p.parse("Analyze example.com")
        # Should get defaults when no specific entity mentioned
        assert len(result.entity_types) > 0


# ── FalsePositiveReducer ─────────────────────────────────────────────


class TestModuleFPStats:
    def test_fp_rate(self):
        s = ModuleFPStats("sfp_test", true_positives=80, false_positives=20)
        assert s.fp_rate == pytest.approx(0.2)

    def test_precision(self):
        s = ModuleFPStats("sfp_test", true_positives=80, false_positives=20)
        assert s.precision == pytest.approx(0.8)

    def test_empty_rate(self):
        s = ModuleFPStats("sfp_test")
        assert s.fp_rate == 0.0
        assert s.precision == 1.0


class TestFalsePositiveReducer:
    def _reducer_with_data(self) -> FalsePositiveReducer:
        r = FalsePositiveReducer(fp_threshold=0.3, min_samples=3)
        # Module with high FP rate for domains
        for _ in range(6):
            r.record_feedback(FindingFeedback(
                "sfp_bad", "DOMAIN_NAME", "domain",
                FeedbackType.FALSE_POSITIVE,
            ))
        for _ in range(4):
            r.record_feedback(FindingFeedback(
                "sfp_bad", "DOMAIN_NAME", "domain",
                FeedbackType.TRUE_POSITIVE,
            ))
        # Good module
        for _ in range(9):
            r.record_feedback(FindingFeedback(
                "sfp_good", "IP_ADDRESS", "ip",
                FeedbackType.TRUE_POSITIVE,
            ))
        r.record_feedback(FindingFeedback(
            "sfp_good", "IP_ADDRESS", "ip",
            FeedbackType.FALSE_POSITIVE,
        ))
        return r

    def test_record_feedback(self):
        r = FalsePositiveReducer()
        r.record_feedback(FindingFeedback("sfp_a", "DOMAIN", "domain",
                                          FeedbackType.TRUE_POSITIVE))
        assert r.feedback_count == 1
        assert r.module_count == 1

    def test_adjust_high_fp_module(self):
        r = self._reducer_with_data()
        adjusted = r.adjust_confidence("sfp_bad", "DOMAIN_NAME", "domain", 0.8)
        assert adjusted < 0.8  # Should be reduced

    def test_adjust_good_module(self):
        r = self._reducer_with_data()
        adjusted = r.adjust_confidence("sfp_good", "IP_ADDRESS", "ip", 0.8)
        assert adjusted == 0.8  # Should not be reduced

    def test_adjust_unknown_module(self):
        r = FalsePositiveReducer()
        adjusted = r.adjust_confidence("sfp_unknown", "X", "y", 0.8)
        assert adjusted == 0.8

    def test_adjust_insufficient_samples(self):
        r = FalsePositiveReducer(min_samples=100)
        r.record_feedback(FindingFeedback("sfp_a", "DOMAIN", "domain",
                                          FeedbackType.FALSE_POSITIVE))
        adjusted = r.adjust_confidence("sfp_a", "DOMAIN", "domain", 0.8)
        assert adjusted == 0.8

    def test_problematic_modules(self):
        r = self._reducer_with_data()
        problematic = r.get_problematic_modules()
        assert len(problematic) == 1
        assert problematic[0][0] == "sfp_bad"

    def test_recommendations(self):
        r = self._reducer_with_data()
        recs = r.get_recommendations()
        assert len(recs) >= 1
        assert recs[0]["module"] == "sfp_bad"
        assert recs[0]["action"] in ("reduce_confidence", "disable_for_target_type")

    def test_summary(self):
        r = self._reducer_with_data()
        summary = r.get_summary()
        assert summary["total_feedback"] == 20
        assert summary["modules_tracked"] == 2

    def test_target_type_fp_rate(self):
        r = self._reducer_with_data()
        stats = r.get_module_stats("sfp_bad")
        assert stats.fp_rate_for_target_type("domain") == pytest.approx(0.6)

    def test_min_confidence_floor(self):
        """Confidence should never go below 5%."""
        r = FalsePositiveReducer(fp_threshold=0.1, min_samples=2)
        for _ in range(10):
            r.record_feedback(FindingFeedback(
                "sfp_terrible", "X", "y", FeedbackType.FALSE_POSITIVE
            ))
        adjusted = r.adjust_confidence("sfp_terrible", "X", "y", 0.1)
        assert adjusted >= 0.05


# ── Integration Tests ─────────────────────────────────────────────────


class TestIntegration:
    def test_gnn_risk_to_fp_reduction(self):
        """High-risk entities from GNN feed into FP reducer."""
        scorer = GraphRiskScorer()
        scorer.add_node(EntityNode("d1", "domain", "example.com"))
        scorer.add_node(EntityNode("v1", "vulnerability", "CVE-2024-001"))
        scorer.add_edge(EntityEdge("d1", "v1", "exposes"))
        scores = scorer.propagate_risk()

        reducer = FalsePositiveReducer(min_samples=3)
        for _ in range(5):
            reducer.record_feedback(FindingFeedback(
                "sfp_vuln", "VULNERABILITY_CVE_CRITICAL", "domain",
                FeedbackType.TRUE_POSITIVE,
                confidence_at_time=scores["v1"],
            ))
        adjusted = reducer.adjust_confidence(
            "sfp_vuln", "VULNERABILITY_CVE_CRITICAL", "domain",
            scores["v1"],
        )
        assert adjusted == scores["v1"]  # Good module, no reduction

    def test_nl_query_to_modules(self):
        """NL query produces valid module list."""
        parser = NaturalLanguageParser()
        result = parser.parse(
            "Find all email addresses reachable from example.com's infrastructure"
        )
        assert result.target == "example.com"
        assert len(result.modules) > 0
        assert result.confidence > 0

    def test_full_pipeline(self):
        """NL query → risk score → FP adjust."""
        parser = NaturalLanguageParser()
        query = parser.parse("Scan example.com for vulnerabilities")

        scorer = GraphRiskScorer()
        scorer.add_node(EntityNode("d1", "domain", query.target))
        scorer.add_node(EntityNode("v1", "vulnerability", "CVE-2024-001"))
        scorer.add_edge(EntityEdge("d1", "v1", "exposes"))
        scores = scorer.propagate_risk()

        reducer = FalsePositiveReducer(min_samples=2)
        for _ in range(3):
            reducer.record_feedback(FindingFeedback(
                "sfp_test", "VULNERABILITY", "domain",
                FeedbackType.TRUE_POSITIVE,
            ))
        adjusted = reducer.adjust_confidence(
            "sfp_test", "VULNERABILITY", "domain", scores["v1"]
        )
        assert adjusted > 0
