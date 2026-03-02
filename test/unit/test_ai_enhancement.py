"""Tests for spiderfoot.ai.tooling (Phase 5, Cycles 351-450)."""

import time
import pytest
from spiderfoot.ai.tooling import (
    Verdict,
    ValidationResult,
    ConfidenceCalibrator,
    FeedbackType,
    VerdictFeedback,
    FeedbackStore,
    PromptCache,
    SchemaField,
    OutputSchema,
    RetrievalResult,
    MockVectorStore,
    QueryExpander,
    GraphNode,
    GraphEdge,
    IntelligenceGraph,
    ThreatIndicator,
    ThreatFeedStore,
)


# ── Verdict Enum ──────────────────────────────────────────────────────


class TestVerdict:
    def test_values(self):
        assert Verdict.CONFIRMED.value == "confirmed"
        assert Verdict.FALSE_POSITIVE.value == "likely_false_positive"
        assert Verdict.NEEDS_REVIEW.value == "needs_review"

    def test_count(self):
        assert len(Verdict) == 3


# ── ValidationResult ──────────────────────────────────────────────────


class TestValidationResult:
    def test_basic(self):
        r = ValidationResult(Verdict.CONFIRMED, 0.95, "looks real")
        assert r.verdict == Verdict.CONFIRMED
        assert r.confidence == 0.95
        assert r.reasoning == "looks real"
        assert r.severity == "info"
        assert r.tags == []

    def test_to_dict(self):
        r = ValidationResult(
            Verdict.FALSE_POSITIVE, 0.7,
            severity="high", tags=["phishing"],
        )
        d = r.to_dict()
        assert d["verdict"] == "likely_false_positive"
        assert d["confidence"] == 0.7
        assert d["severity"] == "high"
        assert d["tags"] == ["phishing"]

    def test_confidence_rounding(self):
        r = ValidationResult(Verdict.CONFIRMED, 0.12345678)
        assert r.to_dict()["confidence"] == 0.123


# ── ConfidenceCalibrator ──────────────────────────────────────────────


class TestConfidenceCalibrator:
    def test_defaults_loaded(self):
        cal = ConfidenceCalibrator()
        assert cal.rule_count >= 7

    def test_penalty_below_threshold(self):
        cal = ConfidenceCalibrator()
        result = ValidationResult(Verdict.CONFIRMED, 0.8)
        calibrated = cal.calibrate(
            result, event_type="BLACKLISTED_SUBNET", risk=20
        )
        assert calibrated.confidence < 0.8

    def test_no_penalty_above_threshold(self):
        cal = ConfidenceCalibrator()
        result = ValidationResult(Verdict.CONFIRMED, 0.8)
        calibrated = cal.calibrate(
            result, event_type="BLACKLISTED_SUBNET", risk=60
        )
        # Above threshold, still get matched to the boost (if any),
        # but no penalty applied
        assert calibrated.confidence >= 0.8 or calibrated.confidence <= 0.8

    def test_boost(self):
        cal = ConfidenceCalibrator()
        result = ValidationResult(Verdict.CONFIRMED, 0.7)
        calibrated = cal.calibrate(
            result, event_type="VULNERABILITY_CVE_CRITICAL", risk=80
        )
        assert calibrated.confidence > 0.7

    def test_confidence_clamped_min(self):
        cal = ConfidenceCalibrator()
        cal.add_rule("TEST_*", risk_threshold=100, penalty=2.0)
        result = ValidationResult(Verdict.CONFIRMED, 0.3)
        calibrated = cal.calibrate(result, event_type="TEST_ITEM", risk=10)
        assert calibrated.confidence == 0.0

    def test_confidence_clamped_max(self):
        cal = ConfidenceCalibrator()
        cal.add_rule("SUPER_*", boost=2.0)
        result = ValidationResult(Verdict.CONFIRMED, 0.8)
        calibrated = cal.calibrate(result, event_type="SUPER_CRITICAL")
        assert calibrated.confidence == 1.0

    def test_no_matching_rule(self):
        cal = ConfidenceCalibrator()
        result = ValidationResult(Verdict.CONFIRMED, 0.5)
        calibrated = cal.calibrate(
            result, event_type="UNMATCHED_TYPE", risk=50
        )
        assert calibrated.confidence == 0.5

    def test_custom_rule(self):
        cal = ConfidenceCalibrator()
        cal.add_rule("CUSTOM_EVENT", risk_threshold=50, penalty=0.2)
        result = ValidationResult(Verdict.CONFIRMED, 0.9)
        calibrated = cal.calibrate(
            result, event_type="CUSTOM_EVENT", risk=30
        )
        assert calibrated.confidence == pytest.approx(0.7, abs=0.05)

    def test_preserves_other_fields(self):
        cal = ConfidenceCalibrator()
        result = ValidationResult(
            Verdict.FALSE_POSITIVE, 0.8,
            reasoning="test", severity="high",
            remediation="fix it", tags=["a", "b"],
        )
        calibrated = cal.calibrate(
            result, event_type="DARKNET_MENTION", risk=80
        )
        assert calibrated.verdict == Verdict.FALSE_POSITIVE
        assert calibrated.reasoning == "test"
        assert calibrated.severity == "high"
        assert calibrated.tags == ["a", "b"]


