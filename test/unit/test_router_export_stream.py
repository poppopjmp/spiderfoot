"""Tests for the JSONL streaming export endpoint in spiderfoot.api.routers.export.

The DB handle, app config, and SpiderFoot are mocked so the
/scans/{scan_id}/export/stream generator runs without a database: it should
emit one JSONL record per event, exclude ROOT events, honour the event_type
filter, and 404 when the scan does not exist.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.export as export_mod
from spiderfoot.api.dependencies import get_api_key


_EVENTS = [
    [1, "8.8.8.8", "x", "sfp_dns", "IP_ADDRESS", 100, 0, 0, "h1", "sh1"],
    [2, "root", "x", "sfp", "ROOT", 100, 0, 0, "h0", "sh0"],
    [3, "a.com", "x", "sfp_dns", "INTERNET_NAME", 100, 0, 0, "h2", "sh2"],
]


def _make_client(scan_info, events=None):
    dbh = MagicMock()
    dbh.scanInstanceGet.return_value = scan_info
    dbh.scanResultEvent.return_value = events or []
    ctx = [
        patch("spiderfoot.api.dependencies.get_app_config",
              lambda: MagicMock(get_config=lambda: {})),
        patch("spiderfoot.sflib.core.SpiderFoot", lambda cfg: MagicMock()),
        patch.object(export_mod, "_get_dbh", lambda: dbh),
    ]
    for p in ctx:
        p.start()
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(export_mod.router)
    return TestClient(app), ctx


def _lines(resp):
    return [json.loads(l) for l in resp.text.strip().split("\n") if l]


class TestExportStream:
    def test_streams_jsonl_excluding_root(self):
        client, ctx = _make_client(["s1", "My Scan", "example.com"], _EVENTS)
        try:
            resp = client.get("/scans/s1/export/stream")
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("application/x-ndjson")
            records = _lines(resp)
            types = [r["event_type"] for r in records]
            # ROOT is filtered out; the two real events remain.
            assert types == ["IP_ADDRESS", "INTERNET_NAME"]
        finally:
            for p in ctx:
                p.stop()

    def test_event_type_filter(self):
        client, ctx = _make_client(["s1", "n", "t"], _EVENTS)
        try:
            resp = client.get("/scans/s1/export/stream",
                             params={"event_type": "IP_ADDRESS"})
            records = _lines(resp)
            assert len(records) == 1
            assert records[0]["event_type"] == "IP_ADDRESS"
        finally:
            for p in ctx:
                p.stop()

    def test_scan_not_found_404(self):
        client, ctx = _make_client(None)
        try:
            assert client.get("/scans/s1/export/stream").status_code == 404
        finally:
            for p in ctx:
                p.stop()

    def test_attachment_filename_header(self):
        client, ctx = _make_client(["s1", "n", "t"], _EVENTS)
        try:
            resp = client.get("/scans/s1/export/stream")
            assert ".jsonl" in resp.headers["content-disposition"]
            assert resp.headers["x-content-type-options"] == "nosniff"
        finally:
            for p in ctx:
                p.stop()
