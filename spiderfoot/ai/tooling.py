"""AI and Intelligence Enhancement Tooling (Phase 5, Cycles 351-450).

Provides testing, validation, and development tools for SpiderFoot's
AI and intelligence features — without requiring live LLM or vector
database connections.

Covers:
  - Cycle 351: FindingValidator confidence calibration
  - Cycle 352-354: Agent output feedback loop & breach context
  - Cycle 355: Prompt caching simulation
  - Cycle 356-380: Structured output validation
  - Cycle 381-400: RAG pipeline testing
  - Cycle 401-420: Intelligence graph analysis
  - Cycle 421-450: Threat intel integration helpers
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.ai.tooling")


# ── Verdict & Confidence (Cycles 351-354) ─────────────────────────────


class Verdict(str, Enum):
    """Agent validation verdict."""
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "likely_false_positive"
    NEEDS_REVIEW = "needs_review"


@dataclass
class ValidationResult:
    """Result of a finding validation."""
    verdict: Verdict
    confidence: float
    reasoning: str = ""
    severity: str = "info"
    remediation: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
            "severity": self.severity,
            "remediation": self.remediation,
            "tags": self.tags,
        }


class ConfidenceCalibrator:
    """Calibrate agent confidence scores to reduce over-reporting.

    Applies Platt scaling-inspired adjustment: events with low signal
    (e.g., BLACKLISTED_SUBNET with risk < 40) get confidence penalties,
    while high-signal events (CVE_CRITICAL) get confidence boosts.

    Usage::

        calibrator = ConfidenceCalibrator()
        calibrator.add_rule("BLACKLISTED_*", risk_threshold=40, penalty=0.3)
        calibrator.add_rule("VULNERABILITY_CVE_CRITICAL", boost=0.15)

        result = ValidationResult(Verdict.CONFIRMED, 0.8)
        calibrated = calibrator.calibrate(result, event_type="BLACKLISTED_SUBNET", risk=30)
        # confidence adjusted down by penalty
    """

    def __init__(self) -> None:
        self._rules: list[dict] = []
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default calibration rules."""
        self.add_rule("BLACKLISTED_*", risk_threshold=40, penalty=0.25)
        self.add_rule("BLACKLISTED_AFFILIATE_*", risk_threshold=30, penalty=0.30)
        self.add_rule("VULNERABILITY_CVE_CRITICAL", boost=0.10)
        self.add_rule("VULNERABILITY_CVE_HIGH", boost=0.05)
        self.add_rule("MALICIOUS_*", risk_threshold=50, penalty=0.15)
        self.add_rule("DARKNET_*", boost=0.05)
        self.add_rule("LEAKED_*", boost=0.08)

    def add_rule(self, event_pattern: str, *,
                 risk_threshold: int = 0,
                 penalty: float = 0.0,
                 boost: float = 0.0) -> None:
        """Add a calibration rule.

        Args:
            event_pattern: Glob pattern for event types (* supported).
            risk_threshold: Apply penalty if risk below this value.
            penalty: How much to reduce confidence (0-1).
            boost: How much to increase confidence (0-1).
        """
        # Convert glob to regex
        regex = "^" + event_pattern.replace("*", ".*") + "$"
        self._rules.append({
            "pattern": re.compile(regex, re.IGNORECASE),
            "risk_threshold": risk_threshold,
            "penalty": penalty,
            "boost": boost,
        })

    def calibrate(self, result: ValidationResult, *,
                  event_type: str = "",
                  risk: int = 50) -> ValidationResult:
        """Apply calibration to a validation result.

        Returns a new ValidationResult with adjusted confidence.
        """
        adj = 0.0

        for rule in self._rules:
            if not rule["pattern"].match(event_type):
                continue

            if rule["risk_threshold"] > 0 and risk < rule["risk_threshold"]:
                adj -= rule["penalty"]

            if rule["boost"] > 0:
                adj += rule["boost"]

        new_confidence = max(0.0, min(1.0, result.confidence + adj))

        return ValidationResult(
            verdict=result.verdict,
            confidence=new_confidence,
            reasoning=result.reasoning,
            severity=result.severity,
            remediation=result.remediation,
            tags=result.tags,
        )

    @property
    def rule_count(self) -> int:
        return len(self._rules)


# ── Agent Feedback Loop (Cycle 352) ───────────────────────────────────


class FeedbackType(str, Enum):
    """User feedback on agent verdicts."""
    AGREE = "agree"
    DISAGREE = "disagree"
    UNSURE = "unsure"