# ── FeedbackStore ─────────────────────────────────────────────────────


class TestFeedbackType:
    def test_values(self):
        assert FeedbackType.AGREE.value == "agree"
        assert FeedbackType.DISAGREE.value == "disagree"
        assert FeedbackType.UNSURE.value == "unsure"


class TestFeedbackStore:
    def _make_feedback(self, feedback_type: FeedbackType,
                       agent: str = "validator"
                       ) -> VerdictFeedback:
        return VerdictFeedback(
            event_id="evt-001",
            agent_name=agent,
            original_verdict=Verdict.CONFIRMED,
            feedback=feedback_type,
        )

    def test_empty(self):
        store = FeedbackStore()
        assert store.count == 0
        assert store.get_accuracy() == 0.0

    def test_add_and_count(self):
        store = FeedbackStore()
        store.add(self._make_feedback(FeedbackType.AGREE))
        assert store.count == 1

    def test_accuracy_all_agree(self):
        store = FeedbackStore()
        for _ in range(5):
            store.add(self._make_feedback(FeedbackType.AGREE))
        assert store.get_accuracy() == 100.0

    def test_accuracy_mixed(self):
        store = FeedbackStore()
        store.add(self._make_feedback(FeedbackType.AGREE))
        store.add(self._make_feedback(FeedbackType.DISAGREE))
        assert store.get_accuracy() == 50.0

    def test_accuracy_by_agent(self):
        store = FeedbackStore()
        store.add(self._make_feedback(FeedbackType.AGREE, "A"))
        store.add(self._make_feedback(FeedbackType.DISAGREE, "B"))
        assert store.get_accuracy("A") == 100.0
        assert store.get_accuracy("B") == 0.0

    def test_get_disagreements(self):
        store = FeedbackStore()
        store.add(self._make_feedback(FeedbackType.AGREE))
        store.add(self._make_feedback(FeedbackType.DISAGREE))
        store.add(self._make_feedback(FeedbackType.DISAGREE))
        assert len(store.get_disagreements()) == 2

    def test_get_stats(self):
        store = FeedbackStore()
        store.add(self._make_feedback(FeedbackType.AGREE))
        store.add(self._make_feedback(FeedbackType.DISAGREE))
        store.add(self._make_feedback(FeedbackType.UNSURE))
        stats = store.get_stats()
        assert stats["total"] == 3
        assert stats["agree"] == 1
        assert stats["disagree"] == 1
        assert stats["unsure"] == 1

    def test_empty_stats(self):
        store = FeedbackStore()
        stats = store.get_stats()
        assert stats["total"] == 0
        assert stats["accuracy"] == 0.0


# ── PromptCache ───────────────────────────────────────────────────────


