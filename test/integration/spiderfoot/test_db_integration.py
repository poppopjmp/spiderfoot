"""Real-PostgreSQL integration tests for the SpiderFootDb persistence layer.

The DB layer is PostgreSQL-only and cannot be meaningfully unit-tested (its SQL,
schema, row mapping, and config round trip only exercise against a real server).
These tests run the full scan/event/config CRUD lifecycle against a live
PostgreSQL instance.

They are skipped unless ``SF_POSTGRES_DSN`` points at a reachable PostgreSQL —
so they are a no-op in the normal unit run and only gate in the CI
integration job (which provisions a postgres service).
"""
from __future__ import annotations

import os
import time
import uuid

import pytest

pytestmark = pytest.mark.integration

DSN = os.environ.get("SF_POSTGRES_DSN", "")
if not DSN:
    pytest.skip(
        "SF_POSTGRES_DSN not set — DB integration tests require PostgreSQL",
        allow_module_level=True,
    )

from spiderfoot.db import SpiderFootDb
from spiderfoot import SpiderFootEvent
from spiderfoot.sflib.config import configSerialize, configUnserialize


@pytest.fixture(scope="module")
def dbh():
    """A SpiderFootDb connected to the live PostgreSQL (schema created)."""
    opts = {"__database": DSN, "__dbtype": "postgresql"}
    handle = SpiderFootDb(opts, init=True)
    return handle


@pytest.fixture
def scan_id(dbh):
    """A fresh scan instance, torn down afterwards."""
    sid = "it-" + uuid.uuid4().hex[:16]
    dbh.scanInstanceCreate(sid, "integration-test", "example.com")
    yield sid
    try:
        dbh.scanInstanceDelete(sid)
    except Exception:
        pass


def _root_and_child(target="example.com"):
    root = SpiderFootEvent("ROOT", target, "", None)
    child = SpiderFootEvent("IP_ADDRESS", "1.2.3.4", "sfp_test", root)
    return root, child


class TestScanLifecycle:
    def test_create_and_get(self, dbh, scan_id):
        rec = dbh.scanInstanceGet(scan_id)
        assert rec is not None
        # row: (guid, name, seed_target, created, started, ended, status, count)
        assert rec[0] == scan_id
        assert rec[1] == "integration-test"
        assert rec[2] == "example.com"

    def test_list_includes_scan(self, dbh, scan_id):
        ids = [row[0] for row in dbh.scanInstanceList()]
        assert scan_id in ids

    def test_get_unknown_returns_none(self, dbh):
        assert dbh.scanInstanceGet("does-not-exist-" + uuid.uuid4().hex) is None

    def test_delete_removes_scan(self, dbh):
        sid = "it-del-" + uuid.uuid4().hex[:12]
        dbh.scanInstanceCreate(sid, "to-delete", "example.org")
        assert dbh.scanInstanceGet(sid) is not None
        dbh.scanInstanceDelete(sid)
        assert dbh.scanInstanceGet(sid) is None


class TestEventStorage:
    def test_store_and_retrieve_events(self, dbh, scan_id):
        root, child = _root_and_child()
        dbh.scanEventStore(scan_id, root)
        dbh.scanEventStore(scan_id, child)

        rows = dbh.scanResultEvent(scan_id, "IP_ADDRESS")
        datas = [r[1] for r in rows]
        assert "1.2.3.4" in datas

    def test_result_summary_by_type(self, dbh, scan_id):
        root, child = _root_and_child()
        dbh.scanEventStore(scan_id, root)
        dbh.scanEventStore(scan_id, child)
        summary = dbh.scanResultSummary(scan_id, "type")
        types = {row[0] for row in summary}
        assert "IP_ADDRESS" in types

    def test_invalid_summary_by_raises(self, dbh, scan_id):
        with pytest.raises(ValueError):
            dbh.scanResultSummary(scan_id, "bogus-grouping")


class TestScanLog:
    def test_log_event(self, dbh, scan_id):
        # Should not raise; persists a log line for the scan.
        dbh.scanLogEvent(scan_id, "INFO", "integration log line", "test")


class TestConfigRoundTrip:
    def test_config_persists_through_postgres(self, dbh):
        # End-to-end validation of the config round trip (incl. the bool fix):
        # values stored and read back via real PostgreSQL must survive intact.
        opts = {
            "test:str_opt": "hello",
            "test:int_opt": "42",
            "test:bool_true": "1",
            "test:bool_false": "0",
        }
        dbh.configSet(opts)
        stored = dbh.configGet()
        assert stored.get("test:str_opt") == "hello"
        assert str(stored.get("test:int_opt")) == "42"
        assert str(stored.get("test:bool_true")) == "1"
        assert str(stored.get("test:bool_false")) == "0"

    def test_full_serialize_db_unserialize_roundtrip(self, dbh):
        # The real production path: configSerialize -> DB (configSet) ->
        # configGet -> configUnserialize. End-to-end validation that boolean
        # options survive the PostgreSQL round trip as their original bools
        # (regression for the int-1-vs-str-"1" bool flip).
        reference = {
            "_rt_enabled": True,
            "_rt_disabled": False,
            "_rt_count": 7,
            "_rt_name": "rtval",
        }
        dbh.configSet(configSerialize(reference, filterSystem=False))
        restored = configUnserialize(dbh.configGet(), reference, filterSystem=False)
        assert restored["_rt_enabled"] is True
        assert restored["_rt_disabled"] is False
        assert restored["_rt_count"] == 7
        assert restored["_rt_name"] == "rtval"
