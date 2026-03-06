"""Phase 8c — GNN Risk Scoring + NL Scan Interface + FP Reduction.

Cycles 801-850: Graph neural network-based risk scoring.
Cycles 901-950: Natural language scan interface.
Cycles 951-1000: Automated false positive reduction from scan feedback.
"""

from __future__ import annotations

import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── GNN-Based Risk Scoring (Cycles 801-850) ──────────────────────────


@dataclass
class EntityNode:
    """A node in the entity graph with features for risk scoring."""

    entity_id: str
    entity_type: str
    value: str
    features: dict[str, float] = field(default_factory=dict)
    risk_score: float = 0.0
    neighbors: list[str] = field(default_factory=list)

    def feature_vector(self) -> list[float]:
        """Return features as a sorted vector for the GNN."""
        return [self.features[k] for k in sorted(self.features)]


@dataclass
class EntityEdge:
    """An edge in the entity graph."""

    source: str
    target: str
    relation: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class GraphRiskScorer:
    """Graph-based risk scoring using message-passing neural network simulation.

    Replaces hardcoded risk levels with a graph-aware scoring model that
    considers entity neighborhood context. Uses simplified GNN-style
    message passing without requiring PyTorch/TensorFlow.
    """

    TYPE_BASE_RISK: dict[str, float] = {
        "vulnerability": 0.9,
        "malware": 0.95,
        "open_port": 0.5,
        "ip_address": 0.2,
        "domain": 0.15,
        "subdomain": 0.15,
        "email": 0.1,
        "certificate": 0.1,
        "person": 0.05,
        "organization": 0.05,
        "technology": 0.2,
        "url": 0.15,
    }

    RELATION_WEIGHTS: dict[str, float] = {
        "resolves_to": 0.8,
        "hosts": 0.7,
        "owned_by": 0.3,
        "linked_to": 0.5,
        "exposes": 0.9,
        "contains": 0.6,
        "registered_by": 0.2,
    }

    def __init__(
        self,
        propagation_rounds: int = 3,
        damping_factor: float = 0.8,
    ) -> None:
        self.propagation_rounds = propagation_rounds
        self.damping_factor = damping_factor
        self._nodes: dict[str, EntityNode] = {}
        self._edges: list[EntityEdge] = []
        self._adjacency: dict[str, list[tuple[str, float]]] = defaultdict(list)

    def add_node(self, node: EntityNode) -> None:
        # Set base risk from type
        if node.risk_score == 0.0:
            node.risk_score = self.TYPE_BASE_RISK.get(node.entity_type, 0.1)
        self._nodes[node.entity_id] = node

    def add_edge(self, edge: EntityEdge) -> None:
        self._edges.append(edge)
        weight = edge.weight * self.RELATION_WEIGHTS.get(edge.relation, 0.5)
        self._adjacency[edge.source].append((edge.target, weight))
        self._adjacency[edge.target].append((edge.source, weight))

        # Update neighbor lists
        if edge.source in self._nodes:
            self._nodes[edge.source].neighbors.append(edge.target)
        if edge.target in self._nodes:
            self._nodes[edge.target].neighbors.append(edge.source)

    def propagate_risk(self) -> dict[str, float]:
        """Run message-passing risk propagation.

        Simulates a GNN by aggregating neighbor risk scores
        with relation-weighted message passing.
        """
        scores = {nid: n.risk_score for nid, n in self._nodes.items()}

        for _ in range(self.propagation_rounds):
            new_scores: dict[str, float] = {}
            for nid in self._nodes:
                # Self contribution
                own_score = scores[nid]

                # Neighbor messages
                neighbor_msgs: list[float] = []
                for neighbor_id, weight in self._adjacency.get(nid, []):
                    if neighbor_id in scores:
                        neighbor_msgs.append(scores[neighbor_id] * weight)

                # Aggregate: mean of neighbor messages
                if neighbor_msgs:
                    agg = sum(neighbor_msgs) / len(neighbor_msgs)
                    new_scores[nid] = (
                        self.damping_factor * own_score
                        + (1 - self.damping_factor) * agg
                    )
                else:
                    new_scores[nid] = own_score

                # Clamp to [0, 1]
                new_scores[nid] = max(0.0, min(1.0, new_scores[nid]))

            scores = new_scores

        # Update node scores
        for nid, score in scores.items():
            self._nodes[nid].risk_score = score

        return scores

    def get_top_risks(self, n: int = 10) -> list[tuple[str, float]]:
        """Get the top N highest-risk entities."""
        scored = [(nid, node.risk_score) for nid, node in self._nodes.items()]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:n]

    def get_risk_distribution(self) -> dict[str, int]:
        """Categorize entities by risk level."""
        dist = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for node in self._nodes.values():
            if node.risk_score >= 0.9:
                dist["critical"] += 1
            elif node.risk_score >= 0.7:
                dist["high"] += 1
            elif node.risk_score >= 0.4:
                dist["medium"] += 1
            elif node.risk_score >= 0.2:
                dist["low"] += 1
            else:
                dist["info"] += 1
        return dist

    def get_node(self, entity_id: str) -> EntityNode | None:
        return self._nodes.get(entity_id)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)


