"""Multi-dimensional correlation analyzer.

Extends vector correlation with multi-dimensional analysis across
orthogonal OSINT dimensions:

* **Entity** — same data value across different sources
* **Temporal** — events clustered in time windows
* **Network** — shared IP space, ASN, hosting providers
* **Identity** — linked emails, names, phone numbers
* **Behavioral** — similar patterns of activity
* **Geographic** — co-location of infrastructure

Each dimension produces independent scores that are fused into
a unified correlation matrix using weighted combination.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from spiderfoot.constants import DEFAULT_TTL_ONE_HOUR

log = logging.getLogger("spiderfoot.multidim")


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

class Dimension(Enum):
    ENTITY = "entity"
    TEMPORAL = "temporal"
    NETWORK = "network"
    IDENTITY = "identity"
    BEHAVIORAL = "behavioral"
    GEOGRAPHIC = "geographic"


DEFAULT_WEIGHTS: dict[Dimension, float] = {
    Dimension.ENTITY: 1.0,
    Dimension.TEMPORAL: 0.8,
    Dimension.NETWORK: 0.9,
    Dimension.IDENTITY: 1.0,
    Dimension.BEHAVIORAL: 0.7,
    Dimension.GEOGRAPHIC: 0.6,
}

# Event type → dimension mapping
DIMENSION_TYPE_MAP: dict[str, set[Dimension]] = {
    "IP_ADDRESS": {Dimension.NETWORK, Dimension.ENTITY},
    "IPV6_ADDRESS": {Dimension.NETWORK, Dimension.ENTITY},
    "INTERNET_NAME": {Dimension.NETWORK, Dimension.ENTITY},
    "DOMAIN_NAME": {Dimension.ENTITY},
    "EMAIL_ADDRESS": {Dimension.IDENTITY, Dimension.ENTITY},
    "PHONE_NUMBER": {Dimension.IDENTITY},
    "HUMAN_NAME": {Dimension.IDENTITY},
    "USERNAME": {Dimension.IDENTITY, Dimension.BEHAVIORAL},
    "GEOINFO": {Dimension.GEOGRAPHIC},
    "PROVIDER_HOSTING": {Dimension.NETWORK},
    "PROVIDER_DNS": {Dimension.NETWORK},
    "BGP_AS_OWNER": {Dimension.NETWORK},
    "TCP_PORT_OPEN": {Dimension.NETWORK, Dimension.BEHAVIORAL},
    "WEBSERVER_BANNER": {Dimension.BEHAVIORAL},
    "URL_WEB": {Dimension.ENTITY},
    "SSL_CERTIFICATE_RAW": {Dimension.NETWORK},
    "SOCIAL_MEDIA": {Dimension.IDENTITY, Dimension.BEHAVIORAL},
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class DimensionScore:
    """Score for a single dimension."""

    dimension: Dimension
    score: float
    evidence_count: int = 0
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "score": round(self.score, 4),
            "evidence_count": self.evidence_count,
            "details": self.details,
        }


@dataclass
class CorrelationPair:
    """A pair of events with multi-dimensional scores."""

    event_a_id: str
    event_b_id: str
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    fused_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_a_id": self.event_a_id,
            "event_b_id": self.event_b_id,
            "fused_score": round(self.fused_score, 4),
            "dimensions": [d.to_dict() for d in self.dimension_scores],
        }


@dataclass
class EventData:
    """Lightweight event representation for analysis."""

    event_id: str
    event_type: str
    data: str
    scan_id: str = ""
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def dimensions(self) -> set[Dimension]:
        return DIMENSION_TYPE_MAP.get(self.event_type, {Dimension.ENTITY})


@dataclass
class MultiDimResult:
    """Result of multi-dimensional analysis."""

    query: str
    pairs: list[CorrelationPair] = field(default_factory=list)
    dimension_summary: dict[str, float] = field(default_factory=dict)
    clusters: list[list[str]] = field(default_factory=list)
    total_events: int = 0
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "pair_count": len(self.pairs),
            "cluster_count": len(self.clusters),
            "total_events": self.total_events,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "dimension_summary": {k: round(v, 4)
                                  for k, v in self.dimension_summary.items()},
            "top_pairs": [p.to_dict() for p in self.pairs[:10]],
        }


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------

def _entity_score(a: EventData, b: EventData) -> float:
    """Score based on shared entity data."""
    if a.data == b.data:
        return 1.0
    # Check partial overlap (e.g. subdomain of domain)
    if a.data in b.data or b.data in a.data:
        return 0.7
    # Same event type but different data
    if a.event_type == b.event_type:
        return 0.1
    return 0.0


def _temporal_score(a: EventData, b: EventData,
                    window_seconds: float = DEFAULT_TTL_ONE_HOUR) -> float:
    """Score based on temporal proximity."""
    if a.timestamp == 0 or b.timestamp == 0:
        return 0.0
    delta = abs(a.timestamp - b.timestamp)
    if delta == 0:
        return 1.0
    if delta > window_seconds:
        return 0.0
    return 1.0 - (delta / window_seconds)


def _network_score(a: EventData, b: EventData) -> float:
    """Score based on network relationship."""
    net_types = {"IP_ADDRESS", "IPV6_ADDRESS", "INTERNET_NAME",
                 "PROVIDER_HOSTING", "PROVIDER_DNS", "BGP_AS_OWNER"}
    a_is_net = a.event_type in net_types
    b_is_net = b.event_type in net_types
    if not (a_is_net or b_is_net):
        return 0.0

    # Same data = strong network link
    if a.data == b.data:
        return 1.0

    # Same /24 subnet for IPs
    if a.event_type == "IP_ADDRESS" and b.event_type == "IP_ADDRESS":
        a_parts = a.data.split(".")
        b_parts = b.data.split(".")
        if len(a_parts) == 4 and len(b_parts) == 4:
            if a_parts[:3] == b_parts[:3]:
                return 0.8
            if a_parts[:2] == b_parts[:2]:
                return 0.4

    # Shared hosting/ASN metadata
    a_asn = a.metadata.get("asn", "")
    b_asn = b.metadata.get("asn", "")
    if a_asn and b_asn and a_asn == b_asn:
        return 0.6

    return 0.0


def _identity_score(a: EventData, b: EventData) -> float:
    """Score based on identity linkage."""
    id_types = {"EMAIL_ADDRESS", "PHONE_NUMBER", "HUMAN_NAME",
                "USERNAME", "SOCIAL_MEDIA"}
    a_is_id = a.event_type in id_types
    b_is_id = b.event_type in id_types
    if not (a_is_id or b_is_id):
        return 0.0
    if a.data == b.data:
        return 1.0
    # Same domain in email
    if a.event_type == "EMAIL_ADDRESS" and b.event_type == "EMAIL_ADDRESS":
        a_domain = a.data.split("@")[-1] if "@" in a.data else ""
        b_domain = b.data.split("@")[-1] if "@" in b.data else ""
        if a_domain and a_domain == b_domain:
            return 0.5
    return 0.0


def _behavioral_score(a: EventData, b: EventData) -> float:
    """Score based on behavioral patterns."""
    behav_types = {"TCP_PORT_OPEN", "WEBSERVER_BANNER", "USERNAME",
                   "SOCIAL_MEDIA"}
    a_is_behav = a.event_type in behav_types
    b_is_behav = b.event_type in behav_types
    if not (a_is_behav or b_is_behav):
        return 0.0
    if a.data == b.data:
        return 1.0
    if a.event_type == b.event_type:
        return 0.3
    return 0.0


def _geographic_score(a: EventData, b: EventData) -> float:
    """Score based on geographic co-location."""
    a_country = a.metadata.get("country", "")
    b_country = b.metadata.get("country", "")
    if a_country and b_country:
        if a_country == b_country:
            a_city = a.metadata.get("city", "")
            b_city = b.metadata.get("city", "")
            if a_city and b_city and a_city == b_city:
                return 1.0
            return 0.5
    return 0.0


DIMENSION_SCORERS = {
    Dimension.ENTITY: _entity_score,
    Dimension.TEMPORAL: _temporal_score,
    Dimension.NETWORK: _network_score,
    Dimension.IDENTITY: _identity_score,
    Dimension.BEHAVIORAL: _behavioral_score,
    Dimension.GEOGRAPHIC: _geographic_score,
}


# ---------------------------------------------------------------------------
# Score fusion
# ---------------------------------------------------------------------------

def weighted_fusion(scores: list[DimensionScore],
                    weights: dict[Dimension, float] | None = None
                    ) -> float:
    """Fuse dimension scores using weighted average."""
    w = weights or DEFAULT_WEIGHTS
    total_weight = 0.0
    total_score = 0.0
    for ds in scores:
        weight = w.get(ds.dimension, 0.5)
        total_score += ds.score * weight
        total_weight += weight
    if total_weight == 0:
        return 0.0
    return total_score / total_weight


def max_fusion(scores: list[DimensionScore]) -> float:
    """Use maximum dimension score."""
    if not scores:
        return 0.0
    return max(ds.score for ds in scores)


def harmonic_fusion(scores: list[DimensionScore]) -> float:
    """Harmonic mean of non-zero scores (rewards multi-dimension coverage)."""
    nonzero = [ds.score for ds in scores if ds.score > 0]
    if not nonzero:
        return 0.0
    return len(nonzero) / sum(1.0 / s for s in nonzero)


# ---------------------------------------------------------------------------
# Multi-dimensional analyzer
# ---------------------------------------------------------------------------

class MultiDimAnalyzer:
    """Analyzes OSINT events across multiple correlation dimensions.

    Usage::

        analyzer = MultiDimAnalyzer()
        events = [EventData(...), EventData(...), ...]
        result = analyzer.analyze("find correlations", events)
    """

    def __init__(
        self,
        weights: dict[Dimension, float] | None = None,
        fusion_method: str = "weighted",
        min_score: float = 0.1,
        temporal_window: float = DEFAULT_TTL_ONE_HOUR,
    ) -> None:
        self._weights = weights or DEFAULT_WEIGHTS
        self._fusion_method = fusion_method
        self._min_score = min_score
        self._temporal_window = temporal_window

    def analyze(self, query: str,
                events: list[EventData],
                dimensions: list[Dimension] | None = None,
                ) -> MultiDimResult:
        """Analyze events across multiple dimensions."""
        start = time.time()
        dims = dimensions or list(Dimension)

        result = MultiDimResult(query=query, total_events=len(events))
        if len(events) < 2:
            result.elapsed_ms = (time.time() - start) * 1000
            return result

        # Score all pairs
        pairs: list[CorrelationPair] = []
        dim_totals: dict[str, float] = {d.value: 0.0 for d in dims}
        dim_counts: dict[str, int] = {d.value: 0 for d in dims}

        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                pair = self._score_pair(events[i], events[j], dims)
                if pair.fused_score >= self._min_score:
                    pairs.append(pair)
                    for ds in pair.dimension_scores:
                        if ds.score > 0:
                            dim_totals[ds.dimension.value] += ds.score
                            dim_counts[ds.dimension.value] += 1

        # Sort by fused score
        pairs.sort(key=lambda p: p.fused_score, reverse=True)
        result.pairs = pairs

        # Dimension summary (average non-zero scores)
        for d in dims:
            cnt = dim_counts.get(d.value, 0)
            if cnt > 0:
                result.dimension_summary[d.value] = \
                    dim_totals[d.value] / cnt

        # Build clusters using Union-Find
        result.clusters = self._cluster_events(events, pairs)

        result.elapsed_ms = (time.time() - start) * 1000
        return result

    def _score_pair(self, a: EventData, b: EventData,
                    dims: list[Dimension]) -> CorrelationPair:
        """Score a pair of events across dimensions."""
        scores: list[DimensionScore] = []
        for dim in dims:
            scorer = DIMENSION_SCORERS.get(dim)
            if not scorer:
                continue
            if dim == Dimension.TEMPORAL:
                score = scorer(a, b, self._temporal_window)
            else:
                score = scorer(a, b)
            scores.append(DimensionScore(
                dimension=dim, score=score,
                evidence_count=1 if score > 0 else 0,
            ))

        # Fuse scores
        if self._fusion_method == "max":
            fused = max_fusion(scores)
        elif self._fusion_method == "harmonic":
            fused = harmonic_fusion(scores)
        else:
            fused = weighted_fusion(scores, self._weights)

        return CorrelationPair(
            event_a_id=a.event_id,
            event_b_id=b.event_id,
            dimension_scores=scores,
            fused_score=fused,
        )

    def _cluster_events(self, events: list[EventData],
                        pairs: list[CorrelationPair]) -> list[list[str]]:
        """Cluster correlated events using Union-Find."""
        parent: dict[str, str] = {e.event_id: e.event_id for e in events}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for pair in pairs:
            if pair.event_a_id in parent and pair.event_b_id in parent:
                union(pair.event_a_id, pair.event_b_id)

        # Group by root
        groups: dict[str, list[str]] = {}
        for eid in parent:
            root = find(eid)
            groups.setdefault(root, []).append(eid)

        # Only return clusters with 2+ members
        return [members for members in groups.values() if len(members) >= 2]

    # Stats
    def stats(self) -> dict[str, Any]:
        return {
            "fusion_method": self._fusion_method,
            "min_score": self._min_score,
            "temporal_window": self._temporal_window,
            "weights": {d.value: w for d, w in self._weights.items()},
        }
