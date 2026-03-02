# -------------------------------------------------------------------------------
# Name:         Database Performance Tests
# Purpose:      Unit tests for Cycles 71-90 (Database Performance)
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2025-07-16
# Copyright:    (c) Agostino Panico 2025
# Licence:      MIT
# -------------------------------------------------------------------------------
"""
Tests for database performance features:
- Cycle 71: QueryDiagnostics / EXPLAIN ANALYZE utilities
- Cycle 72-73: Index improvements (structural, verified at schema level)
- Cycle 74: Bulk event insert + EventBatchWriter
- Cycle 75: LISTEN/NOTIFY service
- Cycle 76: Table partitioning manager
- Cycle 77: VACUUM ANALYZE utility
- Cycle 78: INSERT ON CONFLICT deduplication
- Cycle 79: Redis scan statistics cache
- Cycles 80-90: Read replica router
"""
import json
import threading
import time
import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch, PropertyMock


# ====================================================================== #
# Cycle 71: QueryDiagnostics Tests                                       #
# ====================================================================== #

class TestExplainResult(unittest.TestCase):
    """Test ExplainResult dataclass and parsing."""

    def test_import(self):
        from spiderfoot.db.db_diagnostics import ExplainResult
        r = ExplainResult(query_name="test")
        self.assertEqual(r.query_name, "test")
        self.assertEqual(r.total_cost, 0.0)
        self.assertFalse(r.has_seq_scan)

    def test_to_dict(self):
        from spiderfoot.db.db_diagnostics import ExplainResult
        r = ExplainResult(
            query_name="q1",
            total_cost=42.5,
            has_seq_scan=True,
            execution_time_ms=15.3,
        )
        d = r.to_dict()
        self.assertEqual(d["query_name"], "q1")
        self.assertEqual(d["total_cost"], 42.5)
        self.assertTrue(d["has_seq_scan"])

    def test_parse_explain_output_seq_scan(self):
        from spiderfoot.db.db_diagnostics import _parse_explain_output
        rows = [
            "Seq Scan on tbl_scan_results  (cost=0.00..1234.56 rows=100 width=64) (actual time=0.001..50.000 rows=100 loops=1)",
            "Planning Time: 0.150 ms",
            "Execution Time: 50.200 ms",
        ]
        r = _parse_explain_output("test_q", rows)
        self.assertEqual(r.query_name, "test_q")
        self.assertTrue(r.has_seq_scan)
        self.assertFalse(r.has_index_scan)
        self.assertAlmostEqual(r.total_cost, 1234.56, places=2)
        self.assertEqual(r.estimated_rows, 100)
        self.assertAlmostEqual(r.planning_time_ms, 0.15, places=2)
        self.assertAlmostEqual(r.execution_time_ms, 50.2, places=1)
        self.assertTrue(len(r.warnings) > 0)

    def test_parse_explain_output_index_scan(self):
        from spiderfoot.db.db_diagnostics import _parse_explain_output
        rows = [
            "Index Scan using idx_scan_results_hash on tbl_scan_results  (cost=0.43..8.45 rows=1 width=64) (actual time=0.01..0.02 rows=1 loops=1)",
            "Planning Time: 0.100 ms",
            "Execution Time: 0.050 ms",
        ]
        r = _parse_explain_output("idx_q", rows)
        self.assertFalse(r.has_seq_scan)
        self.assertTrue(r.has_index_scan)
        self.assertAlmostEqual(r.total_cost, 8.45, places=2)

    def test_parse_explain_high_cost_warning(self):
        from spiderfoot.db.db_diagnostics import _parse_explain_output
        rows = [
            "Seq Scan on big_table (cost=0.00..15000.00 rows=50000 width=128)",
        ]
        r = _parse_explain_output("big", rows)
        warnings = [w for w in r.warnings if "High estimated cost" in w]
        self.assertTrue(len(warnings) > 0)

    def test_parse_slow_execution_warning(self):
        from spiderfoot.db.db_diagnostics import _parse_explain_output
        rows = [
            "Index Scan (cost=0.00..5.00 rows=1) (actual time=0.01..1500.00 rows=1 loops=1)",
            "Execution Time: 1500.500 ms",
        ]
        r = _parse_explain_output("slow", rows)
        warnings = [w for w in r.warnings if "Slow execution" in w]
        self.assertTrue(len(warnings) > 0)


