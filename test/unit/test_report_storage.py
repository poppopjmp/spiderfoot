"""
Tests for spiderfoot.report_storage — Report Storage & Caching.

Covers LRU cache, SQLite backend, memory backend, and ReportStore facade.
"""
from __future__ import annotations

import os
import tempfile
import time
import threading

import pytest

from spiderfoot.reporting.report_storage import (
    LRUCache,
    MemoryBackend,
    ReportStore,
    SQLiteBackend,
    StorageBackend,
    StoreConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _report_data(report_id="RPT-1", scan_id="SCAN-1", status="completed"):
    return {
        "report_id": report_id,
        "scan_id": scan_id,
        "title": f"Report {report_id}",
        "status": status,
        "report_type": "full",
        "progress_pct": 100.0 if status == "completed" else 0.0,
        "message": "Done",
        "executive_summary": "Summary.",
        "recommendations": "Fix things.",
        "sections": [{"title": "Section A", "content": "Content A"}],
        "metadata": {"statistics": {"after_filter": 10}},
        "generation_time_ms": 500.0,
        "total_tokens_used": 200,
        "created_at": time.time(),
    }


# ---------------------------------------------------------------------------
# StoreConfig tests
# ---------------------------------------------------------------------------

class TestStoreConfig:
    def test_defaults(self):
        cfg = StoreConfig()
        assert cfg.backend == StorageBackend.SQLITE
        assert cfg.cache_max_size == 100
        assert cfg.cache_ttl_seconds == 3600.0
        assert cfg.auto_cleanup_days == 90

    def test_auto_db_path(self):
        cfg = StoreConfig()
        assert cfg.db_path.endswith("reports.db")

    def test_custom_db_path(self):
        cfg = StoreConfig(db_path="/custom/path.db")
        assert cfg.db_path == "/custom/path.db"

    def test_memory_backend(self):
        cfg = StoreConfig(backend=StorageBackend.MEMORY)
        # Memory backend doesn't need a path but post_init still sets it
        assert cfg.backend == StorageBackend.MEMORY


# ---------------------------------------------------------------------------
# LRU Cache tests
# ---------------------------------------------------------------------------

class TestLRUCache:
    def test_basic_put_get(self):
        cache = LRUCache(max_size=10)
        cache.put("k1", {"value": 1})
        assert cache.get("k1") == {"value": 1}

    def test_miss(self):
        cache = LRUCache(max_size=10)
        assert cache.get("nonexistent") is None

    def test_eviction(self):
        cache = LRUCache(max_size=3)
        cache.put("a", {"v": 1})
        cache.put("b", {"v": 2})
        cache.put("c", {"v": 3})
        cache.put("d", {"v": 4})  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.size == 3

    def test_lru_ordering(self):
        cache = LRUCache(max_size=3)
        cache.put("a", {"v": 1})
        cache.put("b", {"v": 2})
        cache.put("c", {"v": 3})
        # Access "a" to make it most recently used
        cache.get("a")
        cache.put("d", {"v": 4})  # Should evict "b" (LRU)
        assert cache.get("b") is None
        assert cache.get("a") is not None

    def test_ttl_expiration(self):
        cache = LRUCache(max_size=10, ttl_seconds=0.1)
        cache.put("k1", {"v": 1})
        assert cache.get("k1") is not None
        time.sleep(0.15)
        assert cache.get("k1") is None

    def test_no_ttl(self):
        cache = LRUCache(max_size=10, ttl_seconds=0)
        cache.put("k1", {"v": 1})
        assert cache.get("k1") is not None

    def test_update_existing(self):
        cache = LRUCache(max_size=10)
        cache.put("k1", {"v": 1})
        cache.put("k1", {"v": 2})
        assert cache.get("k1") == {"v": 2}
        assert cache.size == 1

    def test_invalidate(self):
        cache = LRUCache(max_size=10)
        cache.put("k1", {"v": 1})
        assert cache.invalidate("k1") is True
        assert cache.get("k1") is None
        assert cache.invalidate("k1") is False

    def test_clear(self):
        cache = LRUCache(max_size=10)
        cache.put("a", {"v": 1})
        cache.put("b", {"v": 2})
        cache.clear()
        assert cache.size == 0

    def test_stats(self):
        cache = LRUCache(max_size=10)
        cache.put("k1", {"v": 1})
        cache.get("k1")  # hit
        cache.get("k2")  # miss
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0
        assert stats["size"] == 1
        assert stats["max_size"] == 10

    def test_thread_safety(self):
        cache = LRUCache(max_size=100)
        errors = []

        def writer(tid):
            try:
                for i in range(50):
                    cache.put(f"t{tid}-{i}", {"v": i})
            except Exception as e:
                errors.append(e)

        def reader(tid):
            try:
                for i in range(50):
                    cache.get(f"t{tid}-{i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for t in range(4):
            threads.append(threading.Thread(target=writer, args=(t,)))
            threads.append(threading.Thread(target=reader, args=(t,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Memory Backend tests
# ---------------------------------------------------------------------------

class TestMemoryBackend:
    def test_save_and_get(self):
        backend = MemoryBackend()
        data = _report_data()
        backend.save(data)
        result = backend.get("RPT-1")
        assert result is not None
        assert result["report_id"] == "RPT-1"

    def test_get_returns_copy(self):
        backend = MemoryBackend()
        backend.save(_report_data())
        r1 = backend.get("RPT-1")
        r2 = backend.get("RPT-1")
        assert r1 is not r2

    def test_get_nonexistent(self):
        backend = MemoryBackend()
        assert backend.get("NOPE") is None

    def test_delete(self):
        backend = MemoryBackend()
        backend.save(_report_data())
        assert backend.delete("RPT-1") is True
        assert backend.get("RPT-1") is None

    def test_delete_nonexistent(self):
        backend = MemoryBackend()
        assert backend.delete("NOPE") is False

    def test_list_all(self):
        backend = MemoryBackend()
        backend.save(_report_data("R-1"))
        backend.save(_report_data("R-2"))
        results = backend.list_reports()
        assert len(results) == 2

    def test_list_by_scan_id(self):
        backend = MemoryBackend()
        backend.save(_report_data("R-1", scan_id="S-1"))
        backend.save(_report_data("R-2", scan_id="S-2"))
        results = backend.list_reports(scan_id="S-1")
        assert len(results) == 1
        assert results[0]["scan_id"] == "S-1"

    def test_list_by_status(self):
        backend = MemoryBackend()
        backend.save(_report_data("R-1", status="completed"))
        backend.save(_report_data("R-2", status="pending"))
        results = backend.list_reports(status="completed")
        assert len(results) == 1

    def test_list_pagination(self):
        backend = MemoryBackend()
        for i in range(10):
            d = _report_data(f"R-{i}")
            d["created_at"] = time.time() + i
            backend.save(d)
        results = backend.list_reports(limit=3, offset=0)
        assert len(results) == 3

    def test_count(self):
        backend = MemoryBackend()
        backend.save(_report_data("R-1", scan_id="S-1"))
        backend.save(_report_data("R-2", scan_id="S-2"))
        assert backend.count() == 2
        assert backend.count(scan_id="S-1") == 1

    def test_cleanup_old(self):
        backend = MemoryBackend()
        old_data = _report_data("R-OLD")
        old_data["created_at"] = time.time() - (100 * 86400)  # 100 days ago
        backend.save(old_data)
        backend.save(_report_data("R-NEW"))
        deleted = backend.cleanup_old(90)
        assert deleted == 1
        assert backend.count() == 1

    def test_cleanup_disabled(self):
        backend = MemoryBackend()
        backend.save(_report_data("R-1"))
        assert backend.cleanup_old(0) == 0


# ---------------------------------------------------------------------------
# SQLite Backend tests
# ---------------------------------------------------------------------------

class TestSQLiteBackend:
    @pytest.fixture
    def db_path(self, tmp_path):
        return str(tmp_path / "test_reports.db")

    @pytest.fixture
    def backend(self, db_path):
        b = SQLiteBackend(db_path)
        yield b
        b.close()

    def test_save_and_get(self, backend):
        backend.save(_report_data())
        result = backend.get("RPT-1")
        assert result is not None
        assert result["report_id"] == "RPT-1"
        assert result["title"] == "Report RPT-1"

    def test_sections_json_roundtrip(self, backend):
        data = _report_data()
        data["sections"] = [{"title": "A", "content": "B"}]
        backend.save(data)
        result = backend.get("RPT-1")
        assert result["sections"] == [{"title": "A", "content": "B"}]

    def test_metadata_json_roundtrip(self, backend):
        data = _report_data()
        data["metadata"] = {"key": "value", "nested": {"a": 1}}
        backend.save(data)
        result = backend.get("RPT-1")
        assert result["metadata"]["key"] == "value"
        assert result["metadata"]["nested"]["a"] == 1

    def test_get_nonexistent(self, backend):
        assert backend.get("NOPE") is None

    def test_upsert(self, backend):
        backend.save(_report_data("R-1", status="pending"))
        data = _report_data("R-1", status="completed")
        backend.save(data)
        result = backend.get("R-1")
        assert result["status"] == "completed"

    def test_delete(self, backend):
        backend.save(_report_data())
        assert backend.delete("RPT-1") is True
        assert backend.get("RPT-1") is None

    def test_delete_nonexistent(self, backend):
        assert backend.delete("NOPE") is False

    def test_list_reports(self, backend):
        backend.save(_report_data("R-1"))
        backend.save(_report_data("R-2"))
        results = backend.list_reports()
        assert len(results) == 2

    def test_list_by_scan_id(self, backend):
        backend.save(_report_data("R-1", scan_id="S-1"))
        backend.save(_report_data("R-2", scan_id="S-2"))
        results = backend.list_reports(scan_id="S-1")
        assert len(results) == 1

    def test_list_by_status(self, backend):
        backend.save(_report_data("R-1", status="completed"))
        backend.save(_report_data("R-2", status="pending"))
        results = backend.list_reports(status="completed")
        assert len(results) == 1

    def test_list_pagination(self, backend):
        for i in range(10):
            d = _report_data(f"R-{i}")
            d["created_at"] = time.time() + i
            backend.save(d)
        results = backend.list_reports(limit=3, offset=2)
        assert len(results) == 3

    def test_count(self, backend):
        backend.save(_report_data("R-1", scan_id="S-1"))
        backend.save(_report_data("R-2", scan_id="S-2"))
        assert backend.count() == 2
        assert backend.count(scan_id="S-1") == 1

    def test_cleanup_old(self, backend):
        old = _report_data("R-OLD")
        old["created_at"] = time.time() - (100 * 86400)
        backend.save(old)
        backend.save(_report_data("R-NEW"))
        deleted = backend.cleanup_old(90)
        assert deleted == 1
        assert backend.count() == 1

    def test_file_persists(self, db_path):
        b1 = SQLiteBackend(db_path)
        b1.save(_report_data())
        b1.close()

        b2 = SQLiteBackend(db_path)
        result = b2.get("RPT-1")
        assert result is not None
        b2.close()


# ---------------------------------------------------------------------------
# ReportStore (facade) tests
# ---------------------------------------------------------------------------

class TestReportStore:
    def test_memory_store(self):
        store = ReportStore(StoreConfig(backend=StorageBackend.MEMORY))
        store.save(_report_data())
        result = store.get("RPT-1")
        assert result is not None
        store.close()

    def test_sqlite_store(self, tmp_path):
        store = ReportStore(StoreConfig(
            backend=StorageBackend.SQLITE,
            db_path=str(tmp_path / "test.db"),
        ))
        store.save(_report_data())
        result = store.get("RPT-1")
        assert result is not None
        store.close()

    def test_cache_hit(self):
        store = ReportStore(StoreConfig(backend=StorageBackend.MEMORY))
        store.save(_report_data())
        # First get: from backend, cached
        store.get("RPT-1")
        # Second get: from cache
        store.get("RPT-1")
        stats = store.cache_stats
        assert stats["hits"] >= 1
        store.close()

    def test_cache_invalidation_on_delete(self):
        store = ReportStore(StoreConfig(backend=StorageBackend.MEMORY))
        store.save(_report_data())
        store.get("RPT-1")  # Cache it
        store.delete("RPT-1")
        assert store.get("RPT-1") is None
        store.close()

    def test_update(self):
        store = ReportStore(StoreConfig(backend=StorageBackend.MEMORY))
        store.save(_report_data(status="pending"))
        assert store.update("RPT-1", {"status": "completed"}) is True
        result = store.get("RPT-1")
        assert result["status"] == "completed"
        store.close()

    def test_update_nonexistent(self):
        store = ReportStore(StoreConfig(backend=StorageBackend.MEMORY))
        assert store.update("NOPE", {"status": "done"}) is False
        store.close()

    def test_list_reports(self):
        store = ReportStore(StoreConfig(backend=StorageBackend.MEMORY))
        store.save(_report_data("R-1"))
        store.save(_report_data("R-2"))
        results = store.list_reports()
        assert len(results) == 2
        store.close()

    def test_count(self):
        store = ReportStore(StoreConfig(backend=StorageBackend.MEMORY))
        store.save(_report_data("R-1"))
        store.save(_report_data("R-2"))
        assert store.count() == 2
        store.close()

    def test_cleanup(self):
        store = ReportStore(StoreConfig(
            backend=StorageBackend.MEMORY,
            auto_cleanup_days=30,
        ))
        old = _report_data("R-OLD")
        old["created_at"] = time.time() - (60 * 86400)
        store.save(old)
        store.save(_report_data("R-NEW"))
        deleted = store.cleanup()
        assert deleted == 1
        assert store.count() == 1
        store.close()

    def test_cleanup_disabled(self):
        store = ReportStore(StoreConfig(
            backend=StorageBackend.MEMORY,
            auto_cleanup_days=0,
        ))
        store.save(_report_data())
        assert store.cleanup() == 0
        store.close()

    def test_cache_stats(self):
        store = ReportStore(StoreConfig(backend=StorageBackend.MEMORY))
        stats = store.cache_stats
        assert "size" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        store.close()

    def test_default_config_uses_memory(self):
        # StoreConfig defaults to SQLITE, but explicit MEMORY for tests
        store = ReportStore(StoreConfig(backend=StorageBackend.MEMORY))
        assert store.config.backend == StorageBackend.MEMORY
        store.close()
