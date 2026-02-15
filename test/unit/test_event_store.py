"""Tests for spiderfoot.event_store."""
from __future__ import annotations

import time
import pytest
from spiderfoot.events.event_store import (
    EventPriority,
    StoredEvent,
    EventQuery,
    RetentionPolicy,
    EventStore,
)


def _make_event(event_id="e1", scan_id="s1", event_type="IP_ADDRESS",
                module="sfp_dns", data="192.168.1.1", **kwargs):
    return StoredEvent(
        event_id=event_id, scan_id=scan_id, event_type=event_type,
        module=module, data=data, **kwargs
    )


class TestStoredEvent:
    def test_defaults(self):
        e = _make_event()
        assert e.event_id == "e1"
        assert e.priority == EventPriority.INFO

    def test_add_tag(self):
        e = _make_event()
        result = e.add_tag("important")
        assert "important" in e.tags
        assert result is e
        e.add_tag("important")  # no duplicate
        assert e.tags.count("important") == 1

    def test_set_meta(self):
        e = _make_event()
        result = e.set_meta("source", "manual")
        assert e.metadata["source"] == "manual"
        assert result is e

    def test_to_dict(self):
        e = _make_event()
        d = e.to_dict()
        assert d["event_id"] == "e1"
        assert d["priority"] == "INFO"


class TestRetentionPolicy:
    def test_defaults(self):
        p = RetentionPolicy()
        assert p.max_events == 0
        assert p.max_age_seconds == 0

    def test_to_dict(self):
        p = RetentionPolicy(max_events=100)
        d = p.to_dict()
        assert d["max_events"] == 100


class TestEventStore:
    def test_store_and_get(self):
        store = EventStore()
        e = _make_event()
        store.store(e)
        assert store.get("e1") is e

    def test_get_missing(self):
        store = EventStore()
        assert store.get("missing") is None

    def test_count(self):
        store = EventStore()
        store.store(_make_event("e1", "s1"))
        store.store(_make_event("e2", "s1"))
        store.store(_make_event("e3", "s2"))
        assert store.count() == 3
        assert store.count("s1") == 2

    def test_delete(self):
        store = EventStore()
        store.store(_make_event("e1"))
        assert store.delete("e1") is True
        assert store.delete("e1") is False
        assert store.count() == 0

    def test_delete_scan(self):
        store = EventStore()
        store.store(_make_event("e1", "s1"))
        store.store(_make_event("e2", "s1"))
        store.store(_make_event("e3", "s2"))
        removed = store.delete_scan("s1")
        assert removed == 2
        assert store.count() == 1

    def test_clear(self):
        store = EventStore()
        store.store(_make_event("e1"))
        store.store(_make_event("e2"))
        store.clear()
        assert store.count() == 0

    def test_query_by_scan(self):
        store = EventStore()
        store.store(_make_event("e1", "s1"))
        store.store(_make_event("e2", "s2"))
        results = store.query(EventQuery(scan_id="s1"))
        assert len(results) == 1
        assert results[0].event_id == "e1"

    def test_query_by_type(self):
        store = EventStore()
        store.store(_make_event("e1", event_type="IP_ADDRESS"))
        store.store(_make_event("e2", event_type="DOMAIN"))
        results = store.query(EventQuery(event_type="IP_ADDRESS"))
        assert len(results) == 1

    def test_query_by_module(self):
        store = EventStore()
        store.store(_make_event("e1", module="sfp_dns"))
        store.store(_make_event("e2", module="sfp_whois"))
        results = store.query(EventQuery(module="sfp_dns"))
        assert len(results) == 1

    def test_query_by_priority(self):
        store = EventStore()
        store.store(_make_event("e1", priority=EventPriority.CRITICAL))
        store.store(_make_event("e2", priority=EventPriority.LOW))
        results = store.query(EventQuery(min_priority=EventPriority.HIGH))
        assert len(results) == 1
        assert results[0].event_id == "e1"

    def test_query_by_tag(self):
        store = EventStore()
        e = _make_event("e1")
        e.add_tag("vuln")
        store.store(e)
        store.store(_make_event("e2"))
        results = store.query(EventQuery(tag="vuln"))
        assert len(results) == 1

    def test_query_limit_offset(self):
        store = EventStore()
        for i in range(5):
            store.store(_make_event(f"e{i}"))
        results = store.query(EventQuery(limit=2, offset=1))
        assert len(results) == 2

    def test_query_time_range(self):
        store = EventStore()
        now = time.time()
        store.store(_make_event("e1", timestamp=now - 100))
        store.store(_make_event("e2", timestamp=now))
        results = store.query(EventQuery(since=now - 50))
        assert len(results) == 1
        assert results[0].event_id == "e2"

    def test_get_event_types(self):
        store = EventStore()
        store.store(_make_event("e1", event_type="IP_ADDRESS"))
        store.store(_make_event("e2", event_type="DOMAIN"))
        types = store.get_event_types()
        assert types == ["DOMAIN", "IP_ADDRESS"]

    def test_get_event_types_by_scan(self):
        store = EventStore()
        store.store(_make_event("e1", scan_id="s1", event_type="IP_ADDRESS"))
        store.store(_make_event("e2", scan_id="s2", event_type="DOMAIN"))
        types = store.get_event_types(scan_id="s1")
        assert types == ["IP_ADDRESS"]

    def test_get_modules(self):
        store = EventStore()
        store.store(_make_event("e1", module="sfp_dns"))
        store.store(_make_event("e2", module="sfp_whois"))
        modules = store.get_modules()
        assert modules == ["sfp_dns", "sfp_whois"]

    def test_retention_max_events(self):
        policy = RetentionPolicy(max_events=3)
        store = EventStore(retention=policy)
        for i in range(5):
            store.store(_make_event(f"e{i}", priority=EventPriority(i % 5)))
        assert store.count() <= 3

    def test_retention_max_age(self):
        policy = RetentionPolicy(max_age_seconds=0.01)
        store = EventStore(retention=policy)
        store.store(_make_event("e_old", timestamp=time.time() - 1))
        store.store(_make_event("e_new"))
        # Old event should have been purged
        assert store.get("e_old") is None

    def test_summary(self):
        store = EventStore()
        store.store(_make_event("e1", scan_id="s1", event_type="IP", module="sfp_dns"))
        s = store.summary()
        assert s["total_events"] == 1
        assert s["scans"] == 1
        assert s["event_types"] == 1

    def test_to_dict(self):
        store = EventStore()
        store.store(_make_event("e1"))
        d = store.to_dict()
        assert "summary" in d
        assert "retention" in d
        assert len(d["events"]) == 1

    def test_index_cleanup_on_delete(self):
        store = EventStore()
        store.store(_make_event("e1", event_type="IP"))
        store.delete("e1")
        assert store.get_event_types() == []
        assert store.get_modules() == []