class TestQueryDiagnostics(unittest.TestCase):
    """Test QueryDiagnostics class with mock connection."""

    def _mock_conn(self, rows=None):
        if rows is None:
            rows = [("Seq Scan on tbl (cost=0.00..10.00 rows=5)",)]
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        conn.cursor.return_value = cursor
        return conn

    def test_init_none_raises(self):
        from spiderfoot.db.db_diagnostics import QueryDiagnostics
        with self.assertRaises(ValueError):
            QueryDiagnostics(None)

    def test_explain_custom(self):
        from spiderfoot.db.db_diagnostics import QueryDiagnostics
        conn = self._mock_conn()
        diag = QueryDiagnostics(conn)
        r = diag.explain_custom("custom", "SELECT 1", ())
        self.assertEqual(r.query_name, "custom")

    def test_explain_all_returns_5_queries(self):
        from spiderfoot.db.db_diagnostics import QueryDiagnostics
        conn = self._mock_conn()
        diag = QueryDiagnostics(conn)
        results = diag.explain_all("test-scan-id")
        self.assertEqual(len(results), 5)
        self.assertIn("scan_result_listing", results)
        self.assertIn("event_type_count", results)
        self.assertIn("correlation_lookup", results)
        self.assertIn("event_children_direct", results)
        self.assertIn("unique_results", results)

    def test_health_check(self):
        from spiderfoot.db.db_diagnostics import QueryDiagnostics
        conn = self._mock_conn()
        diag = QueryDiagnostics(conn)
        report = diag.health_check("test-scan")
        self.assertIn("status", report)
        self.assertIn("queries", report)
        self.assertIn("recommendations", report)

    def test_explain_handles_error(self):
        from spiderfoot.db.db_diagnostics import QueryDiagnostics
        conn = MagicMock()
        cursor = MagicMock()
        cursor.execute.side_effect = Exception("connection lost")
        conn.cursor.return_value = cursor
        diag = QueryDiagnostics(conn)
        r = diag.explain_scan_result_listing("scan-id")
        self.assertTrue(len(r.warnings) > 0)
        self.assertIn("Query failed", r.warnings[0])

    def test_query_patterns_exist(self):
        from spiderfoot.db.db_diagnostics import QueryDiagnostics
        self.assertEqual(len(QueryDiagnostics.QUERY_PATTERNS), 5)
        for name, qry in QueryDiagnostics.QUERY_PATTERNS.items():
            self.assertIn("EXPLAIN ANALYZE", qry)


# ====================================================================== #
# Cycle 72-73: Index Tests (schema-level verification)                   #
# ====================================================================== #

class TestIndexSchema(unittest.TestCase):
    """Verify index DDL is present in schema definitions."""

    def test_fp_partial_index_in_init(self):
        """Cycle 72: false_positive partial index exists in schema."""
        from spiderfoot.db import get_schema_queries
        queries = get_schema_queries("postgresql")
        joined = " ".join(queries)
        self.assertIn("idx_scan_results_fp", joined)
        self.assertIn("false_positive = 1", joined)

    def test_type_time_index_in_init(self):
        """Cycle 72: type+time descending index exists in schema."""
        from spiderfoot.db import get_schema_queries
        queries = get_schema_queries("postgresql")
        joined = " ".join(queries)
        self.assertIn("idx_scan_results_type_time", joined)
        self.assertIn("generated DESC", joined)

    def test_trigram_index_in_core(self):
        """Cycle 73: GIN trigram index DDL exists in DbCore."""
        from spiderfoot.db.db_core import DbCore
        trgm = " ".join(DbCore.trigram_schema_queries)
        self.assertIn("pg_trgm", trgm)
        self.assertIn("gin_trgm_ops", trgm)
        self.assertIn("idx_scan_results_data_trgm", trgm)

    def test_dedup_constraint_in_init(self):
        """Cycle 78: unique constraint for dedup exists in schema."""
        from spiderfoot.db import get_schema_queries
        queries = get_schema_queries("postgresql")
        joined = " ".join(queries)
        self.assertIn("uq_scan_results_hash", joined)


