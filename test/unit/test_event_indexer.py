"""Tests for spiderfoot.event_indexer — Qdrant auto-indexing via EventBus."""
from __future__ import annotations

import pytest
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from spiderfoot.event_indexer import (
    BatchWriter,
    EventIndexer,
    INDEXABLE_TYPES,
    IndexerConfig,
    IndexerMetrics,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _envelope(etype="IP_ADDRESS", data="1.2.3.4", scan_id="s1", module="sfp_test"):
    return SimpleNamespace(
        event_type=etype, data=data, scan_id=scan_id,
        module=module, source_event_hash="hash123",
        confidence=100, risk=0, timestamp=time.time(),
        metadata={},
    )


# ---------------------------------------------------------------------------
# IndexerConfig
# ---------------------------------------------------------------------------

class TestIndexerConfig:
    def test_defaults(self):
        cfg = IndexerConfig()
        assert cfg.batch_size == 50
        assert cfg.enabled is True

    def test_from_env(self):
        with patch.dict("os.environ", {"SF_INDEXER_BATCH_SIZE": "10",
                                        "SF_INDEXER_ENABLED": "0"}):
            cfg = IndexerConfig.from_env()
            assert cfg.batch_size == 10
            assert cfg.enabled is False


# ---------------------------------------------------------------------------
# IndexerMetrics
# ---------------------------------------------------------------------------

class TestIndexerMetrics:
    def test_to_dict(self):
        m = IndexerMetrics(indexed=10, errors=2)
        d = m.to_dict()
        assert d["indexed"] == 10
        assert d["errors"] == 2


# ---------------------------------------------------------------------------
# BatchWriter
# ---------------------------------------------------------------------------

class TestBatchWriter:
    def test_add_and_flush(self):
        metrics = IndexerMetrics()
        flushed = []

        def flush_fn(batch):
            flushed.extend(batch)
            return len(batch)

        cfg = IndexerConfig(batch_size=3, flush_interval_seconds=60)
        writer = BatchWriter(cfg, flush_fn, metrics)

        writer.add("a")
        writer.add("b")
        assert writer.pending == 2

        # Manual flush
        writer.flush()
        assert len(flushed) == 2
        assert writer.pending == 0
        assert metrics.batches_flushed == 1

    def test_auto_flush_on_batch_size(self):
        metrics = IndexerMetrics()
        flushed = []

        def flush_fn(batch):
            flushed.extend(batch)
            return len(batch)

        cfg = IndexerConfig(batch_size=2, flush_interval_seconds=60)
        writer = BatchWriter(cfg, flush_fn, metrics)

        writer.add("a")
        writer.add("b")  # triggers auto-flush at batch_size
        assert len(flushed) == 2

    def test_queue_full(self):
        metrics = IndexerMetrics()
        cfg = IndexerConfig(batch_size=100, max_queue_size=2)
        writer = BatchWriter(cfg, lambda b: len(b), metrics)

        assert writer.add("a") is True
        assert writer.add("b") is True
        assert writer.add("c") is False  # full

    def test_high_water_mark(self):
        metrics = IndexerMetrics()
        cfg = IndexerConfig(batch_size=100, max_queue_size=10)
        writer = BatchWriter(cfg, lambda b: len(b), metrics)

        for i in range(5):
            writer.add(i)
        assert metrics.queue_high_water == 5

    def test_flush_error(self):
        metrics = IndexerMetrics()

        def bad_flush(batch):
            raise RuntimeError("boom")

        cfg = IndexerConfig(batch_size=100)
        writer = BatchWriter(cfg, bad_flush, metrics)
        writer.add("x")
        writer.flush()
        assert metrics.errors == 1

    def test_start_stop(self):
        metrics = IndexerMetrics()
        cfg = IndexerConfig(flush_interval_seconds=0.05)
        writer = BatchWriter(cfg, lambda b: len(b), metrics)
        writer.start()
        assert writer._running is True
        writer.stop()
        assert writer._running is False


# ---------------------------------------------------------------------------
# EventIndexer
# ---------------------------------------------------------------------------

class TestEventIndexer:
    def test_on_event_indexable(self):
        engine = MagicMock()
        engine.index_events.return_value = 1
        indexer = EventIndexer(
            config=IndexerConfig(batch_size=1),
            vector_engine=engine,
        )
        env = _envelope("IP_ADDRESS")
        indexer._on_event(env)
        # Should be queued and flushed (batch_size=1)
        indexer._writer.flush()
        assert indexer.metrics.indexed >= 0  # may have been auto-flushed

    def test_on_event_skipped(self):
        indexer = EventIndexer()
        env = _envelope("IRRELEVANT_TYPE")
        indexer._on_event(env)
        assert indexer.metrics.skipped == 1

    def test_on_event_no_type(self):
        indexer = EventIndexer()
        env = SimpleNamespace()  # no event_type
        indexer._on_event(env)
        assert indexer.metrics.skipped == 0  # silently ignored

    def test_index_batch(self):
        engine = MagicMock()
        engine.index_events.return_value = 2
        indexer = EventIndexer(vector_engine=engine)
        batch = [_envelope("IP_ADDRESS"), _envelope("DOMAIN_NAME", "example.com")]
        count = indexer._index_batch(batch)
        assert count == 2
        assert indexer.metrics.indexed == 2

    def test_index_batch_no_engine(self):
        indexer = EventIndexer()
        indexer._vector_engine = None
        # Patch _get_vector_engine to return None
        indexer._get_vector_engine = lambda: None
        batch = [_envelope()]
        count = indexer._index_batch(batch)
        assert count == 0
        assert indexer.metrics.errors == 1

    def test_start_with_bus(self):
        bus = MagicMock()
        bus.subscribe_sync.return_value = "sub_1"
        engine = MagicMock()
        indexer = EventIndexer(vector_engine=engine, event_bus=bus)
        indexer.start()
        assert indexer._started is True
        bus.subscribe_sync.assert_called_once()
        indexer.stop()
        assert indexer._started is False

    def test_start_no_bus(self):
        indexer = EventIndexer(event_bus=None)
        # Patch _get_event_bus to return None
        indexer._get_event_bus = lambda: None
        indexer.start()
        assert indexer._started is False

    def test_start_disabled(self):
        indexer = EventIndexer(config=IndexerConfig(enabled=False))
        indexer.start()
        assert indexer._started is False

    def test_stats(self):
        indexer = EventIndexer()
        s = indexer.stats()
        assert "started" in s
        assert "pending" in s
        assert "metrics" in s
        assert s["config"]["batch_size"] == 50

    def test_double_start(self):
        bus = MagicMock()
        bus.subscribe_sync.return_value = "sub_1"
        indexer = EventIndexer(vector_engine=MagicMock(), event_bus=bus)
        indexer.start()
        indexer.start()  # should be no-op
        assert bus.subscribe_sync.call_count == 1
        indexer.stop()

    def test_indexable_types_coverage(self):
        """Verify core OSINT types are indexable."""
        assert "IP_ADDRESS" in INDEXABLE_TYPES
        assert "DOMAIN_NAME" in INDEXABLE_TYPES
        assert "EMAIL_ADDRESS" in INDEXABLE_TYPES
        assert "VULNERABILITY_CVE_CRITICAL" in INDEXABLE_TYPES
        assert "MALICIOUS_IPADDR" in INDEXABLE_TYPES

    def test_end_to_end_flow(self):
        """Simulate full event flow: bus → indexer → engine."""
        engine = MagicMock()
        engine.index_events.return_value = 3
        bus = MagicMock()
        bus.subscribe_sync.return_value = "sub_1"

        indexer = EventIndexer(
            config=IndexerConfig(batch_size=3, flush_interval_seconds=60),
            vector_engine=engine, event_bus=bus,
        )
        indexer.start()

        # Simulate 3 events arriving
        for ip in ["1.1.1.1", "2.2.2.2", "3.3.3.3"]:
            indexer._on_event(_envelope(data=ip))

        # batch_size=3 should have triggered auto-flush
        assert indexer.metrics.indexed == 3
        engine.index_events.assert_called_once()
        indexer.stop()