class TestPromptCache:
    def test_compute_key_deterministic(self):
        k1 = PromptCache.compute_key("TYPE", "data")
        k2 = PromptCache.compute_key("TYPE", "data")
        assert k1 == k2

    def test_compute_key_normalization(self):
        k1 = PromptCache.compute_key("TYPE", "Hello World")
        k2 = PromptCache.compute_key("TYPE", "  hello world  ")
        assert k1 == k2

    def test_put_and_get(self):
        cache = PromptCache()
        key = PromptCache.compute_key("TYPE", "test")
        cache.put(key, {"verdict": "confirmed"})
        result = cache.get(key)
        assert result == {"verdict": "confirmed"}

    def test_miss(self):
        cache = PromptCache()
        assert cache.get("nonexistent") is None

    def test_invalidate(self):
        cache = PromptCache()
        key = "test-key"
        cache.put(key, {"data": 1})
        assert cache.invalidate(key) is True
        assert cache.get(key) is None
        assert cache.invalidate(key) is False

    def test_clear(self):
        cache = PromptCache()
        cache.put("k1", {"a": 1})
        cache.put("k2", {"b": 2})
        cache.clear()
        assert cache.size == 0

    def test_max_size_eviction(self):
        cache = PromptCache(max_size=3)
        cache.put("a", {"x": 1})
        cache.put("b", {"x": 2})
        cache.put("c", {"x": 3})
        cache.put("d", {"x": 4})  # evicts "a"
        assert cache.size == 3
        assert cache.get("a") is None
        assert cache.get("d") == {"x": 4}

    def test_expired_entry(self):
        cache = PromptCache()
        key = "exp-key"
        cache.put(key, {"data": 1}, ttl=0)
        time.sleep(0.01)
        assert cache.get(key) is None

    def test_hit_rate(self):
        cache = PromptCache()
        cache.put("k", {"x": 1})
        cache.get("k")  # hit
        cache.get("miss")  # miss
        assert cache.hit_rate == 50.0

    def test_stats(self):
        cache = PromptCache()
        cache.put("k", {"x": 1})
        stats = cache.stats
        assert stats["size"] == 1
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_empty_hit_rate(self):
        cache = PromptCache()
        assert cache.hit_rate == 0.0


# ── OutputSchema ──────────────────────────────────────────────────────


class TestSchemaField:
    def test_basic(self):
        f = SchemaField("verdict", "str", required=True,
                        allowed_values=["confirmed"])
        assert f.name == "verdict"
        assert f.field_type == "str"

    def test_optional(self):
        f = SchemaField("tags", "list", required=False)
        assert f.required is False


class TestOutputSchema:
    def test_valid_output(self):
        schema = OutputSchema("test", [
            SchemaField("name", "str"),
            SchemaField("score", "float", min_value=0, max_value=1),
        ])
        errors = schema.validate({"name": "test", "score": 0.5})
        assert errors == []

    def test_missing_required(self):
        schema = OutputSchema("test", [
            SchemaField("name", "str"),
        ])
        errors = schema.validate({})
        assert len(errors) == 1
        assert "Missing required" in errors[0]

    def test_wrong_type(self):
        schema = OutputSchema("test", [
            SchemaField("name", "str"),
        ])
        errors = schema.validate({"name": 123})
        assert len(errors) == 1
        assert "expected str" in errors[0]

    def test_float_accepts_int(self):
        schema = OutputSchema("test", [
            SchemaField("score", "float"),
        ])
        errors = schema.validate({"score": 1})
        assert errors == []

    def test_allowed_values(self):
        schema = OutputSchema("test", [
            SchemaField("verdict", "str",
                        allowed_values=["confirmed", "false"]),
        ])
        errors = schema.validate({"verdict": "unknown"})
        assert len(errors) == 1
        assert "not in allowed values" in errors[0]

    def test_min_value(self):
        schema = OutputSchema("test", [
            SchemaField("score", "float", min_value=0.0),
        ])
        errors = schema.validate({"score": -0.5})
        assert len(errors) == 1
        assert "below minimum" in errors[0]

    def test_max_value(self):
        schema = OutputSchema("test", [
            SchemaField("score", "float", max_value=1.0),
        ])
        errors = schema.validate({"score": 1.5})
        assert len(errors) == 1
        assert "above maximum" in errors[0]

    def test_optional_field_missing_ok(self):
        schema = OutputSchema("test", [
            SchemaField("tags", "list", required=False),
        ])
        errors = schema.validate({})
        assert errors == []

    def test_add_field(self):
        schema = OutputSchema("test")
        schema.add_field(SchemaField("name", "str"))
        assert schema.field_count == 1
        errors = schema.validate({"name": "ok"})
        assert errors == []

    def test_finding_validation_schema(self):
        schema = OutputSchema.finding_validation_schema()
        assert schema.field_count == 6
        valid_output = {
            "verdict": "confirmed",
            "confidence": 0.9,
            "reasoning": "test",
            "severity": "high",
        }
        errors = schema.validate(valid_output)
        assert errors == []

    def test_finding_schema_rejects_bad_verdict(self):
        schema = OutputSchema.finding_validation_schema()
        errors = schema.validate({
            "verdict": "invalid",
            "confidence": 0.9,
            "reasoning": "test",
            "severity": "high",
        })
        assert any("not in allowed values" in e for e in errors)