# ====================================================================== #
# Cycle 74: Bulk Event Insert Tests                                      #
# ====================================================================== #

class TestBulkEventInsert(unittest.TestCase):
    """Test EventManager.scanEventStoreBulk."""

    def _make_event_manager(self):
        from spiderfoot.db.db_event import EventManager
        dbh = MagicMock()
        conn = MagicMock()
        lock = threading.RLock()
        return EventManager(dbh, conn, lock, "postgresql")

    def _make_event(self, data="test-data", event_type="IP_ADDRESS", module="sfp_test"):
        """Create a mock SpiderFootEvent."""
        evt = MagicMock()
        evt.data = data
        evt.eventType = event_type
        evt.module = module
        evt.hash = f"hash_{data}"
        evt.generated = time.time()
        evt.confidence = 100
        evt.visibility = 100
        evt.risk = 0
        evt.sourceEventHash = "ROOT"
        # Make isinstance check pass
        from spiderfoot.events.event import SpiderFootEvent
        evt.__class__ = SpiderFootEvent
        return evt

    def test_bulk_empty_list(self):
        em = self._make_event_manager()
        result = em.scanEventStoreBulk("scan-1", [])
        self.assertEqual(result, 0)

    def test_bulk_invalid_instanceid(self):
        em = self._make_event_manager()
        with self.assertRaises(TypeError):
            em.scanEventStoreBulk("", [])

    def test_bulk_insert_calls_executemany(self):
        em = self._make_event_manager()
        events = [self._make_event(f"data-{i}") for i in range(5)]
        count = em.scanEventStoreBulk("scan-1", events)
        self.assertEqual(count, 5)
        em.dbh.executemany.assert_called_once()
        em.conn.commit.assert_called_once()

    def test_bulk_insert_on_conflict_clause(self):
        """Cycle 78: bulk query uses ON CONFLICT DO NOTHING."""
        em = self._make_event_manager()
        events = [self._make_event("data-1")]
        em.scanEventStoreBulk("scan-1", events)
        call_args = em.dbh.executemany.call_args
        query = call_args[0][0]
        self.assertIn("ON CONFLICT", query)
        self.assertIn("DO NOTHING", query)

    def test_bulk_insert_with_truncate(self):
        em = self._make_event_manager()
        events = [self._make_event("x" * 200)]
        em.scanEventStoreBulk("scan-1", events, truncateSize=50)
        call_args = em.dbh.executemany.call_args
        rows = call_args[0][1]
        # data field is at index 8
        self.assertEqual(len(rows[0][8]), 50)

    def test_bulk_filters_invalid_events(self):
        em = self._make_event_manager()
        events = [self._make_event("valid"), "not_an_event", 42]
        count = em.scanEventStoreBulk("scan-1", events)
        self.assertEqual(count, 1)

    def test_bulk_rollback_on_error(self):
        import psycopg2
        em = self._make_event_manager()
        em.dbh.executemany.side_effect = psycopg2.Error("test error")
        events = [self._make_event("data")]
        with self.assertRaises(OSError):
            em.scanEventStoreBulk("scan-1", events)
        em.conn.rollback.assert_called_once()