# ── Natural Language Scan Interface (Cycles 901-950) ──────────────────


@dataclass
class ParsedQuery:
    """A parsed natural language scan query."""

    original: str
    intent: str  # find, scan, monitor, analyze
    target: str
    entity_types: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    modules: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "intent": self.intent,
            "target": self.target,
            "entity_types": self.entity_types,
            "constraints": self.constraints,
            "modules": self.modules,
            "confidence": self.confidence,
        }


class NaturalLanguageParser:
    """Parse natural language queries into scan configurations.

    Patterns supported:
    - "Find all email addresses for example.com"
    - "Scan example.com for open ports"
    - "What subdomains does example.com have?"
    - "Monitor example.com for new assets"
    """

    INTENT_PATTERNS: list[tuple[str, str]] = [
        (r"\bfind\b|\bsearch\b|\bdiscover\b|\bget\b|\blist\b", "find"),
        (r"\bscan\b|\bprobe\b|\bcheck\b|\btest\b", "scan"),
        (r"\bmonitor\b|\bwatch\b|\btrack\b|\balert\b", "monitor"),
        (r"\banalyz[e|s]\b|\binvestigat[e|s]\b|\breport\b", "analyze"),
    ]

    ENTITY_PATTERNS: dict[str, list[str]] = {
        "email": [r"\bemails?\b", r"\be-?mail\s+address"],
        "subdomain": [r"\bsub-?domains?\b"],
        "ip_address": [r"\bips?\b", r"\bip\s+address", r"\bipv[46]\b"],
        "open_port": [r"\bports?\b", r"\bopen\s+ports?\b", r"\bservices?\b"],
        "domain": [r"\bdomains?\b", r"\bhosts?\b"],
        "certificate": [r"\bcerts?\b", r"\bcertificates?\b", r"\bssl\b", r"\btls\b"],
        "technology": [r"\btechnolog", r"\bframeworks?\b", r"\bstack\b"],
        "vulnerability": [r"\bvulns?\b", r"\bvulnerabilit", r"\bcve\b", r"\bexploits?\b"],
        "person": [r"\bpersons?\b", r"\bpeople\b", r"\bcontacts?\b", r"\bwho\b"],
    }

    TARGET_PATTERN = re.compile(
        r"(?:for|of|on|from|at|about|does)\s+"
        r"([a-zA-Z0-9](?:[a-zA-Z0-9\-\.]*[a-zA-Z0-9])?(?:\.[a-zA-Z]{2,}))"
    )

    BARE_DOMAIN_PATTERN = re.compile(
        r"\b([a-zA-Z0-9](?:[a-zA-Z0-9\-]*[a-zA-Z0-9])?\.(?:com|net|org|io|co|gov|edu|info|biz|[a-z]{2}))\b"
    )

    IP_TARGET_PATTERN = re.compile(
        r"\b(\d{1,3}(?:\.\d{1,3}){3})\b"
    )

    ENTITY_TO_MODULES: dict[str, list[str]] = {
        "email": ["sfp_email", "sfp_whois"],
        "subdomain": ["sfp_subdomain", "sfp_dns"],
        "ip_address": ["sfp_dns", "sfp_shodan"],
        "open_port": ["sfp_portscan", "sfp_shodan"],
        "domain": ["sfp_dns", "sfp_whois"],
        "certificate": ["sfp_ssl"],
        "technology": ["sfp_webtech", "sfp_shodan"],
        "vulnerability": ["sfp_portscan", "sfp_shodan"],
        "person": ["sfp_whois", "sfp_email"],
    }

    CONSTRAINT_PATTERNS: dict[str, str] = {
        "passive_only": r"\bpassive\b|\bnon.?intrusive\b|\bstealthy?\b",
        "fast": r"\bquick\b|\bfast\b|\brapid\b",
        "thorough": r"\bthorough\b|\bdeep\b|\bfull\b|\bcomplete\b",
    }

    def parse(self, query: str) -> ParsedQuery:
        """Parse a natural language query into a structured scan request."""
        lower = query.lower().strip()
        confidence = 0.0

        # Detect intent
        intent = "find"  # default
        for pattern, intent_name in self.INTENT_PATTERNS:
            if re.search(pattern, lower):
                intent = intent_name
                confidence += 0.2
                break

        # Extract target
        target = ""
        ip_match = self.IP_TARGET_PATTERN.search(query)
        if ip_match:
            target = ip_match.group(1)
            confidence += 0.3
        else:
            target_match = self.TARGET_PATTERN.search(lower)
            if target_match:
                target = target_match.group(1)
                confidence += 0.3
            else:
                # Fall back to bare domain detection
                bare_match = self.BARE_DOMAIN_PATTERN.search(lower)
                if bare_match:
                    target = bare_match.group(1)
                    confidence += 0.3

        # Detect entity types
        entity_types: list[str] = []
        for etype, patterns in self.ENTITY_PATTERNS.items():
            for p in patterns:
                if re.search(p, lower):
                    entity_types.append(etype)
                    confidence += 0.1
                    break

        if not entity_types:
            # Default to broad recon
            entity_types = ["domain", "ip_address", "subdomain"]

        # Map to modules
        modules: list[str] = []
        seen: set[str] = set()
        for etype in entity_types:
            for mod in self.ENTITY_TO_MODULES.get(etype, []):
                if mod not in seen:
                    modules.append(mod)
                    seen.add(mod)

        # Detect constraints
        constraints: dict[str, Any] = {}
        for cname, cpattern in self.CONSTRAINT_PATTERNS.items():
            if re.search(cpattern, lower):
                constraints[cname] = True

        confidence = min(1.0, confidence)

        return ParsedQuery(
            original=query,
            intent=intent,
            target=target,
            entity_types=entity_types,
            constraints=constraints,
            modules=modules,
            confidence=confidence,
        )

    def suggest_refinements(self, parsed: ParsedQuery) -> list[str]:
        """Suggest ways to improve a low-confidence query."""
        suggestions: list[str] = []
        if not parsed.target:
            suggestions.append(
                "Specify a target domain or IP (e.g., 'for example.com')"
            )
        if not parsed.entity_types:
            suggestions.append(
                "Specify what to look for (e.g., 'email addresses', "
                "'subdomains', 'open ports')"
            )
        if parsed.confidence < 0.3:
            suggestions.append(
                "Try a more specific query like 'Find all subdomains "
                "for example.com'"
            )
        return suggestions