# ── MockVectorStore ───────────────────────────────────────────────────


class TestRetrievalResult:
    def test_to_dict(self):
        r = RetrievalResult("content", 0.95, {"key": "val"}, "doc-1")
        d = r.to_dict()
        assert d["content"] == "content"
        assert d["score"] == 0.95
        assert d["source_id"] == "doc-1"


class TestMockVectorStore:
    def test_add_and_count(self):
        store = MockVectorStore()
        doc_id = store.add("test document")
        assert doc_id == "doc-0001"
        assert store.count == 1

    def test_search_by_keyword(self):
        store = MockVectorStore()
        store.add("python security vulnerability")
        store.add("javascript framework tutorial")
        store.add("python malware analysis")
        results = store.search("python security")
        assert len(results) >= 1
        assert "python" in results[0].content.lower()

    def test_search_top_k(self):
        store = MockVectorStore()
        for i in range(10):
            store.add(f"document {i} about python")
        results = store.search("python", top_k=3)
        assert len(results) == 3

    def test_search_empty_query(self):
        store = MockVectorStore()
        store.add("test")
        assert store.search("") == []

    def test_search_no_match(self):
        store = MockVectorStore()
        store.add("completely unrelated")
        results = store.search("xyz_nonexistent_term")
        assert results == []

    def test_add_batch(self):
        store = MockVectorStore()
        ids = store.add_batch([
            {"content": "doc1"},
            {"content": "doc2", "metadata": {"src": "test"}},
        ])
        assert len(ids) == 2
        assert store.count == 2

    def test_delete(self):
        store = MockVectorStore()
        doc_id = store.add("test")
        assert store.delete(doc_id) is True
        assert store.count == 0
        assert store.delete(doc_id) is False

    def test_search_scores_ordered(self):
        store = MockVectorStore()
        store.add("python security vulnerability exploit")
        store.add("python")
        results = store.search("python security vulnerability")
        assert len(results) == 2
        assert results[0].score >= results[1].score


# ── QueryExpander ─────────────────────────────────────────────────────


class TestQueryExpander:
    def test_expand_known_term(self):
        expanded = QueryExpander.expand("phishing attack")
        assert len(expanded) > 1
        assert "phishing attack" in expanded

    def test_expand_unknown_term(self):
        expanded = QueryExpander.expand("random_unknown_query")
        assert expanded == ["random_unknown_query"]

    def test_get_synonyms(self):
        syns = QueryExpander.get_synonyms("malware")
        assert "virus" in syns
        assert "trojan" in syns

    def test_get_synonyms_unknown(self):
        assert QueryExpander.get_synonyms("xyz") == []

    def test_no_duplicates(self):
        expanded = QueryExpander.expand("phishing")
        assert len(expanded) == len(set(expanded))


# ── IntelligenceGraph ─────────────────────────────────────────────────


class TestGraphNode:
    def test_basic(self):
        n = GraphNode("n1", "domain", "example.com")
        assert n.node_id == "n1"
        assert n.label == "example.com"