class TestEventBatchWriter(unittest.TestCase):
    """Test EventBatchWriter with timed flushing."""

    def _make_writer(self, batch_size=5, flush_interval=0.1):
        from spiderfoot.db.db_event import EventBatchWriter
        em = MagicMock()
        em.scanEventStoreBulk.return_value = batch_size
        writer = EventBatchWriter(em, "scan-1", batch_size=batch_size, flush_interval=flush_interval)
        return writer, em

    def _make_event(self, data="test"):
        from spiderfoot.events.event import SpiderFootEvent
        evt = MagicMock()
        evt.__class__ = SpiderFootEvent
        return evt

    def test_batch_writer_init(self):
        from spiderfoot.db.db_event import EventBatchWriter
        em = MagicMock()
        w = EventBatchWriter(em, "scan-1")
        self.assertEqual(w.stats["total_flushed"], 0)
        self.assertEqual(w.stats["buffer_size"], 0)

    def test_batch_writer_add_below_threshold(self):
        writer, em = self._make_writer(batch_size=10)
        for i in range(5):
            writer.add(self._make_event(f"d{i}"))
        # Below batch_size — not flushed yet
        self.assertEqual(writer.stats["buffer_size"], 5)
        em.scanEventStoreBulk.assert_not_called()

    def test_batch_writer_add_triggers_flush(self):
        writer, em = self._make_writer(batch_size=3)
        em.scanEventStoreBulk.return_value = 3
        for i in range(3):
            writer.add(self._make_event(f"d{i}"))
        # Batch should have been flushed
        time.sleep(0.05)
        em.scanEventStoreBulk.assert_called()

    def test_batch_writer_stop_flushes(self):
        writer, em = self._make_writer(batch_size=100, flush_interval=10)
        for i in range(5):
            writer.add(self._make_event(f"d{i}"))
        writer.stop()
        em.scanEventStoreBulk.assert_called()

    def test_batch_writer_timed_flush(self):
        writer, em = self._make_writer(batch_size=1000, flush_interval=0.1)
        em.scanEventStoreBulk.return_value = 2
        writer.start()
        for i in range(2):
            writer.add(self._make_event(f"d{i}"))
        time.sleep(0.3)  # wait for timer flush
        writer.stop()
        em.scanEventStoreBulk.assert_called()

    def test_batch_writer_stats(self):
        from spiderfoot.db.db_event import EventBatchWriter
        em = MagicMock()
        em.scanEventStoreBulk.return_value = 0
        w = EventBatchWriter(em, "scan-1", batch_size=5)
        stats = w.stats
        self.assertIn("total_flushed", stats)
        self.assertIn("flush_count", stats)
        self.assertIn("buffer_size", stats)


# ====================================================================== #
# Cycle 75: LISTEN/NOTIFY Tests                                         #
# ====================================================================== #

class TestNotifyPayload(unittest.TestCase):
    """Test NotifyPayload dataclass."""

    def test_to_json(self):
        from spiderfoot.db.db_notify import NotifyPayload
        p = NotifyPayload(scan_id="s1", event_hash="h1", event_type="IP_ADDRESS")
        j = p.to_json()
        d = json.loads(j)
        self.assertEqual(d["scan_id"], "s1")
        self.assertEqual(d["event_hash"], "h1")

    def test_from_json(self):
        from spiderfoot.db.db_notify import NotifyPayload
        j = '{"scan_id": "s2", "event_hash": "h2", "event_type": "DOMAIN_NAME"}'
        p = NotifyPayload.from_json(j)
        self.assertEqual(p.scan_id, "s2")
        self.assertEqual(p.event_type, "DOMAIN_NAME")

    def test_roundtrip(self):
        from spiderfoot.db.db_notify import NotifyPayload
        p1 = NotifyPayload(scan_id="s3", event_hash="h3", event_type="EMAILADDR", timestamp=1234567890.0)
        p2 = NotifyPayload.from_json(p1.to_json())
        self.assertEqual(p1.scan_id, p2.scan_id)
        self.assertEqual(p1.event_hash, p2.event_hash)


