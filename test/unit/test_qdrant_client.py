"""Tests for spiderfoot.qdrant_client — Qdrant vector store client."""

from __future__ import annotations

import pytest
import time
from spiderfoot.qdrant_client import (
    CollectionInfo,
    DistanceMetric,
    Filter,
    MemoryVectorBackend,
    QdrantBackend,
    QdrantClient,
    QdrantConfig,
    SearchResult,
    VectorPoint,
    create_vector_store,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vec(dims: int = 4, seed: float = 1.0) -> list:
    """Generate a deterministic test vector."""
    return [seed * (i + 1) / dims for i in range(dims)]


def _make_client(prefix: str = "test_") -> QdrantClient:
    cfg = QdrantConfig(backend=QdrantBackend.MEMORY, collection_prefix=prefix)
    return QdrantClient(cfg)


# ---------------------------------------------------------------------------
# VectorPoint
# ---------------------------------------------------------------------------

class TestVectorPoint:
    def test_to_dict(self):
        p = VectorPoint(id="p1", vector=[0.1, 0.2], payload={"k": "v"}, score=0.95)
        d = p.to_dict()
        assert d["id"] == "p1"
        assert d["score"] == 0.95
        assert d["payload"]["k"] == "v"

    def test_defaults(self):
        p = VectorPoint(id="p2", vector=[])
        assert p.payload == {}
        assert p.score == 0.0


# ---------------------------------------------------------------------------
# CollectionInfo
# ---------------------------------------------------------------------------

class TestCollectionInfo:
    def test_to_dict(self):
        ci = CollectionInfo(name="c1", vector_size=128, distance=DistanceMetric.DOT)
        d = ci.to_dict()
        assert d["distance"] == "Dot"
        assert d["vector_size"] == 128


# ---------------------------------------------------------------------------
# SearchResult
# ---------------------------------------------------------------------------

class TestSearchResult:
    def test_to_dict(self):
        sr = SearchResult(
            points=[VectorPoint(id="x", vector=[1.0], score=0.9)],
            query_time_ms=1.234,
            total_found=1,
        )
        d = sr.to_dict()
        assert d["query_time_ms"] == 1.23
        assert len(d["points"]) == 1

    def test_empty(self):
        sr = SearchResult(points=[])
        assert sr.to_dict()["total_found"] == 0


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------

class TestFilter:
    def test_match(self):
        f = Filter(must=[Filter.match("type", "IP")])
        assert not f.is_empty
        d = f.to_dict()
        assert "must" in d
        assert d["must"][0]["key"] == "type"

    def test_range(self):
        f = Filter(must=[Filter.range("risk", gte=5.0, lte=10.0)])
        d = f.to_dict()
        assert d["must"][0]["range"]["gte"] == 5.0
        assert d["must"][0]["range"]["lte"] == 10.0

    def test_empty(self):
        f = Filter()
        assert f.is_empty

    def test_to_dict_skips_empty_lists(self):
        f = Filter(should=[Filter.match("x", 1)])
        d = f.to_dict()
        assert "must" not in d
        assert "should" in d


# ---------------------------------------------------------------------------
# QdrantConfig
# ---------------------------------------------------------------------------

class TestQdrantConfig:
    def test_defaults(self):
        cfg = QdrantConfig()
        assert cfg.backend == QdrantBackend.MEMORY
        assert cfg.port == 6333

    def test_from_env(self):
        env = {
            "SF_QDRANT_BACKEND": "http",
            "SF_QDRANT_HOST": "qdrant.local",
            "SF_QDRANT_PORT": "6334",
            "SF_QDRANT_API_KEY": "secret",
            "SF_QDRANT_HTTPS": "true",
            "SF_QDRANT_PREFIX": "myapp_",
        }
        cfg = QdrantConfig.from_env(env)
        assert cfg.backend == QdrantBackend.HTTP
        assert cfg.host == "qdrant.local"
        assert cfg.port == 6334
        assert cfg.api_key == "secret"
        assert cfg.https is True
        assert cfg.collection_prefix == "myapp_"


# ---------------------------------------------------------------------------
# MemoryVectorBackend
# ---------------------------------------------------------------------------

class TestMemoryVectorBackend:
    def setup_method(self):
        self.backend = MemoryVectorBackend()
        self.backend.create_collection("test", 4)

    def test_create_collection(self):
        assert self.backend.collection_exists("test")
        assert not self.backend.create_collection("test", 4)  # duplicate

    def test_delete_collection(self):
        assert self.backend.delete_collection("test")
        assert not self.backend.collection_exists("test")
        assert not self.backend.delete_collection("test")  # already gone

    def test_list_collections(self):
        self.backend.create_collection("other", 8)
        names = self.backend.list_collections()
        assert "test" in names
        assert "other" in names

    def test_collection_info(self):
        info = self.backend.collection_info("test")
        assert info is not None
        assert info.vector_size == 4
        assert info.distance == DistanceMetric.COSINE

    def test_collection_info_missing(self):
        assert self.backend.collection_info("nope") is None

    def test_upsert_and_get(self):
        points = [
            VectorPoint(id="a", vector=_vec(4, 1.0), payload={"k": "v1"}),
            VectorPoint(id="b", vector=_vec(4, 2.0), payload={"k": "v2"}),
        ]
        count = self.backend.upsert("test", points)
        assert count == 2

        got = self.backend.get("test", ["a", "b", "missing"])
        assert len(got) == 2
        assert got[0].id == "a"

    def test_upsert_to_missing_collection(self):
        count = self.backend.upsert("nope", [VectorPoint(id="x", vector=[1.0])])
        assert count == 0

    def test_upsert_auto_id(self):
        p = VectorPoint(id="", vector=_vec(4))
        self.backend.upsert("test", [p])
        assert p.id != ""

    def test_delete_points(self):
        self.backend.upsert("test", [
            VectorPoint(id="a", vector=_vec(4)),
            VectorPoint(id="b", vector=_vec(4)),
        ])
        assert self.backend.delete("test", ["a"]) == 1
        assert self.backend.count("test") == 1

    def test_delete_missing_points(self):
        assert self.backend.delete("test", ["nonexistent"]) == 0

    def test_count(self):
        assert self.backend.count("test") == 0
        self.backend.upsert("test", [VectorPoint(id="a", vector=_vec(4))])
        assert self.backend.count("test") == 1

    def test_search_cosine(self):
        self.backend.upsert("test", [
            VectorPoint(id="a", vector=[1.0, 0.0, 0.0, 0.0], payload={"t": "x"}),
            VectorPoint(id="b", vector=[0.0, 1.0, 0.0, 0.0], payload={"t": "y"}),
            VectorPoint(id="c", vector=[0.9, 0.1, 0.0, 0.0], payload={"t": "x"}),
        ])
        result = self.backend.search("test", [1.0, 0.0, 0.0, 0.0], limit=2)
        assert len(result.points) == 2
        assert result.points[0].id == "a"  # exact match first
        assert result.points[0].score > 0.99

    def test_search_with_filter(self):
        self.backend.upsert("test", [
            VectorPoint(id="a", vector=[1.0, 0.0, 0.0, 0.0], payload={"t": "x"}),
            VectorPoint(id="b", vector=[0.9, 0.1, 0.0, 0.0], payload={"t": "y"}),
        ])
        f = Filter(must=[Filter.match("t", "y")])
        result = self.backend.search("test", [1.0, 0.0, 0.0, 0.0], filter_=f)
        assert len(result.points) == 1
        assert result.points[0].id == "b"

    def test_search_with_threshold(self):
        self.backend.upsert("test", [
            VectorPoint(id="a", vector=[1.0, 0.0, 0.0, 0.0]),
            VectorPoint(id="b", vector=[0.0, 1.0, 0.0, 0.0]),
        ])
        result = self.backend.search("test", [1.0, 0.0, 0.0, 0.0],
                                     score_threshold=0.9)
        assert len(result.points) == 1

    def test_search_euclid(self):
        self.backend.create_collection("euc", 2, DistanceMetric.EUCLID)
        self.backend.upsert("euc", [
            VectorPoint(id="a", vector=[0.0, 0.0]),
            VectorPoint(id="b", vector=[10.0, 10.0]),
        ])
        result = self.backend.search("euc", [0.0, 0.0], limit=1)
        assert result.points[0].id == "a"

    def test_search_dot(self):
        self.backend.create_collection("dot", 2, DistanceMetric.DOT)
        self.backend.upsert("dot", [
            VectorPoint(id="a", vector=[1.0, 0.0]),
            VectorPoint(id="b", vector=[0.5, 0.5]),
        ])
        result = self.backend.search("dot", [1.0, 0.0], limit=1)
        assert result.points[0].id == "a"

    def test_search_empty_collection(self):
        result = self.backend.search("test", _vec(4))
        assert len(result.points) == 0

    def test_search_missing_collection(self):
        result = self.backend.search("nope", _vec(4))
        assert len(result.points) == 0

    def test_scroll(self):
        for i in range(5):
            self.backend.upsert("test", [
                VectorPoint(id=f"p{i}", vector=_vec(4, float(i)))
            ])
        points, offset = self.backend.scroll("test", limit=3)
        assert len(points) == 3
        assert offset is not None

        points2, offset2 = self.backend.scroll("test", limit=3, offset=offset)
        assert len(points2) == 2
        assert offset2 is None

    def test_scroll_with_filter(self):
        self.backend.upsert("test", [
            VectorPoint(id="a", vector=_vec(4), payload={"t": "x"}),
            VectorPoint(id="b", vector=_vec(4), payload={"t": "y"}),
            VectorPoint(id="c", vector=_vec(4), payload={"t": "x"}),
        ])
        f = Filter(must=[Filter.match("t", "x")])
        points, _ = self.backend.scroll("test", filter_=f)
        assert len(points) == 2


# ---------------------------------------------------------------------------
# Filter matching logic
# ---------------------------------------------------------------------------

class TestFilterMatching:
    def setup_method(self):
        self.backend = MemoryVectorBackend()
        self.backend.create_collection("f", 2)
        self.backend.upsert("f", [
            VectorPoint(id="a", vector=[1.0, 0.0], payload={"type": "IP", "risk": 3}),
            VectorPoint(id="b", vector=[0.0, 1.0], payload={"type": "DOMAIN", "risk": 8}),
            VectorPoint(id="c", vector=[0.5, 0.5], payload={"type": "IP", "risk": 9}),
        ])

    def test_must_not(self):
        f = Filter(must_not=[Filter.match("type", "IP")])
        result = self.backend.search("f", [1.0, 0.0], filter_=f)
        assert all(p.payload["type"] != "IP" for p in result.points)

    def test_should(self):
        f = Filter(should=[Filter.match("type", "DOMAIN"), Filter.match("risk", 3)])
        result = self.backend.search("f", [1.0, 0.0], filter_=f)
        assert len(result.points) == 2

    def test_range_filter(self):
        f = Filter(must=[Filter.range("risk", gte=5)])
        result = self.backend.search("f", [1.0, 0.0], filter_=f)
        assert all(p.payload["risk"] >= 5 for p in result.points)

    def test_combined_must_and_range(self):
        f = Filter(
            must=[Filter.match("type", "IP"), Filter.range("risk", gte=5)],
        )
        result = self.backend.search("f", [1.0, 0.0], filter_=f)
        assert len(result.points) == 1
        assert result.points[0].id == "c"


# ---------------------------------------------------------------------------
# create_vector_store factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_memory(self):
        store = create_vector_store(QdrantConfig(backend=QdrantBackend.MEMORY))
        assert isinstance(store, MemoryVectorBackend)

    def test_default(self):
        store = create_vector_store()
        assert isinstance(store, MemoryVectorBackend)


# ---------------------------------------------------------------------------
# QdrantClient high-level
# ---------------------------------------------------------------------------

class TestQdrantClient:
    def setup_method(self):
        self.client = _make_client()

    def test_ensure_collection(self):
        assert self.client.ensure_collection("events", vector_size=4)
        # Idempotent
        assert self.client.ensure_collection("events", vector_size=4)

    def test_delete_collection(self):
        self.client.ensure_collection("events", 4)
        assert self.client.delete_collection("events")

    def test_list_collections(self):
        self.client.ensure_collection("a", 4)
        self.client.ensure_collection("b", 4)
        names = self.client.list_collections()
        assert len(names) == 2

    def test_collection_info(self):
        self.client.ensure_collection("events", 4)
        info = self.client.collection_info("events")
        assert info is not None
        assert info.vector_size == 4

    def test_upsert_and_search(self):
        self.client.ensure_collection("events", 4)
        self.client.upsert("events", [
            VectorPoint(id="1", vector=[1.0, 0.0, 0.0, 0.0], payload={"t": "IP"}),
            VectorPoint(id="2", vector=[0.0, 1.0, 0.0, 0.0], payload={"t": "DNS"}),
        ])
        result = self.client.search("events", [1.0, 0.0, 0.0, 0.0], limit=1)
        assert len(result.points) == 1
        assert result.points[0].id == "1"

    def test_batch_upsert(self):
        self.client.ensure_collection("events", 4)
        points = [VectorPoint(id=str(i), vector=_vec(4, float(i))) for i in range(250)]
        count = self.client.upsert("events", points, batch_size=50)
        assert count == 250
        assert self.client.count("events") == 250

    def test_get_and_delete(self):
        self.client.ensure_collection("events", 4)
        self.client.upsert("events", [
            VectorPoint(id="1", vector=_vec(4)),
            VectorPoint(id="2", vector=_vec(4)),
        ])
        got = self.client.get("events", ["1"])
        assert len(got) == 1

        self.client.delete("events", ["1"])
        assert self.client.count("events") == 1

    def test_scroll(self):
        self.client.ensure_collection("events", 4)
        for i in range(10):
            self.client.upsert("events", [
                VectorPoint(id=f"p{i:02d}", vector=_vec(4, float(i)))
            ])
        points, offset = self.client.scroll("events", limit=5)
        assert len(points) == 5
        assert offset is not None

    def test_stats(self):
        self.client.ensure_collection("a", 4)
        self.client.upsert("a", [VectorPoint(id="1", vector=_vec(4))])
        stats = self.client.stats()
        assert stats["collections"] == 1
        assert stats["total_points"] == 1
        assert stats["backend"] == "memory"

    def test_collection_prefix(self):
        client = _make_client(prefix="myapp_")
        client.ensure_collection("events", 4)
        names = client.list_collections()
        assert all(n.startswith("myapp_") for n in names)

    def test_search_with_filter(self):
        self.client.ensure_collection("events", 4)
        self.client.upsert("events", [
            VectorPoint(id="1", vector=[1.0, 0.0, 0.0, 0.0], payload={"type": "IP"}),
            VectorPoint(id="2", vector=[0.9, 0.1, 0.0, 0.0], payload={"type": "DNS"}),
        ])
        f = Filter(must=[Filter.match("type", "DNS")])
        result = self.client.search("events", [1.0, 0.0, 0.0, 0.0], filter_=f)
        assert len(result.points) == 1
        assert result.points[0].payload["type"] == "DNS"