@dataclass
class VerdictFeedback:
    """User feedback on an agent verdict."""
    event_id: str
    agent_name: str
    original_verdict: Verdict
    feedback: FeedbackType
    corrected_verdict: Verdict | None = None
    comment: str = ""
    timestamp: float = field(default_factory=time.time)


class FeedbackStore:
    """Stores and analyzes user feedback on agent verdicts.

    Enables tracking of agent accuracy over time and identifying
    patterns where agents consistently err.
    """

    def __init__(self) -> None:
        self._feedback: list[VerdictFeedback] = []

    def add(self, feedback: VerdictFeedback) -> None:
        """Record user feedback."""
        self._feedback.append(feedback)

    def get_accuracy(self, agent_name: str | None = None) -> float:
        """Compute accuracy (% of agree feedbacks).

        Args:
            agent_name: Filter by specific agent. None = all.

        Returns:
            Accuracy as 0-100 float.
        """
        items = self._feedback
        if agent_name:
            items = [f for f in items if f.agent_name == agent_name]
        if not items:
            return 0.0
        agrees = sum(1 for f in items if f.feedback == FeedbackType.AGREE)
        return round((agrees / len(items)) * 100, 2)

    def get_disagreements(self, agent_name: str | None = None
                          ) -> list[VerdictFeedback]:
        """Get all disagree feedbacks."""
        items = self._feedback
        if agent_name:
            items = [f for f in items if f.agent_name == agent_name]
        return [f for f in items if f.feedback == FeedbackType.DISAGREE]

    def get_stats(self) -> dict:
        """Get aggregate feedback statistics."""
        total = len(self._feedback)
        if total == 0:
            return {"total": 0, "agree": 0, "disagree": 0, "unsure": 0,
                    "accuracy": 0.0}

        by_type = Counter(f.feedback.value for f in self._feedback)
        return {
            "total": total,
            "agree": by_type.get("agree", 0),
            "disagree": by_type.get("disagree", 0),
            "unsure": by_type.get("unsure", 0),
            "accuracy": self.get_accuracy(),
        }

    @property
    def count(self) -> int:
        return len(self._feedback)


# ── Prompt Cache (Cycle 355) ──────────────────────────────────────────


class PromptCache:
    """Simulates LLM prompt caching for identical event patterns.

    Groups events by (event_type, data_signature) and returns
    cached responses for semantically equivalent inputs.

    Usage::

        cache = PromptCache()
        key = cache.compute_key("VULNERABILITY_CVE_CRITICAL", "CVE-2024-1234 ...")
        if cached := cache.get(key):
            return cached
        response = call_llm(...)
        cache.put(key, response, ttl=3600)
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._cache: dict[str, dict] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    @staticmethod
    def compute_key(event_type: str, data: str) -> str:
        """Compute a cache key from event type and data.

        Normalizes the data (lowercase, strip whitespace) before
        hashing to increase cache hit rate.
        """
        normalized = f"{event_type}:{data.lower().strip()}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def get(self, key: str) -> dict | None:
        """Retrieve a cached response."""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        if entry.get("expires_at", float("inf")) < time.time():
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        return entry["response"]

    def put(self, key: str, response: dict, ttl: int = 3600) -> None:
        """Store a response in the cache.

        Args:
            key: Cache key from compute_key().
            response: The LLM response to cache.
            ttl: Time-to-live in seconds.
        """
        if len(self._cache) >= self._max_size:
            # Evict oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = {
            "response": response,
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
        }

    def invalidate(self, key: str) -> bool:
        """Invalidate a cache entry."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return round((self._hits / total) * 100, 2)

    @property
    def stats(self) -> dict:
        return {
            "size": self.size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
        }


# ── Structured Output Validation (Cycles 356-380) ────────────────────


@dataclass
class SchemaField:
    """A field in a structured output schema."""
    name: str
    field_type: str  # "str", "float", "int", "bool", "list", "dict"
    required: bool = True
    allowed_values: list[str] | None = None
    min_value: float | None = None
    max_value: float | None = None