class TestPgNotifyService(unittest.TestCase):
    """Test PgNotifyService with mock connection."""

    def test_init_none_raises(self):
        from spiderfoot.db.db_notify import PgNotifyService
        with self.assertRaises(ValueError):
            PgNotifyService(None)

    def test_notify_event(self):
        from spiderfoot.db.db_notify import PgNotifyService
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        svc = PgNotifyService(conn)
        result = svc.notify_event("s1", "h1", "IP_ADDRESS")
        self.assertTrue(result)
        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args
        self.assertIn("pg_notify", call_args[0][0])

    def test_notify_scan_status(self):
        from spiderfoot.db.db_notify import PgNotifyService
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        svc = PgNotifyService(conn)
        result = svc.notify_scan_status("s1", "FINISHED")
        self.assertTrue(result)

    def test_notify_handles_error(self):
        from spiderfoot.db.db_notify import PgNotifyService
        conn = MagicMock()
        conn.cursor.side_effect = Exception("conn error")
        svc = PgNotifyService(conn)
        result = svc.notify_event("s1", "h1", "TYPE")
        self.assertFalse(result)

    def test_stop(self):
        from spiderfoot.db.db_notify import PgNotifyService
        conn = MagicMock()
        svc = PgNotifyService(conn)
        svc.stop()
        self.assertFalse(svc._listening)


# ====================================================================== #
# Cycle 76: Table Partitioning Tests                                     #
# ====================================================================== #

class TestPartitionManager(unittest.TestCase):
    """Test PartitionManager for scan result partitioning."""

    def test_partition_name(self):
        from spiderfoot.db.db_performance import PartitionManager
        name = PartitionManager.partition_name("abc-123-def")
        self.assertEqual(name, "tbl_scan_results_abc_123_def")

    def test_get_partitioned_ddl(self):
        from spiderfoot.db.db_performance import PartitionManager
        ddl = PartitionManager.get_partitioned_table_ddl()
        self.assertTrue(len(ddl) >= 2)
        self.assertIn("PARTITION BY LIST", ddl[0])

    def test_ensure_partition_existing(self):
        from spiderfoot.db.db_performance import PartitionManager
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)  # partition exists
        conn.cursor.return_value = cursor
        pm = PartitionManager(conn)
        result = pm.ensure_partition("scan-1")
        self.assertTrue(result)

    def test_ensure_partition_creates_new(self):
        from spiderfoot.db.db_performance import PartitionManager
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None  # doesn't exist
        conn.cursor.return_value = cursor
        pm = PartitionManager(conn)
        result = pm.ensure_partition("scan-2")
        self.assertTrue(result)
        # Should have called CREATE TABLE
        calls = [str(c) for c in cursor.execute.call_args_list]
        self.assertTrue(any("PARTITION" in c for c in calls))

    def test_ensure_partition_cached(self):
        from spiderfoot.db.db_performance import PartitionManager
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        conn.cursor.return_value = cursor
        pm = PartitionManager(conn)
        pm.ensure_partition("scan-3")
        pm.ensure_partition("scan-3")  # second call should be cached
        # cursor only created once
        self.assertEqual(conn.cursor.call_count, 1)

    def test_drop_partition(self):
        from spiderfoot.db.db_performance import PartitionManager
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        pm = PartitionManager(conn)
        result = pm.drop_partition("scan-4")
        self.assertTrue(result)
        calls = [str(c) for c in cursor.execute.call_args_list]
        self.assertTrue(any("DROP TABLE" in c for c in calls))

    def test_init_none_raises(self):
        from spiderfoot.db.db_performance import PartitionManager
        with self.assertRaises(ValueError):
            PartitionManager(None)


# ====================================================================== #
# Cycle 77: VACUUM ANALYZE Tests                                        #
# ====================================================================== #