# ── Automated FP Reduction (Cycles 951-1000) ──────────────────────────


class FeedbackType(Enum):
    """User feedback on scan findings."""

    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    UNCERTAIN = "uncertain"


@dataclass
class FindingFeedback:
    """Feedback on a specific finding."""

    module_name: str
    event_type: str
    target_type: str  # domain, ip, url, etc.
    feedback: FeedbackType
    confidence_at_time: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ModuleFPStats:
    """False positive statistics for a module."""

    module_name: str
    total_findings: int = 0
    true_positives: int = 0
    false_positives: int = 0
    uncertain: int = 0
    by_target_type: dict[str, dict[str, int]] = field(default_factory=dict)
    by_event_type: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def fp_rate(self) -> float:
        confirmed = self.true_positives + self.false_positives
        if confirmed == 0:
            return 0.0
        return self.false_positives / confirmed

    @property
    def precision(self) -> float:
        confirmed = self.true_positives + self.false_positives
        if confirmed == 0:
            return 1.0
        return self.true_positives / confirmed

    def fp_rate_for_target_type(self, target_type: str) -> float:
        stats = self.by_target_type.get(target_type, {})
        tp = stats.get("true_positive", 0)
        fp = stats.get("false_positive", 0)
        if tp + fp == 0:
            return 0.0
        return fp / (tp + fp)