class OutputSchema:
    """Defines and validates structured LLM output schemas.

    Ensures agent responses conform to expected structure.
    Rejects malformed outputs and provides detailed error messages.
    """

    def __init__(self, name: str, fields: list[SchemaField] | None = None
                 ) -> None:
        self.name = name
        self._fields: dict[str, SchemaField] = {}
        for f in (fields or []):
            self._fields[f.name] = f

    def add_field(self, field: SchemaField) -> None:
        """Add a field to the schema."""
        self._fields[field.name] = field

    def validate(self, output: dict) -> list[str]:
        """Validate output against the schema.

        Returns list of error messages (empty = valid).
        """
        errors: list[str] = []

        for name, field in self._fields.items():
            if name not in output:
                if field.required:
                    errors.append(f"Missing required field: {name}")
                continue

            value = output[name]
            errors.extend(self._validate_field(field, value))

        return errors

    def _validate_field(self, field: SchemaField, value: Any) -> list[str]:
        """Validate a single field value."""
        errors: list[str] = []
        type_map = {
            "str": str,
            "float": (int, float),
            "int": int,
            "bool": bool,
            "list": list,
            "dict": dict,
        }

        expected_type = type_map.get(field.field_type)
        if expected_type and not isinstance(value, expected_type):
            errors.append(
                f"Field '{field.name}' expected {field.field_type}, "
                f"got {type(value).__name__}"
            )
            return errors

        if field.allowed_values is not None:
            if str(value) not in field.allowed_values:
                errors.append(
                    f"Field '{field.name}' value '{value}' not in "
                    f"allowed values: {field.allowed_values}"
                )

        if field.min_value is not None and isinstance(value, (int, float)):
            if value < field.min_value:
                errors.append(
                    f"Field '{field.name}' value {value} below "
                    f"minimum {field.min_value}"
                )

        if field.max_value is not None and isinstance(value, (int, float)):
            if value > field.max_value:
                errors.append(
                    f"Field '{field.name}' value {value} above "
                    f"maximum {field.max_value}"
                )

        return errors

    @property
    def field_count(self) -> int:
        return len(self._fields)

    @classmethod
    def finding_validation_schema(cls) -> "OutputSchema":
        """Pre-built schema for FindingValidator output."""
        return cls("finding_validation", [
            SchemaField("verdict", "str", required=True,
                        allowed_values=["confirmed", "likely_false_positive",
                                         "needs_review"]),
            SchemaField("confidence", "float", required=True,
                        min_value=0.0, max_value=1.0),
            SchemaField("reasoning", "str", required=True),
            SchemaField("severity", "str", required=True,
                        allowed_values=["critical", "high", "medium",
                                         "low", "info"]),
            SchemaField("remediation", "str", required=False),
            SchemaField("tags", "list", required=False),
        ])


# ── RAG Pipeline Testing (Cycles 381-400) ─────────────────────────────


@dataclass
class RetrievalResult:
    """A single retrieval result from the RAG pipeline."""
    content: str
    score: float
    metadata: dict = field(default_factory=dict)
    source_id: str = ""

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "score": round(self.score, 4),
            "metadata": self.metadata,
            "source_id": self.source_id,
        }


class MockVectorStore:
    """Mock vector store for testing RAG pipelines without Qdrant.

    Supports add, search (by keyword similarity), and delete.
    """

    def __init__(self) -> None:
        self._documents: dict[str, dict] = {}
        self._counter = 0

    def add(self, content: str, metadata: dict | None = None) -> str:
        """Add a document. Returns the document ID."""
        self._counter += 1
        doc_id = f"doc-{self._counter:04d}"
        self._documents[doc_id] = {
            "content": content.lower(),
            "raw_content": content,
            "metadata": metadata or {},
        }
        return doc_id

    def add_batch(self, documents: list[dict]) -> list[str]:
        """Add multiple documents. Returns list of IDs."""
        ids = []
        for doc in documents:
            doc_id = self.add(
                doc.get("content", ""),
                doc.get("metadata"),
            )
            ids.append(doc_id)
        return ids

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        """Search by keyword overlap.

        Scores documents by the fraction of query words
        that appear in the document content.
        """
        query_words = set(query.lower().split())
        if not query_words:
            return []

        scored = []
        for doc_id, doc in self._documents.items():
            content_words = set(doc["content"].split())
            overlap = query_words & content_words
            if overlap:
                score = len(overlap) / len(query_words)
                scored.append(RetrievalResult(
                    content=doc["raw_content"],
                    score=score,
                    metadata=doc["metadata"],
                    source_id=doc_id,
                ))

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._documents)