class TestVacuumAnalyze(unittest.TestCase):
    """Test VacuumAnalyze utility."""

    def test_init_none_raises(self):
        from spiderfoot.db.db_performance import VacuumAnalyze
        with self.assertRaises(ValueError):
            VacuumAnalyze(None)

    def test_vacuum_analyze_all(self):
        from spiderfoot.db.db_performance import VacuumAnalyze
        conn = MagicMock()
        conn.autocommit = False
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        va = VacuumAnalyze(conn)
        result = va.vacuum_analyze_all()
        self.assertTrue(result)
        cursor.execute.assert_called_with("VACUUM ANALYZE")

    def test_vacuum_analyze_scan(self):
        from spiderfoot.db.db_performance import VacuumAnalyze
        conn = MagicMock()
        conn.autocommit = False
        cursor = MagicMock()
        # For partition check, return None (no partition)
        cursor.fetchone.return_value = None
        conn.cursor.return_value = cursor
        va = VacuumAnalyze(conn)
        results = va.vacuum_analyze_scan("scan-1")
        self.assertIn("tbl_scan_results", results)
        self.assertIn("tbl_scan_log", results)

    def test_analyze_only(self):
        from spiderfoot.db.db_performance import VacuumAnalyze
        conn = MagicMock()
        conn.autocommit = False
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        va = VacuumAnalyze(conn)
        result = va.analyze_only("tbl_scan_results")
        self.assertTrue(result)

    def test_scan_tables_constant(self):
        from spiderfoot.db.db_performance import VacuumAnalyze
        self.assertTrue(len(VacuumAnalyze.SCAN_TABLES) >= 4)
        self.assertIn("tbl_scan_results", VacuumAnalyze.SCAN_TABLES)


# ====================================================================== #
# Cycle 78: ON CONFLICT Dedup Tests                                      #
# ====================================================================== #

class TestDedupQueries(unittest.TestCase):
    """Test ON CONFLICT deduplication queries."""

    def test_get_dedup_insert_query(self):
        from spiderfoot.db.db_performance import get_dedup_insert_query
        q = get_dedup_insert_query()
        self.assertIn("INSERT INTO tbl_scan_results", q)
        self.assertIn("ON CONFLICT", q)
        self.assertIn("DO NOTHING", q)

    def test_get_dedup_constraint_ddl(self):
        from spiderfoot.db.db_performance import get_dedup_constraint_ddl
        ddl = get_dedup_constraint_ddl()
        self.assertTrue(len(ddl) >= 1)
        joined = " ".join(ddl)
        self.assertIn("uq_scan_results_hash", joined)

    def test_single_event_store_uses_on_conflict(self):
        """Verify scanEventStore query includes ON CONFLICT."""
        from spiderfoot.db.db_event import EventManager
        from spiderfoot.events.event import SpiderFootEvent
        em = EventManager(MagicMock(), MagicMock(), threading.RLock(), "postgresql")

        # Create a source event mock that passes isinstance check
        source_evt = MagicMock(spec=SpiderFootEvent)

        # Create event mock
        evt = MagicMock()
        evt.data = "192.168.1.1"
        evt.eventType = "IP_ADDRESS"
        evt.module = "sfp_test"
        evt.hash = "abcdef123456"
        evt.generated = time.time()
        evt.confidence = 100
        evt.visibility = 100
        evt.risk = 0
        evt.sourceEvent = source_evt
        evt.sourceEventHash = "ROOT"
        evt.__class__ = SpiderFootEvent

        em.scanEventStore("scan-1", evt)
        call_args = em.dbh.execute.call_args
        query = call_args[0][0]
        self.assertIn("ON CONFLICT", query)
        self.assertIn("DO NOTHING", query)


# ====================================================================== #
# Cycle 79: Redis Scan Stats Cache Tests                                 #
# ====================================================================== #