class FalsePositiveReducer:
    """Automated false positive reduction through feedback learning.

    Tracks module accuracy across target types and event types,
    then adjusts confidence scores based on historical FP rates.
    """

    def __init__(
        self,
        fp_threshold: float = 0.3,
        min_samples: int = 5,
    ) -> None:
        self.fp_threshold = fp_threshold
        self.min_samples = min_samples
        self._feedback: list[FindingFeedback] = []
        self._stats: dict[str, ModuleFPStats] = {}

    def record_feedback(self, feedback: FindingFeedback) -> None:
        """Record user feedback on a finding."""
        self._feedback.append(feedback)
        self._update_stats(feedback)

    def _update_stats(self, fb: FindingFeedback) -> None:
        if fb.module_name not in self._stats:
            self._stats[fb.module_name] = ModuleFPStats(
                module_name=fb.module_name
            )
        stats = self._stats[fb.module_name]
        stats.total_findings += 1

        if fb.feedback == FeedbackType.TRUE_POSITIVE:
            stats.true_positives += 1
        elif fb.feedback == FeedbackType.FALSE_POSITIVE:
            stats.false_positives += 1
        else:
            stats.uncertain += 1

        # By target type
        if fb.target_type not in stats.by_target_type:
            stats.by_target_type[fb.target_type] = {}
        tt = stats.by_target_type[fb.target_type]
        tt[fb.feedback.value] = tt.get(fb.feedback.value, 0) + 1

        # By event type
        if fb.event_type not in stats.by_event_type:
            stats.by_event_type[fb.event_type] = {}
        et = stats.by_event_type[fb.event_type]
        et[fb.feedback.value] = et.get(fb.feedback.value, 0) + 1

    def adjust_confidence(
        self,
        module_name: str,
        event_type: str,
        target_type: str,
        original_confidence: float,
    ) -> float:
        """Adjust confidence based on historical FP rates.

        If a module has a high FP rate for a specific target type,
        reduce confidence proportionally.
        """
        stats = self._stats.get(module_name)
        if not stats:
            return original_confidence

        # Need minimum samples
        total = stats.true_positives + stats.false_positives
        if total < self.min_samples:
            return original_confidence

        # Check target-specific FP rate
        target_fp = stats.fp_rate_for_target_type(target_type)
        overall_fp = stats.fp_rate

        # Use the more specific rate if we have enough data
        target_stats = stats.by_target_type.get(target_type, {})
        target_total = sum(
            target_stats.get(k, 0)
            for k in ("true_positive", "false_positive")
        )

        fp_rate = target_fp if target_total >= self.min_samples else overall_fp

        if fp_rate > self.fp_threshold:
            # Reduce confidence proportional to FP rate
            reduction = fp_rate * 0.5  # At most 50% reduction
            adjusted = original_confidence * (1.0 - reduction)
            return max(0.05, adjusted)  # Never go below 5%

        return original_confidence

    def get_problematic_modules(self) -> list[tuple[str, float]]:
        """Get modules with high FP rates, sorted by rate descending."""
        result: list[tuple[str, float]] = []
        for name, stats in self._stats.items():
            total = stats.true_positives + stats.false_positives
            if total >= self.min_samples and stats.fp_rate > self.fp_threshold:
                result.append((name, stats.fp_rate))
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    def get_module_stats(self, module_name: str) -> ModuleFPStats | None:
        return self._stats.get(module_name)

    def get_recommendations(self) -> list[dict[str, Any]]:
        """Generate recommendations based on FP analysis."""
        recs: list[dict[str, Any]] = []

        for name, fp_rate in self.get_problematic_modules():
            stats = self._stats[name]
            rec: dict[str, Any] = {
                "module": name,
                "fp_rate": round(fp_rate, 3),
                "total_reviewed": stats.true_positives + stats.false_positives,
                "action": "reduce_confidence",
            }

            # Find worst target types
            worst_target: str = ""
            worst_rate: float = 0.0
            for tt, tt_stats in stats.by_target_type.items():
                tp = tt_stats.get("true_positive", 0)
                fp = tt_stats.get("false_positive", 0)
                if tp + fp >= 3:
                    rate = fp / (tp + fp)
                    if rate > worst_rate:
                        worst_target = tt
                        worst_rate = rate

            if worst_target:
                rec["worst_target_type"] = worst_target
                rec["worst_target_fp_rate"] = round(worst_rate, 3)
                if worst_rate > 0.8:
                    rec["action"] = "disable_for_target_type"

            recs.append(rec)

        return recs

    def get_summary(self) -> dict[str, Any]:
        """Get overall FP reduction summary."""
        total_feedback = len(self._feedback)
        total_tp = sum(s.true_positives for s in self._stats.values())
        total_fp = sum(s.false_positives for s in self._stats.values())
        total_uncertain = sum(s.uncertain for s in self._stats.values())

        return {
            "total_feedback": total_feedback,
            "true_positives": total_tp,
            "false_positives": total_fp,
            "uncertain": total_uncertain,
            "overall_fp_rate": (
                total_fp / (total_tp + total_fp)
                if (total_tp + total_fp) > 0
                else 0.0
            ),
            "modules_tracked": len(self._stats),
            "problematic_modules": len(self.get_problematic_modules()),
        }

    @property
    def feedback_count(self) -> int:
        return len(self._feedback)

    @property
    def module_count(self) -> int:
        return len(self._stats)