class QueryExpander:
    """Expand search queries with related terms.

    Uses a static synonym map for OSINT-relevant terms
    to improve recall in semantic search.
    """

    SYNONYMS: dict[str, list[str]] = {
        "phishing": ["spear phishing", "credential theft",
                      "social engineering", "email fraud"],
        "malware": ["virus", "trojan", "ransomware", "backdoor",
                     "rootkit", "worm"],
        "vulnerability": ["CVE", "exploit", "weakness", "flaw",
                           "security bug"],
        "breach": ["data leak", "compromise", "exposure",
                    "unauthorized access"],
        "dns": ["nameserver", "domain resolution", "DNS record",
                 "zone transfer"],
        "ssl": ["TLS", "certificate", "HTTPS", "X.509"],
        "ip": ["IP address", "IPv4", "IPv6", "host address"],
        "email": ["SMTP", "mail server", "MX record",
                    "email address"],
        "port": ["service", "open port", "listening port",
                  "network service"],
        "dark web": ["darknet", "Tor", "onion service",
                      ".onion", "hidden service"],
    }

    @classmethod
    def expand(cls, query: str) -> list[str]:
        """Expand a query with synonyms.

        Returns the original query plus expanded versions.
        """
        expanded = [query]
        query_lower = query.lower()

        for term, synonyms in cls.SYNONYMS.items():
            if term in query_lower:
                for syn in synonyms:
                    expanded.append(query_lower.replace(term, syn))

        return list(dict.fromkeys(expanded))  # deduplicate

    @classmethod
    def get_synonyms(cls, term: str) -> list[str]:
        """Get synonyms for a specific term."""
        return cls.SYNONYMS.get(term.lower(), [])


# ── Intelligence Graph (Cycles 401-420) ───────────────────────────────