class TestScanStatsCache(unittest.TestCase):
    """Test ScanStatsCache with mock Redis."""

    def test_disabled_when_no_redis(self):
        from spiderfoot.db.db_performance import ScanStatsCache
        cache = ScanStatsCache(redis_client=None)
        self.assertFalse(cache.enabled)
        self.assertIsNone(cache.get("scan-1"))
        self.assertFalse(cache.set("scan-1", {"count": 10}))
        self.assertFalse(cache.invalidate("scan-1"))

    def test_get_miss(self):
        from spiderfoot.db.db_performance import ScanStatsCache
        redis = MagicMock()
        redis.get.return_value = None
        cache = ScanStatsCache(redis_client=redis, ttl=30)
        result = cache.get("scan-1")
        self.assertIsNone(result)
        self.assertEqual(cache.stats["misses"], 1)

    def test_get_hit(self):
        from spiderfoot.db.db_performance import ScanStatsCache
        redis = MagicMock()
        redis.get.return_value = '{"count": 42}'
        cache = ScanStatsCache(redis_client=redis)
        result = cache.get("scan-1")
        self.assertEqual(result["count"], 42)
        self.assertEqual(cache.stats["hits"], 1)

    def test_set_stores_with_ttl(self):
        from spiderfoot.db.db_performance import ScanStatsCache
        redis = MagicMock()
        cache = ScanStatsCache(redis_client=redis, ttl=60)
        cache.set("scan-1", {"count": 10})
        redis.setex.assert_called_once()
        call_args = redis.setex.call_args
        self.assertEqual(call_args[0][1], 60)  # TTL

    def test_invalidate(self):
        from spiderfoot.db.db_performance import ScanStatsCache
        redis = MagicMock()
        redis.delete.return_value = 1
        cache = ScanStatsCache(redis_client=redis)
        result = cache.invalidate("scan-1")
        self.assertTrue(result)
        redis.delete.assert_called_once()

    def test_invalidate_all(self):
        from spiderfoot.db.db_performance import ScanStatsCache
        redis = MagicMock()
        redis.keys.return_value = ["sf:scan_stats:s1", "sf:scan_stats:s2"]
        redis.delete.return_value = 2
        cache = ScanStatsCache(redis_client=redis)
        count = cache.invalidate_all()
        self.assertEqual(count, 2)

    def test_stats_hit_rate(self):
        from spiderfoot.db.db_performance import ScanStatsCache
        redis = MagicMock()
        redis.get.side_effect = ['{"a":1}', None, '{"b":2}']
        cache = ScanStatsCache(redis_client=redis)
        cache.get("s1")  # hit
        cache.get("s2")  # miss
        cache.get("s3")  # hit
        stats = cache.stats
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 2/3, places=2)

    def test_key_prefix(self):
        from spiderfoot.db.db_performance import ScanStatsCache
        cache = ScanStatsCache(redis_client=MagicMock())
        key = cache._key("my-scan-id")
        self.assertTrue(key.startswith("sf:scan_stats:"))
        self.assertIn("my-scan-id", key)


# ====================================================================== #
# Cycles 80-90: Read Replica Router Tests                                #
# ====================================================================== #

class TestReplicaConfig(unittest.TestCase):
    """Test ReplicaConfig dataclass."""

    def test_defaults(self):
        from spiderfoot.db.db_performance import ReplicaConfig
        rc = ReplicaConfig(dsn="host=localhost dbname=sf_replica")
        self.assertEqual(rc.name, "replica")
        self.assertEqual(rc.weight, 1)
        self.assertTrue(rc.enabled)
        self.assertEqual(rc.max_lag_seconds, 30.0)