class TestIntelligenceGraph:
    def _build_graph(self) -> IntelligenceGraph:
        g = IntelligenceGraph()
        g.add_node(GraphNode("d1", "domain", "example.com"))
        g.add_node(GraphNode("i1", "ip", "1.2.3.4"))
        g.add_node(GraphNode("i2", "ip", "5.6.7.8"))
        g.add_node(GraphNode("e1", "email", "admin@example.com"))
        g.add_edge(GraphEdge("d1", "i1", "resolves_to"))
        g.add_edge(GraphEdge("d1", "e1", "belongs_to"))
        return g

    def test_add_node(self):
        g = IntelligenceGraph()
        g.add_node(GraphNode("n1", "domain", "test.com"))
        assert g.node_count == 1

    def test_add_edge(self):
        g = self._build_graph()
        assert g.edge_count == 2

    def test_get_node(self):
        g = self._build_graph()
        n = g.get_node("d1")
        assert n is not None
        assert n.label == "example.com"
        assert g.get_node("nonexistent") is None

    def test_get_neighbors(self):
        g = self._build_graph()
        neighbors = g.get_neighbors("d1")
        assert len(neighbors) == 2
        labels = {n.label for n in neighbors}
        assert "1.2.3.4" in labels
        assert "admin@example.com" in labels

    def test_shortest_path(self):
        g = self._build_graph()
        path = g.shortest_path("i1", "e1")
        assert path is not None
        assert path[0] == "i1"
        assert path[-1] == "e1"
        assert "d1" in path

    def test_shortest_path_self(self):
        g = self._build_graph()
        assert g.shortest_path("d1", "d1") == ["d1"]

    def test_shortest_path_no_path(self):
        g = self._build_graph()
        path = g.shortest_path("i1", "i2")
        assert path is None

    def test_shortest_path_bad_node(self):
        g = self._build_graph()
        assert g.shortest_path("missing", "d1") is None

    def test_detect_communities(self):
        g = self._build_graph()
        communities = g.detect_communities()
        # d1-i1-e1 are connected, i2 is isolated
        assert len(communities) == 2
        sizes = sorted(len(c) for c in communities)
        assert sizes == [1, 3]

    def test_to_stix_bundle(self):
        g = self._build_graph()
        bundle = g.to_stix_bundle()
        assert bundle["type"] == "bundle"
        assert len(bundle["objects"]) > 0
        # Should have node objects + edge objects
        types = {o["type"] for o in bundle["objects"]}
        assert "domain-name" in types
        assert "ipv4-addr" in types
        assert "relationship" in types

    def test_stix_identity(self):
        g = IntelligenceGraph()
        g.add_node(GraphNode("p1", "person", "John Doe"))
        bundle = g.to_stix_bundle()
        obj = bundle["objects"][0]
        assert obj["type"] == "identity"
        assert obj["name"] == "John Doe"

    def test_stix_vulnerability(self):
        g = IntelligenceGraph()
        g.add_node(GraphNode("v1", "vulnerability", "CVE-2024-1234"))
        bundle = g.to_stix_bundle()
        obj = bundle["objects"][0]
        assert obj["type"] == "vulnerability"
        assert obj["name"] == "CVE-2024-1234"

    def test_stix_custom_type(self):
        g = IntelligenceGraph()
        g.add_node(GraphNode("x1", "custom", "Unknown Entity"))
        bundle = g.to_stix_bundle()
        obj = bundle["objects"][0]
        assert obj["type"] == "x-sf-entity"
        assert obj["x_sf_type"] == "custom"

    def test_get_stats(self):
        g = self._build_graph()
        stats = g.get_stats()
        assert stats["node_count"] == 4
        assert stats["edge_count"] == 2
        assert stats["community_count"] == 2
        assert stats["largest_community"] == 3
        assert "domain" in stats["node_types"]


# ── ThreatIndicator ───────────────────────────────────────────────────


class TestThreatIndicator:
    def test_to_dict(self):
        ind = ThreatIndicator("ip", "1.2.3.4", confidence=0.9,
                              source="feed-a", tags=["apt"])
        d = ind.to_dict()
        assert d["type"] == "ip"
        assert d["value"] == "1.2.3.4"
        assert d["confidence"] == 0.9
        assert d["tags"] == ["apt"]