@dataclass
class GraphNode:
    """A node in the intelligence graph."""
    node_id: str
    node_type: str  # domain, ip, email, person, etc.
    label: str
    data: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge (relationship) in the intelligence graph."""
    source_id: str
    target_id: str
    edge_type: str  # resolves_to, belongs_to, linked_to, etc.
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)


class IntelligenceGraph:
    """In-memory intelligence graph for entity relationship analysis.

    Supports community detection, shortest path, and STIX export.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._adjacency: dict[str, list[str]] = defaultdict(list)

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph."""
        self._nodes[node.node_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge to the graph."""
        self._edges.append(edge)
        self._adjacency[edge.source_id].append(edge.target_id)
        self._adjacency[edge.target_id].append(edge.source_id)

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> list[GraphNode]:
        """Get neighboring nodes."""
        neighbor_ids = self._adjacency.get(node_id, [])
        return [self._nodes[nid] for nid in neighbor_ids
                if nid in self._nodes]

    def shortest_path(self, source_id: str, target_id: str
                      ) -> list[str] | None:
        """Find shortest path between two nodes (BFS).

        Returns list of node IDs or None if no path exists.
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            return None
        if source_id == target_id:
            return [source_id]

        visited = {source_id}
        queue = [(source_id, [source_id])]

        while queue:
            current, path = queue.pop(0)
            for neighbor in self._adjacency.get(current, []):
                if neighbor == target_id:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def detect_communities(self) -> list[set[str]]:
        """Detect communities using connected components.

        Returns list of sets of node IDs, each set being
        a community (connected component).
        """
        visited: set[str] = set()
        communities: list[set[str]] = []

        for node_id in self._nodes:
            if node_id in visited:
                continue

            # BFS to find connected component
            component: set[str] = set()
            queue = [node_id]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                for neighbor in self._adjacency.get(current, []):
                    if neighbor not in visited:
                        queue.append(neighbor)

            communities.append(component)

        return communities

    def to_stix_bundle(self) -> dict:
        """Export graph as a STIX 2.1 bundle.

        Maps graph node types to STIX domain objects.
        """
        stix_type_map = {
            "domain": "domain-name",
            "ip": "ipv4-addr",
            "ipv6": "ipv6-addr",
            "email": "email-addr",
            "url": "url",
            "file": "file",
            "person": "identity",
            "vulnerability": "vulnerability",
            "malware": "malware",
        }

        objects = []

        for node in self._nodes.values():
            stix_type = stix_type_map.get(node.node_type, "x-sf-entity")
            obj: dict[str, Any] = {
                "type": stix_type,
                "id": f"{stix_type}--{node.node_id}",
                "spec_version": "2.1",
            }

            if stix_type == "domain-name":
                obj["value"] = node.label
            elif stix_type in ("ipv4-addr", "ipv6-addr"):
                obj["value"] = node.label
            elif stix_type == "email-addr":
                obj["value"] = node.label
            elif stix_type == "url":
                obj["value"] = node.label
            elif stix_type == "identity":
                obj["name"] = node.label
                obj["identity_class"] = "individual"
            elif stix_type == "vulnerability":
                obj["name"] = node.label
            elif stix_type == "malware":
                obj["name"] = node.label
                obj["is_family"] = False
            else:
                obj["name"] = node.label
                obj["x_sf_type"] = node.node_type

            objects.append(obj)

        for edge in self._edges:
            rel = {
                "type": "relationship",
                "id": f"relationship--{edge.source_id}--{edge.target_id}",
                "spec_version": "2.1",
                "relationship_type": edge.edge_type,
                "source_ref": f"x-sf-entity--{edge.source_id}",
                "target_ref": f"x-sf-entity--{edge.target_id}",
            }
            objects.append(rel)

        return {
            "type": "bundle",
            "id": f"bundle--spiderfoot-{int(time.time())}",
            "objects": objects,
        }

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def get_stats(self) -> dict:
        """Get graph statistics."""
        type_counts = Counter(n.node_type for n in self._nodes.values())
        edge_type_counts = Counter(e.edge_type for e in self._edges)
        communities = self.detect_communities()

        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "node_types": dict(type_counts),
            "edge_types": dict(edge_type_counts),
            "community_count": len(communities),
            "largest_community": max(len(c) for c in communities) if communities else 0,
        }


# ── Threat Intel Helpers (Cycles 421-450) ─────────────────────────────


@dataclass
class ThreatIndicator:
    """An indicator of compromise (IoC)."""
    indicator_type: str  # ip, domain, hash, email, url
    value: str
    confidence: float = 0.5
    source: str = ""
    first_seen: float = 0.0
    last_seen: float = 0.0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": self.indicator_type,
            "value": self.value,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "tags": self.tags,
        }


class ThreatFeedStore:
    """In-memory threat indicator store for testing and development.

    Supports CRUD, deduplication, and match scanning.
    """

    def __init__(self) -> None:
        self._indicators: dict[str, ThreatIndicator] = {}

    def add(self, indicator: ThreatIndicator) -> str:
        """Add an indicator. Returns the key."""
        key = f"{indicator.indicator_type}:{indicator.value}"
        existing = self._indicators.get(key)
        if existing and indicator.last_seen > existing.last_seen:
            self._indicators[key] = indicator
        elif not existing:
            self._indicators[key] = indicator
        return key

    def add_batch(self, indicators: list[ThreatIndicator]) -> int:
        """Add multiple indicators. Returns count added/updated."""
        count = 0
        for ind in indicators:
            key = self.add(ind)
            count += 1
        return count

    def get(self, indicator_type: str, value: str
            ) -> ThreatIndicator | None:
        """Get a specific indicator."""
        key = f"{indicator_type}:{value}"
        return self._indicators.get(key)

    def search(self, *, indicator_type: str | None = None,
               value_pattern: str | None = None,
               min_confidence: float = 0.0,
               tags: list[str] | None = None) -> list[ThreatIndicator]:
        """Search indicators with filters."""
        results = list(self._indicators.values())

        if indicator_type:
            results = [i for i in results
                       if i.indicator_type == indicator_type]

        if value_pattern:
            try:
                pat = re.compile(value_pattern, re.IGNORECASE)
                results = [i for i in results if pat.search(i.value)]
            except re.error:
                results = [i for i in results
                           if value_pattern.lower() in i.value.lower()]

        if min_confidence > 0:
            results = [i for i in results
                       if i.confidence >= min_confidence]

        if tags:
            tag_set = set(tags)
            results = [i for i in results
                       if tag_set & set(i.tags)]

        return results

    def match_events(self, events: list[dict]) -> list[dict]:
        """Match events against the threat feed.

        Args:
            events: List of event dicts with "event_type" and "data".

        Returns:
            List of match dicts with event + matched indicator.
        """
        matches = []
        type_mapping = {
            "IP_ADDRESS": "ip",
            "IPV6_ADDRESS": "ip",
            "DOMAIN_NAME": "domain",
            "INTERNET_NAME": "domain",
            "EMAILADDR": "email",
            "URL": "url",
            "HASH": "hash",
        }

        for event in events:
            event_type = event.get("event_type", "")
            data = event.get("data", "")
            ioc_type = type_mapping.get(event_type)
            if not ioc_type or not data:
                continue

            indicator = self.get(ioc_type, data)
            if indicator:
                matches.append({
                    "event": event,
                    "indicator": indicator.to_dict(),
                    "match_type": ioc_type,
                })

        return matches

    @property
    def count(self) -> int:
        return len(self._indicators)

    def get_stats(self) -> dict:
        """Get feed statistics."""
        type_counts = Counter(i.indicator_type
                              for i in self._indicators.values())
        return {
            "total": self.count,
            "by_type": dict(type_counts),
            "avg_confidence": round(
                sum(i.confidence for i in self._indicators.values())
                / max(1, self.count), 3
            ),
        }