class TestReadReplicaRouter(unittest.TestCase):
    """Test ReadReplicaRouter with mock connections."""

    def test_init_none_raises(self):
        from spiderfoot.db.db_performance import ReadReplicaRouter
        with self.assertRaises(ValueError):
            ReadReplicaRouter(None)

    def test_write_always_primary(self):
        from spiderfoot.db.db_performance import ReadReplicaRouter
        primary = MagicMock()
        router = ReadReplicaRouter(primary)
        self.assertIs(router.get_write_connection(), primary)

    def test_read_falls_back_to_primary(self):
        from spiderfoot.db.db_performance import ReadReplicaRouter
        primary = MagicMock()
        router = ReadReplicaRouter(primary)
        # No replicas — should return primary
        self.assertIs(router.get_read_connection(), primary)

    def test_read_with_replica(self):
        from spiderfoot.db.db_performance import ReadReplicaRouter, ReplicaConfig
        primary = MagicMock()
        router = ReadReplicaRouter(primary)
        # Manually inject a mock replica
        replica_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        replica_conn.cursor.return_value = cursor
        router._replicas.append({
            "config": ReplicaConfig(dsn="mock", name="r1"),
            "conn": replica_conn,
            "healthy": True,
            "last_check": time.time(),
        })
        conn = router.get_read_connection()
        self.assertIs(conn, replica_conn)

    def test_unhealthy_replica_falls_back(self):
        from spiderfoot.db.db_performance import ReadReplicaRouter, ReplicaConfig
        primary = MagicMock()
        router = ReadReplicaRouter(primary)
        replica_conn = MagicMock()
        cursor = MagicMock()
        cursor.execute.side_effect = Exception("dead")
        replica_conn.cursor.return_value = cursor
        router._replicas.append({
            "config": ReplicaConfig(dsn="mock", name="r1"),
            "conn": replica_conn,
            "healthy": True,
            "last_check": time.time(),
        })
        conn = router.get_read_connection()
        self.assertIs(conn, primary)

    def test_replica_count(self):
        from spiderfoot.db.db_performance import ReadReplicaRouter, ReplicaConfig
        primary = MagicMock()
        router = ReadReplicaRouter(primary)
        self.assertEqual(router.replica_count, 0)
        router._replicas.append({
            "config": ReplicaConfig(dsn="mock"),
            "conn": MagicMock(),
            "healthy": True,
            "last_check": time.time(),
        })
        self.assertEqual(router.replica_count, 1)

    def test_status(self):
        from spiderfoot.db.db_performance import ReadReplicaRouter
        primary = MagicMock()
        router = ReadReplicaRouter(primary)
        status = router.status()
        self.assertEqual(status["primary"], "connected")
        self.assertEqual(status["total"], 0)

    def test_close_replicas(self):
        from spiderfoot.db.db_performance import ReadReplicaRouter, ReplicaConfig
        primary = MagicMock()
        router = ReadReplicaRouter(primary)
        mock_conn = MagicMock()
        router._replicas.append({
            "config": ReplicaConfig(dsn="mock"),
            "conn": mock_conn,
            "healthy": True,
            "last_check": time.time(),
        })
        router.close_replicas()
        mock_conn.close.assert_called_once()
        self.assertEqual(router.replica_count, 0)

    def test_check_replica_lag(self):
        from spiderfoot.db.db_performance import ReadReplicaRouter, ReplicaConfig
        primary = MagicMock()
        router = ReadReplicaRouter(primary)
        replica_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (5.0,)  # 5 second lag
        replica_conn.cursor.return_value = cursor
        router._replicas.append({
            "config": ReplicaConfig(dsn="mock", name="r1", max_lag_seconds=30),
            "conn": replica_conn,
            "healthy": True,
            "last_check": time.time(),
        })
        lags = router.check_replica_lag()
        self.assertAlmostEqual(lags["r1"], 5.0, places=1)

    def test_check_replica_lag_exceeds_threshold(self):
        from spiderfoot.db.db_performance import ReadReplicaRouter, ReplicaConfig
        primary = MagicMock()
        router = ReadReplicaRouter(primary)
        replica_conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (60.0,)  # 60s lag > 30s threshold
        replica_conn.cursor.return_value = cursor
        router._replicas.append({
            "config": ReplicaConfig(dsn="mock", name="r1", max_lag_seconds=30),
            "conn": replica_conn,
            "healthy": True,
            "last_check": time.time(),
        })
        lags = router.check_replica_lag()
        self.assertEqual(lags["r1"], 60.0)
        # Should be marked unhealthy
        self.assertFalse(router._replicas[0]["healthy"])


if __name__ == "__main__":
    unittest.main()