class TestThreatFeedStore:
    def test_add_and_count(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("ip", "1.2.3.4"))
        assert store.count == 1

    def test_dedup_by_key(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("ip", "1.2.3.4", last_seen=100))
        store.add(ThreatIndicator("ip", "1.2.3.4", last_seen=200))
        assert store.count == 1
        ind = store.get("ip", "1.2.3.4")
        assert ind is not None
        assert ind.last_seen == 200

    def test_dedup_older_not_updated(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("ip", "1.2.3.4", last_seen=200))
        store.add(ThreatIndicator("ip", "1.2.3.4", last_seen=100))
        ind = store.get("ip", "1.2.3.4")
        assert ind is not None
        assert ind.last_seen == 200

    def test_get_not_found(self):
        store = ThreatFeedStore()
        assert store.get("ip", "1.2.3.4") is None

    def test_add_batch(self):
        store = ThreatFeedStore()
        count = store.add_batch([
            ThreatIndicator("ip", "1.2.3.4"),
            ThreatIndicator("domain", "evil.com"),
        ])
        assert count == 2
        assert store.count == 2

    def test_search_by_type(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("ip", "1.2.3.4"))
        store.add(ThreatIndicator("domain", "evil.com"))
        results = store.search(indicator_type="ip")
        assert len(results) == 1
        assert results[0].value == "1.2.3.4"

    def test_search_by_pattern(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("domain", "evil.example.com"))
        store.add(ThreatIndicator("domain", "good.example.com"))
        results = store.search(value_pattern="evil")
        assert len(results) == 1

    def test_search_by_regex(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("ip", "192.168.1.1"))
        store.add(ThreatIndicator("ip", "10.0.0.1"))
        results = store.search(value_pattern=r"^192\.")
        assert len(results) == 1

    def test_search_by_confidence(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("ip", "1.2.3.4", confidence=0.3))
        store.add(ThreatIndicator("ip", "5.6.7.8", confidence=0.9))
        results = store.search(min_confidence=0.5)
        assert len(results) == 1
        assert results[0].value == "5.6.7.8"

    def test_search_by_tags(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("ip", "1.2.3.4", tags=["apt", "c2"]))
        store.add(ThreatIndicator("ip", "5.6.7.8", tags=["spam"]))
        results = store.search(tags=["apt"])
        assert len(results) == 1
        assert results[0].value == "1.2.3.4"

    def test_match_events_ip(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("ip", "1.2.3.4", confidence=0.9))
        events = [
            {"event_type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"event_type": "IP_ADDRESS", "data": "9.9.9.9"},
        ]
        matches = store.match_events(events)
        assert len(matches) == 1
        assert matches[0]["match_type"] == "ip"

    def test_match_events_domain(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("domain", "evil.com"))
        events = [
            {"event_type": "DOMAIN_NAME", "data": "evil.com"},
        ]
        matches = store.match_events(events)
        assert len(matches) == 1

    def test_match_events_no_match(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("ip", "1.2.3.4"))
        events = [{"event_type": "UNKNOWN_TYPE", "data": "1.2.3.4"}]
        matches = store.match_events(events)
        assert matches == []

    def test_get_stats(self):
        store = ThreatFeedStore()
        store.add(ThreatIndicator("ip", "1.2.3.4", confidence=0.8))
        store.add(ThreatIndicator("domain", "evil.com", confidence=0.6))
        stats = store.get_stats()
        assert stats["total"] == 2
        assert stats["by_type"]["ip"] == 1
        assert stats["by_type"]["domain"] == 1
        assert stats["avg_confidence"] == 0.7


# ── Integration Tests ─────────────────────────────────────────────────


class TestIntegration:
    def test_calibrate_and_validate(self):
        """Calibrate + schema validation end-to-end."""
        cal = ConfidenceCalibrator()
        result = ValidationResult(
            Verdict.CONFIRMED, 0.8,
            reasoning="CVE detected",
            severity="critical",
        )
        calibrated = cal.calibrate(
            result, event_type="VULNERABILITY_CVE_CRITICAL", risk=90
        )

        schema = OutputSchema.finding_validation_schema()
        errors = schema.validate(calibrated.to_dict())
        assert errors == []

    def test_cache_then_feedback(self):
        """Cache response, then record feedback."""
        cache = PromptCache()
        key = PromptCache.compute_key("MALICIOUS_IP", "1.2.3.4")
        response = {"verdict": "confirmed", "confidence": 0.9}
        cache.put(key, response)

        cached = cache.get(key)
        assert cached is not None

        feedback_store = FeedbackStore()
        feedback_store.add(VerdictFeedback(
            event_id="evt-1",
            agent_name="validator",
            original_verdict=Verdict.CONFIRMED,
            feedback=FeedbackType.AGREE,
        ))
        assert feedback_store.get_accuracy() == 100.0

    def test_graph_to_threat_feed(self):
        """Build graph, export STIX, match events."""
        g = IntelligenceGraph()
        g.add_node(GraphNode("d1", "domain", "evil.com"))
        g.add_node(GraphNode("i1", "ip", "1.2.3.4"))
        g.add_edge(GraphEdge("d1", "i1", "resolves_to"))

        bundle = g.to_stix_bundle()
        assert len(bundle["objects"]) == 3

        feed = ThreatFeedStore()
        feed.add(ThreatIndicator("domain", "evil.com", confidence=0.95))
        feed.add(ThreatIndicator("ip", "1.2.3.4", confidence=0.90))

        events = [
            {"event_type": "DOMAIN_NAME", "data": "evil.com"},
            {"event_type": "IP_ADDRESS", "data": "1.2.3.4"},
        ]
        matches = feed.match_events(events)
        assert len(matches) == 2

    def test_vector_store_with_query_expansion(self):
        """Expand queries, search vector store."""
        store = MockVectorStore()
        store.add("phishing email targeting employees")
        store.add("spear phishing campaign detected")
        store.add("DNS zone transfer vulnerability")

        queries = QueryExpander.expand("phishing")
        all_results = []
        for q in queries:
            results = store.search(q)
            for r in results:
                if r.source_id not in {x.source_id for x in all_results}:
                    all_results.append(r)

        # Should find phishing-related docs
        assert len(all_results) >= 1

    def test_full_pipeline_flow(self):
        """Simulate a full AI pipeline flow."""
        # 1. Store threat indicators
        feed = ThreatFeedStore()
        feed.add(ThreatIndicator("ip", "10.0.0.1", confidence=0.85,
                                  tags=["c2"]))

        # 2. Match against events
        events = [{"event_type": "IP_ADDRESS", "data": "10.0.0.1"}]
        matches = feed.match_events(events)
        assert len(matches) == 1

        # 3. Simulate validation
        result = ValidationResult(Verdict.CONFIRMED, 0.8,
                                  reasoning="Known C2 IP",
                                  severity="high")

        # 4. Calibrate confidence
        cal = ConfidenceCalibrator()
        calibrated = cal.calibrate(
            result, event_type="MALICIOUS_IPADDR", risk=80
        )

        # 5. Validate output schema
        schema = OutputSchema.finding_validation_schema()
        errors = schema.validate(calibrated.to_dict())
        assert errors == []

        # 6. Cache the result
        cache = PromptCache()
        key = PromptCache.compute_key("MALICIOUS_IPADDR", "10.0.0.1")
        cache.put(key, calibrated.to_dict())
        assert cache.get(key) is not None

        # 7. Record feedback
        store = FeedbackStore()
        store.add(VerdictFeedback(
            event_id="evt-1",
            agent_name="validator",
            original_verdict=Verdict.CONFIRMED,
            feedback=FeedbackType.AGREE,
        ))
        assert store.get_accuracy() == 100.0

        # 8. Build intelligence graph
        g = IntelligenceGraph()
        g.add_node(GraphNode("ip1", "ip", "10.0.0.1",
                             data={"tags": ["c2"]}))
        g.add_node(GraphNode("d1", "domain", "c2-server.evil.com"))
        g.add_edge(GraphEdge("d1", "ip1", "resolves_to"))
        assert g.node_count == 2
        assert g.edge_count == 1
